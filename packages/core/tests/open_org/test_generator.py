"""Tests for the Open Org profile generator orchestrator.

Wires together the CC enricher, ONS lookup, mission rewriter, theme extractor,
schema validator, and JSON↔markdown converter. All external dependencies are
injected so tests are hermetic and offline.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from llmstxt_core.enrichers.charity_commission import CharityData
from llmstxt_core.llm import CachedAnthropic
from llmstxt_core.open_org.generator import (
    GenerationResult,
    ProfileGenerationError,
    generate_profile_from_charity_number,
)
from llmstxt_core.open_org.mission_rewriter import MissionRewriteResult
from llmstxt_core.open_org.theme_extractor import ThemeExtractionResult


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _full_charity_data(**overrides) -> CharityData:
    base = dict(
        name="Acme Aid",
        number="1234567",
        status="Registered",
        date_registered="2010-04-01",
        date_removed=None,
        latest_income=240_000,
        latest_expenditure=230_000,
        charitable_objects="To advance the education of young people in the UK.",
        activities="Provision of after-school clubs, mentoring, and training.",
        trustees=["Alice", "Bob"],
        contact={
            "email": "info@acme.example",
            "phone": "020 1234 5678",
            "address": "1 Acme Street, London",
            "web": "https://acme.example",
        },
        area_of_operation=["England", "Wales"],
        company_number="01234567",
        latest_acc_fin_period_end_date="2024-03-31",
        trustee_count=12,
    )
    base.update(overrides)
    return CharityData(**base)


def _stub_anthropic() -> CachedAnthropic:
    return CachedAnthropic(api_key="test")


@pytest.fixture
def fake_fetch_charity():
    return AsyncMock()


@pytest.fixture
def fake_rewrite_mission():
    def _stub(*, client, activities_text, model=None):
        return MissionRewriteResult(summary="We help young people thrive.")

    return _stub


@pytest.fixture
def fake_extract_themes():
    def _stub(*, client, objects_text, activities_text, **kw):
        return ThemeExtractionResult(
            themes=["education", "children_and_young_people"],
            flagged=[],
        )

    return _stub


@pytest.fixture(autouse=True)
def _no_real_crawls(monkeypatch):
    """Stop the generator's default ``collect_website_pages`` from hitting the
    network. Tests that exercise the crawl integration inject their own stub
    via the ``collect_pages`` parameter; this autouse fixture protects every
    other test."""

    async def _empty_pages(url, **kwargs):
        return []

    import llmstxt_core.open_org.generator as gen_mod

    monkeypatch.setattr(gen_mod, "collect_website_pages", _empty_pages)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_profile_returns_markdown_and_json(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    fake_fetch_charity.return_value = _full_charity_data()

    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
    )

    assert isinstance(result, GenerationResult)
    assert result.json_payload["schema_version"] == "open-org/v0.1"
    assert result.json_payload["identity"]["name"] == "Acme Aid"
    assert result.markdown.startswith("---\n")
    # Markdown must contain the rendered Mission heading derived from summary.
    assert "## Mission" in result.markdown


@pytest.mark.asyncio
async def test_generate_profile_maps_cc_fields_to_identity(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    fake_fetch_charity.return_value = _full_charity_data()
    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
    )
    identity = result.json_payload["identity"]
    assert identity["registration"]["charity_commission_ew"] == "1234567"
    assert identity["registration"]["companies_house"] == "01234567"
    assert identity["identifiers"]["org_id"] == "GB-CHC-1234567"
    assert identity["geography"]["primary_area"] == "England"
    assert identity["geography"]["primary_area_code"] == "E92000001"
    assert identity["geography"]["operating_areas"] == ["England", "Wales"]
    assert identity["scale"]["annual_income_band"] == "100k-250k"
    assert identity["scale"]["annual_income"] == 240_000
    assert identity["scale"]["trustee_count"] == 12
    assert identity["website"] == "https://acme.example"
    assert identity["founded"] == "2010-04-01"
    assert identity["contact"]["email"] == "info@acme.example"


@pytest.mark.asyncio
async def test_generate_profile_uses_mission_rewrite_and_themes(
    fake_fetch_charity, fake_extract_themes
):
    fake_fetch_charity.return_value = _full_charity_data()

    def stub_rewrite(*, client, activities_text, model=None):
        return MissionRewriteResult(summary="A short, plain-language mission.")

    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=stub_rewrite,
        extract_themes=fake_extract_themes,
    )

    mission = result.json_payload["mission"]
    assert mission["summary"] == "A short, plain-language mission."
    assert mission["themes"] == ["education", "children_and_young_people"]
    assert mission["objects"] == "To advance the education of young people in the UK."


@pytest.mark.asyncio
async def test_generate_profile_governance_uses_trustee_count_and_acc_period(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    fake_fetch_charity.return_value = _full_charity_data()
    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
    )
    governance = result.json_payload["governance"]
    assert governance["board_size"] == 12
    assert governance["accounts_filed_to"] == "2024-03-31"


@pytest.mark.asyncio
async def test_generate_profile_returns_combined_usage(
    fake_fetch_charity, fake_extract_themes
):
    fake_fetch_charity.return_value = _full_charity_data()

    from llmstxt_core.llm import Usage

    def rewrite(*, client, activities_text, model=None):
        return MissionRewriteResult(
            summary="ok", usage=Usage(input_tokens=100, output_tokens=20)
        )

    def themes(*, client, objects_text, activities_text, **kw):
        return ThemeExtractionResult(
            themes=["education"],
            flagged=[],
            usage=Usage(input_tokens=300, output_tokens=40),
        )

    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=rewrite,
        extract_themes=themes,
    )
    assert result.total_usage.input_tokens == 400
    assert result.total_usage.output_tokens == 60


# ---------------------------------------------------------------------------
# Sad paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raises_when_charity_not_found(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    fake_fetch_charity.return_value = None
    with pytest.raises(ProfileGenerationError) as exc:
        await generate_profile_from_charity_number(
            "9999999",
            anthropic_client=_stub_anthropic(),
            fetch_charity=fake_fetch_charity,
            rewrite_mission=fake_rewrite_mission,
            extract_themes=fake_extract_themes,
        )
    assert "not found" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_raises_when_no_themes_meet_threshold(
    fake_fetch_charity, fake_rewrite_mission
):
    fake_fetch_charity.return_value = _full_charity_data()

    def stub_themes(*, client, objects_text, activities_text, **kw):
        return ThemeExtractionResult(themes=[], flagged=[])

    with pytest.raises(ProfileGenerationError) as exc:
        await generate_profile_from_charity_number(
            "1234567",
            anthropic_client=_stub_anthropic(),
            fetch_charity=fake_fetch_charity,
            rewrite_mission=fake_rewrite_mission,
            extract_themes=stub_themes,
        )
    assert "theme" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_handles_minimal_cc_data(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    """A charity with only name + number + objects must still produce a valid profile."""
    fake_fetch_charity.return_value = CharityData(
        name="Minimal Trust",
        number="2222222",
        status="Registered",
        date_registered=None,
        date_removed=None,
        latest_income=None,
        latest_expenditure=None,
        charitable_objects="To relieve poverty.",
        activities=None,
        trustees=[],
        contact={},
    )
    result = await generate_profile_from_charity_number(
        "2222222",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
    )
    payload = result.json_payload
    assert payload["identity"]["name"] == "Minimal Trust"
    # Optional sections must be omitted, not empty.
    assert "geography" not in payload["identity"]
    assert "scale" not in payload["identity"]
    assert "governance" not in payload


@pytest.mark.asyncio
async def test_normalises_iso_datetime_to_date(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    """CC sometimes returns dates with a T00:00:00 suffix; schema needs YYYY-MM-DD."""
    fake_fetch_charity.return_value = _full_charity_data(
        date_registered="2010-04-01T00:00:00",
        latest_acc_fin_period_end_date="2024-03-31T00:00:00",
    )
    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
    )
    assert result.json_payload["identity"]["founded"] == "2010-04-01"
    assert result.json_payload["governance"]["accounts_filed_to"] == "2024-03-31"


@pytest.mark.asyncio
async def test_omits_invalid_email(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    fake_fetch_charity.return_value = _full_charity_data(
        contact={"email": "not-an-email", "phone": "020", "web": "https://x.example"}
    )
    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
    )
    contact = result.json_payload["identity"].get("contact", {})
    assert "email" not in contact
    assert contact.get("phone") == "020"


@pytest.mark.asyncio
async def test_clamps_negative_income(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    fake_fetch_charity.return_value = _full_charity_data(latest_income=-100)
    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
    )
    assert result.json_payload["identity"]["scale"]["annual_income"] == 0
    assert result.json_payload["identity"]["scale"]["annual_income_band"] == "under_10k"


@pytest.mark.asyncio
async def test_markdown_round_trips_back_to_json(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    """The generated markdown must parse back to the same JSON payload.

    This is the contract the editor relies on: the user opens the markdown,
    edits, saves, and the same converter produces the same JSON shape.
    """
    fake_fetch_charity.return_value = _full_charity_data()
    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
    )

    from llmstxt_core.open_org.converter import markdown_to_json

    re_parsed = markdown_to_json(result.markdown, kind="profile")
    assert re_parsed == result.json_payload


# ---------------------------------------------------------------------------
# v0.2.1 — website-content augmentation (now via collect_pages)
# ---------------------------------------------------------------------------


def _fake_page(body: str = "", url: str = "https://acme.example/", title: str = ""):
    """Build an ExtractedPage stand-in for the tests."""
    from llmstxt_core.extractor import ExtractedPage, PageType

    return ExtractedPage(
        url=url,
        title=title or "Acme",
        description=None,
        headings=[],
        body_text=body,
        page_type=PageType.HOME,
        contact_info=None,
        charity_number=None,
    )


async def test_generator_passes_website_text_to_theme_extractor(
    fake_fetch_charity, fake_rewrite_mission
):
    """When a website URL is on file, the crawl helper is called and its
    concatenated body text flows to the theme extractor."""
    fake_fetch_charity.return_value = _full_charity_data()

    received: dict = {}

    def stub_themes(*, client, objects_text, activities_text, website_text="", **kw):
        received["website_text"] = website_text
        return ThemeExtractionResult(
            themes=["education", "food_access"], flagged=[]
        )

    async def stub_pages(url, **kwargs):
        received["crawled_url"] = url
        return [_fake_page(body="Acme runs food banks.")]

    await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=stub_themes,
        collect_pages=stub_pages,
    )

    assert received["crawled_url"] == "https://acme.example"
    assert received["website_text"] == "Acme runs food banks."


async def test_generator_skips_crawl_when_no_website_on_file(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    """No website URL → don't call the crawl helper at all."""
    cc = _full_charity_data()
    cc.contact = {"email": "x@y.example"}  # no 'web' key
    fake_fetch_charity.return_value = cc

    collect_called = False

    async def stub_pages(url, **kwargs):
        nonlocal collect_called
        collect_called = True
        return []

    await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
        collect_pages=stub_pages,
    )
    assert collect_called is False


