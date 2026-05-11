"""Generate an Open Org profile from a UK charity number.

Pipeline (per spec section 1):

1. Fetch raw data from the Charity Commission (existing enricher).
2. Map CC fields to Open Org identity/governance fields.
3. Look up the ONS code for the primary area of operation.
4. Rewrite the CC ``activities`` text into a plain-language ``mission.summary``.
5. Extract ``mission.themes`` from CC objects + activities via tool_use.
6. Validate against the profile schema.
7. Render the validated payload back to markdown via the converter.

External dependencies (CC fetch, mission rewriter, theme extractor) are
injectable so tests can run offline. Production callers use the defaults.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from llmstxt_core.enrichers.charity_commission import (
    CharityData,
    fetch_charity_data,
)
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
from llmstxt_core.open_org.website_text import collect_website_text


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


FetchCharity = Callable[..., Awaitable[CharityData | None]]
RewriteMission = Callable[..., MissionRewriteResult]
ExtractThemes = Callable[..., ThemeExtractionResult]
CollectWebsite = Callable[..., Awaitable[str]]


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


def _build_payload(
    cc: CharityData,
    *,
    summary: str,
    themes: list[str],
) -> dict:
    org_id = f"GB-CHC-{cc.number}"
    primary_area = cc.area_of_operation[0] if cc.area_of_operation else None

    income = _clamp_income(cc.latest_income)

    contact_in = cc.contact or {}
    contact_out = {
        "email": _valid_email(contact_in.get("email")),
        "phone": contact_in.get("phone") or None,
        "address": contact_in.get("address") or None,
    }

    payload: dict = {
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "name": cc.name,
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
            "website": (contact_in.get("web") or None),
            "founded": _normalise_date(cc.date_registered),
            "contact": contact_out,
        },
        "mission": {
            "summary": summary or None,
            "objects": cc.charitable_objects or None,
            "themes": themes,
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
    fetch_charity: FetchCharity | None = None,
    rewrite_mission: RewriteMission | None = None,
    extract_themes: ExtractThemes | None = None,
    collect_website: CollectWebsite | None = None,
) -> GenerationResult:
    """Generate an Open Org profile from a UK Charity Commission number.

    Returns markdown + JSON payload + accumulated LLM usage. Raises
    :class:`ProfileGenerationError` if the charity isn't found or the
    generated profile fails schema validation (e.g. no themes detected).
    """
    fetch = fetch_charity or fetch_charity_data
    rewrite = rewrite_mission or rewrite_mission_summary
    themer = extract_themes or _default_extract_themes
    collect = collect_website or collect_website_text

    cc = await fetch(charity_number, api_key=cc_api_key)
    if cc is None:
        raise ProfileGenerationError(
            f"Charity {charity_number!r} not found via Charity Commission"
        )

    # v0.2.1: augment theme extraction with the charity's own website content.
    # CC ``who_what_where`` classifications are too sparse for orgs like
    # Trussell Trust and Shelter (per baseline_v0.1.md). When no website is
    # on file or the crawl fails, ``collect`` returns "" and we silently
    # fall back to CC-only theme extraction.
    website_url = (cc.contact or {}).get("web")
    website_text = await collect(website_url) if website_url else ""

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

    payload = _build_payload(
        cc,
        summary=rewrite_result.summary,
        themes=theme_result.themes,
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


__all__ = [
    "GenerationResult",
    "ProfileGenerationError",
    "generate_profile_from_charity_number",
]
