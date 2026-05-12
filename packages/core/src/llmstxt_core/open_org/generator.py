"""Generate an Open Org profile from a UK charity number.

Pipeline (per spec section 1, with v0.5 enrichment from the website analyzer):

1. Fetch raw data from the Charity Commission (existing enricher).
2. Crawl the charity's website once (``collect_website_pages``) — re-used
   by every downstream LLM call so we don't pay for two crawls.
3. From the crawled pages, derive:
   - Concatenated body text → theme extractor + mission rewriter.
   - The pages themselves → ``analyze_organisation`` for the structured
     fields llmstxt-social already extracts (programmes, beneficiaries,
     impact metrics, working name, refined contact and geography).
4. Merge CC + analyzer outputs into the Open Org schema. CC stays the
   spine (registration, income band, trustee count); the analyzer fills
   in the soft tissue the CC API never carries (services, programmes,
   contact details, beneficiaries narrative).
5. Validate against the profile schema.
6. Render the validated payload back to markdown via the converter.

Every external collaborator (CC fetch, mission rewriter, theme extractor,
website crawl, analyzer) is injectable so tests run offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from llmstxt_core.analyzer import OrganisationAnalysis, analyze_organisation
from llmstxt_core.enrichers.charity_commission import (
    CharityData,
    fetch_charity_data,
)
from llmstxt_core.extractor import ExtractedPage
from llmstxt_core.llm import CachedAnthropic, Usage
from llmstxt_core.open_org import SCHEMA_VERSION
from llmstxt_core.open_org.converter import json_to_markdown
from llmstxt_core.open_org.income_bands import income_to_band
from llmstxt_core.open_org.mission_rewriter import (
    MissionRewriteResult,
    rewrite_mission_summary,
)
from llmstxt_core.open_org.ons_geography import lookup_lad_code
from llmstxt_core.open_org.theme_extractor import (
    ThemeExtractionResult,
    extract_themes,
)
from llmstxt_core.open_org.validator import ValidationError, validate_for_kind
from llmstxt_core.open_org.website_text import collect_website_pages


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Geographic strings the CC commonly emits for organisations that operate
# nationwide. We treat these as low-signal so the analyzer's more specific
# answer ("Great Yarmouth", "East London") wins when available.
_VAGUE_AREA_TERMS = {
    "england",
    "wales",
    "scotland",
    "northern ireland",
    "united kingdom",
    "uk",
    "great britain",
    "throughout england",
    "throughout uk",
}

# How much page text we feed the theme extractor / mission rewriter. The
# analyzer prepares its own content via ``_prepare_content`` and applies its
# own caps independently.
_TEXT_MAX_CHARS = 20_000


FetchCharity = Callable[..., Awaitable[CharityData | None]]
RewriteMission = Callable[..., MissionRewriteResult]
ExtractThemes = Callable[..., ThemeExtractionResult]
CollectPages = Callable[..., Awaitable[list[ExtractedPage]]]
AnalyzeOrg = Callable[..., Awaitable[OrganisationAnalysis | None]]


class ProfileGenerationError(RuntimeError):
    """Raised when the generator cannot produce a valid Open Org profile."""

    def __init__(self, message: str, *, errors: list[dict] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


@dataclass
class GenerationResult:
    org_id: str
    markdown: str
    json_payload: dict
    flagged_themes: list[dict] = field(default_factory=list)
    total_usage: Usage = field(default_factory=Usage)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _normalise_date(value: Any) -> str | None:
    """Return an ISO ``YYYY-MM-DD`` string or ``None`` if the value can't be parsed.

    CC sometimes returns dates with a ``T00:00:00`` time suffix or full
    timestamps; the schema requires a date only.
    """
    if not isinstance(value, str):
        return None
    candidate = value.strip()[:10]
    if re.match(r"^\d{4}-\d{2}-\d{2}$", candidate):
        return candidate
    return None


def _clamp_income(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _valid_email(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if _EMAIL_RE.match(candidate):
        return candidate
    return None


def _strip_empty(d: dict) -> dict:
    """Recursively drop keys whose value is None, empty string, empty list, or empty dict."""
    if not isinstance(d, dict):
        return d
    out: dict = {}
    for k, v in d.items():
        if isinstance(v, dict):
            cleaned = _strip_empty(v)
            if cleaned:
                out[k] = cleaned
        elif v is None or v == "" or v == []:
            continue
        else:
            out[k] = v
    return out


def _pages_to_text(pages: list[ExtractedPage], max_chars: int = _TEXT_MAX_CHARS) -> str:
    """Concatenate the body text of the relevant pages with a char cap."""
    bodies = [(p.body_text or "").strip() for p in pages]
    bodies = [b for b in bodies if b]
    if not bodies:
        return ""
    text = "\n\n".join(bodies)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip()
    return text


def _is_vague_area(name: str | None) -> bool:
    if not name or not isinstance(name, str):
        return False
    return name.strip().lower() in _VAGUE_AREA_TERMS


def _merge_programmes(
    services: list[dict] | None, projects: list[dict] | None
) -> list[dict]:
    """Combine analyzer ``services`` and ``projects`` into one ``programmes``
    array, deduping by lowercase name. Services have ``eligibility``;
    projects have ``location`` — keep whichever fields each carries.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for source in (services or [], projects or []):
        for item in source:
            if not isinstance(item, dict):
                continue
            name = (item.get("name") or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            programme = {"name": name}
            for k in ("description", "eligibility", "location"):
                value = item.get(k)
                if isinstance(value, str) and value.strip():
                    programme[k] = value.strip()
            out.append(programme)
    return out


def _evidence_summary(impact_metrics: dict | None) -> dict:
    """Map analyzer's ``impact_metrics`` to ``mission.evidence_summary``.

    Analyzer shape: ``{beneficiaries_served: str|None, outcomes: [str]|None}``.
    Schema shape: ``{beneficiaries_served_text?: str, outcomes?: [str]}``.
    Returns ``{}`` when there's nothing meaningful to surface.
    """
    if not isinstance(impact_metrics, dict):
        return {}
    out: dict = {}
    served = impact_metrics.get("beneficiaries_served")
    if isinstance(served, str) and served.strip():
        out["beneficiaries_served_text"] = served.strip()
    outcomes = impact_metrics.get("outcomes")
    if isinstance(outcomes, list):
        cleaned_outcomes = [o.strip() for o in outcomes if isinstance(o, str) and o.strip()]
        if cleaned_outcomes:
            out["outcomes"] = cleaned_outcomes
    return out


def _build_payload(
    cc: CharityData,
    *,
    summary: str,
    themes: list[str],
    analysis: OrganisationAnalysis | None = None,
) -> dict:
    """Build the Open Org profile payload, merging CC and analyzer data.

    CC is the spine (registration, income, trustee count). The analyzer
    fills in the soft tissue the CC API never exposes: programmes from
    services + projects, narrative beneficiaries, evidence stubs from
    impact metrics, contact details a real human would actually use,
    working name when it differs from the registered one.
    """
    org_id = f"GB-CHC-{cc.number}"

    # --- name + also_known_as -------------------------------------------------
    analyzer_name = (
        analysis.name.strip() if analysis and isinstance(analysis.name, str) else None
    )
    also_known_as: list[str] = []
    if analyzer_name and analyzer_name.lower() != (cc.name or "").strip().lower():
        also_known_as.append(analyzer_name)

    # --- geography ------------------------------------------------------------
    cc_primary = cc.area_of_operation[0] if cc.area_of_operation else None
    analyzer_geo = (
        analysis.geographic_area.strip()
        if analysis and isinstance(analysis.geographic_area, str)
        else None
    )
    # Prefer analyzer's geographic area when CC's is vague (England, UK, etc.)
    # — the analyzer typically pulls a town/LA from the website footer.
    if analyzer_geo and (cc_primary is None or _is_vague_area(cc_primary)):
        primary_area = analyzer_geo
    else:
        primary_area = cc_primary

    # --- contact --------------------------------------------------------------
    cc_contact = cc.contact or {}
    analyzer_contact = (analysis.contact if analysis else None) or {}
    # CC takes priority where present; analyzer fills gaps. Phone normalisation
    # is light — we don't try to canonicalise UK numbers, just pass strings
    # through after stripping whitespace.
    contact_out = {
        "email": (
            _valid_email(cc_contact.get("email"))
            or _valid_email(analyzer_contact.get("email"))
        ),
        "phone": (
            (cc_contact.get("phone") or analyzer_contact.get("phone") or "").strip()
            or None
        ),
        "address": (
            (cc_contact.get("address") or analyzer_contact.get("address") or "").strip()
            or None
        ),
    }

    # --- mission summary + theory_of_change + beneficiaries ------------------
    # Prefer analyzer's mission only when CC's rewrite came back empty.
    # The CC rewrite already passes through the LLM and is informed by the
    # CC text — it's usually more legally accurate. Keep it where present.
    final_summary = summary or (
        (analysis.mission.strip() if analysis and isinstance(analysis.mission, str) else "")
    )

    theory_of_change = (
        analysis.description.strip()
        if analysis and isinstance(analysis.description, str) and analysis.description.strip()
        else None
    )

    beneficiaries_list: list[str] = []
    if analysis and isinstance(analysis.beneficiaries, str):
        candidate = analysis.beneficiaries.strip()
        if candidate:
            beneficiaries_list.append(candidate)

    # --- programmes + evidence_summary ---------------------------------------
    programmes = (
        _merge_programmes(analysis.services, analysis.projects) if analysis else []
    )
    evidence_summary = (
        _evidence_summary(analysis.impact_metrics) if analysis else {}
    )

    income = _clamp_income(cc.latest_income)

    payload: dict = {
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "name": cc.name,
            "also_known_as": also_known_as or None,
            "registration": {
                "charity_commission_ew": cc.number,
                "companies_house": cc.company_number or None,
            },
            "identifiers": {
                "org_id": org_id,
            },
            "geography": {
                "primary_area": primary_area,
                "primary_area_code": (
                    lookup_lad_code(primary_area) if primary_area else None
                ),
                "operating_areas": cc.area_of_operation or None,
            },
            "scale": {
                "annual_income_band": income_to_band(income),
                "annual_income": income,
                "trustee_count": cc.trustee_count,
            },
            "website": (cc_contact.get("web") or None),
            "founded": _normalise_date(cc.date_registered),
            "contact": contact_out,
        },
        "mission": {
            "summary": final_summary or None,
            "objects": cc.charitable_objects or None,
            "theory_of_change": theory_of_change,
            "themes": themes,
            "beneficiaries": beneficiaries_list or None,
            "programmes": programmes or None,
            "evidence_summary": evidence_summary or None,
        },
        "governance": {
            "board_size": cc.trustee_count,
            "accounts_filed_to": _normalise_date(cc.latest_acc_fin_period_end_date),
        },
    }
    cleaned = _strip_empty(payload)
    # ``mission.themes`` can be an empty list at this point if the extractor
    # returned nothing — the validator will reject it and we'll surface a
    # ProfileGenerationError below. Restore it so the validator sees the right
    # shape for its error message.
    cleaned.setdefault("mission", {}).setdefault("themes", themes)
    return cleaned


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def generate_profile_from_charity_number(
    charity_number: str,
    *,
    anthropic_client: CachedAnthropic,
    cc_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    fetch_charity: FetchCharity | None = None,
    rewrite_mission: RewriteMission | None = None,
    extract_themes: ExtractThemes | None = None,
    collect_pages: CollectPages | None = None,
    analyze: AnalyzeOrg | None = None,
) -> GenerationResult:
    """Generate an Open Org profile from a UK Charity Commission number.

    Returns markdown + JSON payload + accumulated LLM usage. Raises
    :class:`ProfileGenerationError` if the charity isn't found or the
    generated profile fails schema validation (e.g. no themes detected).

    ``anthropic_api_key`` is forwarded to the website analyzer (which
    instantiates its own SDK client internally). When omitted, the analyzer
    falls back to ``ANTHROPIC_API_KEY`` from the environment.
    """
    fetch = fetch_charity or fetch_charity_data
    rewrite = rewrite_mission or rewrite_mission_summary
    themer = extract_themes or _default_extract_themes
    pages_fn = collect_pages or collect_website_pages
    analyzer = analyze or _default_analyze

    cc = await fetch(charity_number, api_key=cc_api_key)
    if cc is None:
        raise ProfileGenerationError(
            f"Charity {charity_number!r} not found via Charity Commission"
        )

    # v0.5: a single crawl drives every downstream extractor. The analyzer
    # works on the structured pages; the theme extractor + mission rewriter
    # work on a flat-text concatenation.
    website_url = (cc.contact or {}).get("web")
    pages: list[ExtractedPage] = (
        await pages_fn(website_url) if website_url else []
    )
    website_text = _pages_to_text(pages)

    rewrite_result = rewrite(
        client=anthropic_client,
        activities_text=cc.activities or "",
    )
    theme_result = themer(
        client=anthropic_client,
        objects_text=cc.charitable_objects or "",
        activities_text=cc.activities or "",
        website_text=website_text,
    )
    analysis: OrganisationAnalysis | None = None
    if pages:
        # Defensive: a flaky analyzer (network, parse error) must never break
        # generation. CC + theme extraction alone produces a valid profile.
        try:
            analysis = await analyzer(pages=pages, api_key=anthropic_api_key)
        except Exception:  # noqa: BLE001 — see comment above
            analysis = None

    payload = _build_payload(
        cc,
        summary=rewrite_result.summary,
        themes=theme_result.themes,
        analysis=analysis if isinstance(analysis, OrganisationAnalysis) else None,
    )

    try:
        validate_for_kind(payload, kind="profile")
    except ValidationError as exc:
        # The most common failure here is ``mission.themes`` minItems=1 when
        # the theme extractor returned nothing — surface that explicitly.
        if not theme_result.themes:
            raise ProfileGenerationError(
                "No themes met the confidence threshold; cannot build a "
                "valid profile. The owner can add themes manually after "
                "claiming the profile.",
                errors=exc.errors,
            ) from exc
        raise ProfileGenerationError(
            "Generated profile failed schema validation",
            errors=exc.errors,
        ) from exc

    markdown = json_to_markdown(payload, kind="profile")

    total = Usage(
        input_tokens=rewrite_result.usage.input_tokens
        + theme_result.usage.input_tokens,
        output_tokens=rewrite_result.usage.output_tokens
        + theme_result.usage.output_tokens,
        cache_creation_tokens=rewrite_result.usage.cache_creation_tokens
        + theme_result.usage.cache_creation_tokens,
        cache_read_tokens=rewrite_result.usage.cache_read_tokens
        + theme_result.usage.cache_read_tokens,
        model=theme_result.usage.model or rewrite_result.usage.model,
    )

    return GenerationResult(
        org_id=payload["identity"]["identifiers"]["org_id"],
        markdown=markdown,
        json_payload=payload,
        flagged_themes=theme_result.flagged,
        total_usage=total,
    )


def _default_extract_themes(*args, **kwargs) -> ThemeExtractionResult:
    # Late binding so tests that patch ``extract_themes`` directly via the
    # injected callable don't accidentally hit the production module symbol.
    return extract_themes(*args, **kwargs)


async def _default_analyze(*, pages, api_key=None):
    return await analyze_organisation(pages, template="charity", api_key=api_key)


__all__ = [
    "GenerationResult",
    "ProfileGenerationError",
    "generate_profile_from_charity_number",
]