async def test_generator_falls_back_when_crawl_returns_empty(
    fake_fetch_charity, fake_rewrite_mission
):
    """An empty crawl result still flows; theme extractor gets website_text=''."""
    fake_fetch_charity.return_value = _full_charity_data()

    received: dict = {}

    def stub_themes(*, client, objects_text, activities_text, website_text="", **kw):
        received["website_text"] = website_text
        return ThemeExtractionResult(themes=["education"], flagged=[])

    async def empty_pages(url, **kwargs):
        return []

    await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=stub_themes,
        collect_pages=empty_pages,
    )
    assert received["website_text"] == ""


# ---------------------------------------------------------------------------
# v0.5 — analyzer enrichment (services, beneficiaries, contact, etc.)
# ---------------------------------------------------------------------------


def _stub_analysis(**overrides):
    """Build a default OrganisationAnalysis with sensible enrichment data."""
    from llmstxt_core.analyzer import OrganisationAnalysis

    base = dict(
        name="Acme Aid",
        org_type="charity",
        registration_number="1234567",
        mission="We help young people thrive.",
        description="Acme runs after-school clubs and mentoring in East London, "
        "reaching 600 young people each year.",
        geographic_area="Tower Hamlets",
        services=[
            {
                "name": "After-school club",
                "description": "Daily homework support and creative activities.",
                "eligibility": "Ages 8-16 in Tower Hamlets",
            },
            {
                "name": "Mentoring",
                "description": "1:1 weekly mentoring for young people in care.",
                "eligibility": "Referrals via local authority",
            },
        ],
        projects=[
            {
                "name": "Summer school",
                "description": "Six-week intensive in maths and reading.",
                "location": "Tower Hamlets",
            },
            # Duplicate of an existing service — should be deduped on name.
            {"name": "After-school club", "description": "Same thing"},
        ],
        impact_metrics={
            "beneficiaries_served": "600 young people per year",
            "outcomes": [
                "85% of mentees report improved confidence",
                "Reading age uplift of 1.2 years on average",
            ],
        },
        beneficiaries="Young people aged 8-16 facing disadvantage in East London",
        themes=["youth services", "education"],
        contact={
            "email": "hello@acme.example",
            "phone": "020 9999 0000",
            "address": "5 Acme Lane, London E14",
            "hours": "Mon-Fri 9-5",
        },
        team_info="Small team of 8 plus 45 active volunteers.",
        ai_guidance=[],
    )
    base.update(overrides)
    return OrganisationAnalysis(**base)


