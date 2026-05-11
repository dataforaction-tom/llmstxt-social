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
    """Stop the generator's default ``collect_website_text`` from hitting the
    network. Tests that exercise the crawl integration inject their own stub
    via the ``collect_website`` parameter; this autouse fixture protects every
    other test."""

    async def _empty(url, **kwargs):
        return ""

    import llmstxt_core.open_org.generator as gen_mod

    monkeypatch.setattr(gen_mod, "collect_website_text", _empty)


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
# v0.2.1 — website-content augmentation
# ---------------------------------------------------------------------------


async def test_generator_passes_website_text_to_theme_extractor(
    fake_fetch_charity, fake_rewrite_mission
):
    """When a website URL is on file, the crawl helper is called and its
    output flows to the theme extractor."""
    fake_fetch_charity.return_value = _full_charity_data()

    received: dict = {}

    def stub_themes(*, client, objects_text, activities_text, website_text="", **kw):
        received["website_text"] = website_text
        return ThemeExtractionResult(
            themes=["education", "food_access"], flagged=[]
        )

    async def stub_collect(url, **kwargs):
        received["crawled_url"] = url
        return "Acme runs food banks."

    await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=stub_themes,
        collect_website=stub_collect,
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

    async def stub_collect(url, **kwargs):
        nonlocal collect_called
        collect_called = True
        return ""

    await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=fake_extract_themes,
        collect_website=stub_collect,
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

    async def empty_collect(url, **kwargs):
        return ""

    await generate_profile_from_charity_number(
        "1234567",
        anthropic_client=_stub_anthropic(),
        fetch_charity=fake_fetch_charity,
        rewrite_mission=fake_rewrite_mission,
        extract_themes=stub_themes,
        collect_website=empty_collect,
    )
    assert received["website_text"] == ""
