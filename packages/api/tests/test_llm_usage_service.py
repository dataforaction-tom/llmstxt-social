"""Tests for the LLM usage logging + £0.50/org/day budget service."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest import mock

import pytest


# --- pure cost calculation --------------------------------------------------

def test_usage_cost_usd_input_only():
    from llmstxt_api.services.llm_usage import usage_cost_usd
    from llmstxt_core.llm import Usage

    # 1 million input tokens on claude-sonnet-4-20250514 = $3.00
    u = Usage(input_tokens=1_000_000, output_tokens=0, model="claude-sonnet-4-20250514")
    assert usage_cost_usd(u) == Decimal("3.00")


def test_usage_cost_usd_output_only():
    from llmstxt_api.services.llm_usage import usage_cost_usd
    from llmstxt_core.llm import Usage

    # 1 million output tokens = $15.00
    u = Usage(input_tokens=0, output_tokens=1_000_000, model="claude-sonnet-4-20250514")
    assert usage_cost_usd(u) == Decimal("15.00")


def test_usage_cost_usd_includes_cache_write_and_read_pricing():
    from llmstxt_api.services.llm_usage import usage_cost_usd
    from llmstxt_core.llm import Usage

    # 1M cache write = $3.75; 1M cache read = $0.30
    u = Usage(
        input_tokens=0,
        output_tokens=0,
        cache_creation_tokens=1_000_000,
        cache_read_tokens=1_000_000,
        model="claude-sonnet-4-20250514",
    )
    assert usage_cost_usd(u) == Decimal("4.05")  # 3.75 + 0.30


def test_usage_cost_usd_realistic_strategy_session():
    """A typical strategy creation session: ~15k input (cached schema +
    conversation), ~5k cache reads (from a previous turn), ~6k output."""
    from llmstxt_api.services.llm_usage import usage_cost_usd
    from llmstxt_core.llm import Usage

    u = Usage(
        input_tokens=10_000,
        output_tokens=6_000,
        cache_creation_tokens=5_000,  # cached system on first turn
        cache_read_tokens=5_000,  # cache hits on subsequent turns
        model="claude-sonnet-4-20250514",
    )
    cost = usage_cost_usd(u)
    # 10k input @ $3/M = $0.03
    # 6k output @ $15/M = $0.09
    # 5k cache write @ $3.75/M = $0.01875
    # 5k cache read @ $0.30/M = $0.0015
    # Total: $0.14025
    assert cost == Decimal("0.14025")


def test_usage_cost_usd_unknown_model_raises():
    from llmstxt_api.services.llm_usage import usage_cost_usd, UnknownModelError
    from llmstxt_core.llm import Usage

    u = Usage(input_tokens=1000, model="claude-mystery-model")
    with pytest.raises(UnknownModelError, match="claude-mystery-model"):
        usage_cost_usd(u)


def test_usage_cost_gbp_applies_fx_rate():
    from llmstxt_api.services.llm_usage import usage_cost_gbp
    from llmstxt_core.llm import Usage

    u = Usage(input_tokens=1_000_000, model="claude-sonnet-4-20250514")
    # $3.00 USD * GBP_PER_USD constant
    gbp = usage_cost_gbp(u)
    assert gbp > Decimal("0")
    assert gbp < Decimal("3.00")  # GBP is stronger than USD


def test_daily_budget_constant_is_fifty_pence():
    """Locked decision #10 in PLAN.md: £0.50/org/day soft cap."""
    from llmstxt_api.services.llm_usage import DAILY_BUDGET_GBP
    assert DAILY_BUDGET_GBP == Decimal("0.50")


# --- log_usage --------------------------------------------------------------

def test_log_usage_creates_row_with_correct_fields():
    from llmstxt_api.services.llm_usage import log_usage
    from llmstxt_core.llm import Usage

    session = mock.MagicMock()
    usage = Usage(
        input_tokens=100,
        output_tokens=50,
        cache_creation_tokens=200,
        cache_read_tokens=300,
        model="claude-sonnet-4-20250514",
    )

    row = log_usage(
        session,
        feature="profile_generator",
        usage=usage,
        org_id="GB-CHC-1234567",
    )

    assert row.feature == "profile_generator"
    assert row.org_id == "GB-CHC-1234567"
    assert row.input_tokens == 100
    assert row.output_tokens == 50
    assert row.cache_creation_tokens == 200
    assert row.cache_read_tokens == 300
    assert row.model == "claude-sonnet-4-20250514"
    session.add.assert_called_once_with(row)


def test_log_usage_accepts_no_org_id():
    """Some features (e.g. background workers) don't have an org context."""
    from llmstxt_api.services.llm_usage import log_usage
    from llmstxt_core.llm import Usage

    session = mock.MagicMock()
    usage = Usage(input_tokens=10, model="claude-sonnet-4-20250514")
    row = log_usage(session, feature="background_task", usage=usage)
    assert row.org_id is None
    assert row.feature == "background_task"


# --- daily budget check -----------------------------------------------------

@pytest.mark.asyncio
async def test_is_within_daily_budget_true_when_no_usage():
    """An org with no usage today is trivially within budget."""
    from llmstxt_api.services.llm_usage import is_within_daily_budget

    session = mock.AsyncMock()
    execute_result = mock.MagicMock()
    execute_result.all.return_value = []  # no rows
    session.execute.return_value = execute_result

    assert await is_within_daily_budget(session, org_id="GB-CHC-1234567") is True


@pytest.mark.asyncio
async def test_is_within_daily_budget_false_when_over_cap():
    from llmstxt_api.services.llm_usage import is_within_daily_budget
    from llmstxt_api.open_org_models import LlmUsage

    session = mock.AsyncMock()
    # Simulate $5 of usage today (well over £0.50)
    huge_usage = LlmUsage(
        feature="x",
        org_id="GB-CHC-1234567",
        input_tokens=2_000_000,  # ~$6
        output_tokens=0,
        model="claude-sonnet-4-20250514",
    )
    execute_result = mock.MagicMock()
    execute_result.all.return_value = [(huge_usage,)]
    session.execute.return_value = execute_result

    assert await is_within_daily_budget(session, org_id="GB-CHC-1234567") is False


@pytest.mark.asyncio
async def test_is_within_daily_budget_respects_override_limit():
    from llmstxt_api.services.llm_usage import is_within_daily_budget
    from llmstxt_api.open_org_models import LlmUsage

    session = mock.AsyncMock()
    # 1M tokens input on Sonnet = $3.00 USD ≈ £2.37
    row = LlmUsage(
        feature="x",
        org_id="GB-CHC-X",
        input_tokens=1_000_000,
        output_tokens=0,
        model="claude-sonnet-4-20250514",
    )
    execute_result = mock.MagicMock()
    execute_result.all.return_value = [(row,)]
    session.execute.return_value = execute_result

    # Over £0.50 default cap
    assert await is_within_daily_budget(session, org_id="GB-CHC-X") is False
    # Within £10 override cap
    assert await is_within_daily_budget(
        session, org_id="GB-CHC-X", limit_gbp=Decimal("10.00")
    ) is True