def _async_returning(value):
    async def _fn(**kwargs):
        return value
    return _fn


async def test_analyzer_output_populates_programmes(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    """Analyzer services + projects merge into mission.programmes, deduped by name."""
    fake_fetch_charity.return_value = _full_charity_data()

    async def stub_pages(url, **kwargs):
        return [_fake_page(body="some text")]

    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
        collect_pages=stub_pages,
        analyze=_async_returning(_stub_analysis()),
    )

    programmes = result.json_payload["mission"]["programmes"]
    names = [p["name"] for p in programmes]
    # Three unique programmes after dedup (the duplicate After-school club is dropped).
    assert names == ["After-school club", "Mentoring", "Summer school"]
    assert programmes[0]["eligibility"] == "Ages 8-16 in Tower Hamlets"
    assert programmes[2]["location"] == "Tower Hamlets"


async def test_analyzer_output_populates_evidence_summary(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    fake_fetch_charity.return_value = _full_charity_data()

    async def stub_pages(url, **kwargs):
        return [_fake_page(body="some text")]

    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
        collect_pages=stub_pages,
        analyze=_async_returning(_stub_analysis()),
    )

    ev = result.json_payload["mission"]["evidence_summary"]
    assert ev["beneficiaries_served_text"] == "600 young people per year"
    assert len(ev["outcomes"]) == 2


async def test_analyzer_output_populates_beneficiaries_array(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    """Analyzer's beneficiaries (string) lands as a one-item array."""
    fake_fetch_charity.return_value = _full_charity_data()

    async def stub_pages(url, **kwargs):
        return [_fake_page(body="some text")]

    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
        collect_pages=stub_pages,
        analyze=_async_returning(_stub_analysis()),
    )

    beneficiaries = result.json_payload["mission"]["beneficiaries"]
    assert beneficiaries == [
        "Young people aged 8-16 facing disadvantage in East London"
    ]


async def test_analyzer_description_lands_in_theory_of_change(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    fake_fetch_charity.return_value = _full_charity_data()

    async def stub_pages(url, **kwargs):
        return [_fake_page(body="x")]

    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
        collect_pages=stub_pages,
        analyze=_async_returning(_stub_analysis()),
    )

    assert "after-school clubs" in result.json_payload["mission"]["theory_of_change"]


async def test_analyzer_name_lands_in_also_known_as_when_distinct(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    """When the analyzer's name differs from CC's, it goes to also_known_as."""
    cc = _full_charity_data(name="Acme Trust")
    fake_fetch_charity.return_value = cc

    async def stub_pages(url, **kwargs):
        return [_fake_page(body="x")]

    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
        collect_pages=stub_pages,
        analyze=_async_returning(_stub_analysis(name="Acme Aid")),
    )

    assert result.json_payload["identity"]["also_known_as"] == ["Acme Aid"]


async def test_analyzer_name_skipped_in_also_known_as_when_same_as_cc(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    fake_fetch_charity.return_value = _full_charity_data(name="Acme Aid")

    async def stub_pages(url, **kwargs):
        return [_fake_page(body="x")]

    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
        collect_pages=stub_pages,
        analyze=_async_returning(_stub_analysis(name="Acme Aid")),
    )

    assert "also_known_as" not in result.json_payload["identity"]


async def test_analyzer_contact_fills_gaps_left_by_cc(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    """CC contact takes priority; analyzer fills email/phone/address gaps."""
    cc = _full_charity_data()
    cc.contact = {"web": "https://acme.example"}  # CC has no contact details
    fake_fetch_charity.return_value = cc

    async def stub_pages(url, **kwargs):
        return [_fake_page(body="x")]

    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
        collect_pages=stub_pages,
        analyze=_async_returning(_stub_analysis()),
    )

    contact = result.json_payload["identity"]["contact"]
    assert contact["email"] == "hello@acme.example"
    assert contact["phone"] == "020 9999 0000"
    assert contact["address"] == "5 Acme Lane, London E14"


async def test_cc_contact_wins_when_present(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    fake_fetch_charity.return_value = _full_charity_data()  # has CC contact

    async def stub_pages(url, **kwargs):
        return [_fake_page(body="x")]

    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
        collect_pages=stub_pages,
        analyze=_async_returning(_stub_analysis()),
    )

    contact = result.json_payload["identity"]["contact"]
    assert contact["email"] == "info@acme.example"
    assert contact["address"] == "1 Acme Street, London"


async def test_analyzer_geography_used_when_cc_is_vague(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    """When CC's primary_area is 'England' / 'UK' etc., prefer the analyzer's specific area."""
    cc = _full_charity_data(area_of_operation=["England", "Wales"])
    fake_fetch_charity.return_value = cc

    async def stub_pages(url, **kwargs):
        return [_fake_page(body="x")]

    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
        collect_pages=stub_pages,
        analyze=_async_returning(_stub_analysis(geographic_area="Tower Hamlets")),
    )

    assert result.json_payload["identity"]["geography"]["primary_area"] == "Tower Hamlets"


async def test_analyzer_geography_skipped_when_cc_is_specific(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    """CC 'Manchester' wins over analyzer 'Greater Manchester' — CC is already specific enough."""
    cc = _full_charity_data(area_of_operation=["Manchester"])
    fake_fetch_charity.return_value = cc

    async def stub_pages(url, **kwargs):
        return [_fake_page(body="x")]

    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
        collect_pages=stub_pages,
        analyze=_async_returning(_stub_analysis(geographic_area="Greater Manchester")),
    )

    assert result.json_payload["identity"]["geography"]["primary_area"] == "Manchester"


async def test_analyzer_failure_does_not_break_generation(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    """If the analyzer raises (network, parse), the profile still generates from CC alone."""
    fake_fetch_charity.return_value = _full_charity_data()

    async def stub_pages(url, **kwargs):
        return [_fake_page(body="x")]

    async def flaky_analyzer(**kwargs):
        raise RuntimeError("Claude said no")

    result = await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
        collect_pages=stub_pages,
        analyze=flaky_analyzer,
    )

    # CC-only payload — no programmes, no evidence_summary, no beneficiaries.
    assert result.json_payload["identity"]["name"] == "Acme Aid"
    assert "programmes" not in result.json_payload["mission"]
    assert "evidence_summary" not in result.json_payload["mission"]


async def test_analyzer_skipped_when_crawl_returns_no_pages(
    fake_fetch_charity, fake_rewrite_mission, fake_extract_themes
):
    """Don't pay for analyzer if there are no pages to feed it."""
    fake_fetch_charity.return_value = _full_charity_data()

    async def empty_pages(url, **kwargs):
        return []

    analyzer_called = False

    async def stub_analyzer(**kwargs):
        nonlocal analyzer_called
        analyzer_called = True
        return _stub_analysis()

    await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
        collect_pages=empty_pages,
        analyze=stub_analyzer,
    )

    assert analyzer_called is False
