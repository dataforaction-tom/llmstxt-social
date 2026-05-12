"""Anthropic usage logging and per-org daily budget enforcement.

Per PLAN.md row 10: soft cap £0.50/org/day. Over-budget orgs get 429 from
the route layer; this service surfaces ``is_within_daily_budget`` for that
check, and ``log_usage`` for writing rows on every Anthropic call.

Pricing is denominated in USD per million tokens (Anthropic's published
rate-card) and converted to GBP for the budget check via a fixed FX rate.
The FX rate is a constant rather than a live FX lookup — close enough for
a soft cap, and avoids adding an FX provider dependency.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmstxt_api.open_org_models import LlmUsage
from llmstxt_core.llm import Usage


class UnknownModelError(ValueError):
    """Raised when a usage row references a model not in ``MODEL_PRICING``."""


# USD per million tokens. Keep keys in sync with the model IDs CachedAnthropic
# actually calls — update when models are added.
MODEL_PRICING: dict[str, dict[str, Decimal]] = {
    # Sonnet 4 (2025-05-14) — what Phase 1 uses by default
    "claude-sonnet-4-20250514": {
        "input": Decimal("3.00"),
        "output": Decimal("15.00"),
        "cache_write": Decimal("3.75"),
        "cache_read": Decimal("0.30"),
    },
    # Haiku 4.5 — cheaper fallback if cost becomes an issue
    "claude-haiku-4-5-20251001": {
        "input": Decimal("1.00"),
        "output": Decimal("5.00"),
        "cache_write": Decimal("1.25"),
        "cache_read": Decimal("0.10"),
    },
}

# Approximate £/$. Updated when material drift would break the soft cap.
# Current as of 2026-05-10: $1.27/£ → £1 ≈ $1.27 → £ = $ × 0.7874.
GBP_PER_USD = Decimal("0.7874")

DAILY_BUDGET_GBP = Decimal("0.50")
_TOKENS_PER_MILLION = Decimal("1000000")


def usage_cost_usd(usage: Usage) -> Decimal:
    """Return the USD cost of one :class:`Usage`."""
    pricing = MODEL_PRICING.get(usage.model)
    if pricing is None:
        raise UnknownModelError(
            f"no pricing for model {usage.model!r}; add it to MODEL_PRICING"
        )
    return (
        Decimal(usage.input_tokens) * pricing["input"]
        + Decimal(usage.output_tokens) * pricing["output"]
        + Decimal(usage.cache_creation_tokens) * pricing["cache_write"]
        + Decimal(usage.cache_read_tokens) * pricing["cache_read"]
    ) / _TOKENS_PER_MILLION


def usage_cost_gbp(usage: Usage) -> Decimal:
    """Return the GBP cost of one :class:`Usage` (USD × fixed FX rate)."""
    return usage_cost_usd(usage) * GBP_PER_USD


def log_usage(
    session: AsyncSession,
    *,
    feature: str,
    usage: Usage,
    org_id: str | None = None,
) -> LlmUsage:
    """Insert an :class:`LlmUsage` row and return it.

    Caller is responsible for committing the session — this lets callers
    batch usage logging into the same transaction as their feature work.
    """
    row = LlmUsage(
        feature=feature,
        org_id=org_id,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_creation_tokens=usage.cache_creation_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        model=usage.model,
    )
    session.add(row)
    return row


def _today_window_utc(on_date: date | None = None) -> tuple[datetime, datetime]:
    """Return naive UTC ``[start, end)`` datetimes for the given date.

    ``LlmUsage.created_at`` is ``TIMESTAMP WITHOUT TIME ZONE`` and rows are
    written with ``datetime.utcnow`` (also naive). asyncpg refuses to compare
    a naive column against TZ-aware bounds, so the window must be naive too.
    """
    target = on_date or datetime.now(timezone.utc).date()
    start = datetime.combine(target, time.min)
    end = start.replace(hour=23, minute=59, second=59, microsecond=999_999)
    return start, end


async def daily_cost_gbp_for_org(
    session: AsyncSession,
    *,
    org_id: str,
    on_date: date | None = None,
) -> Decimal:
    """Sum today's GBP cost for the given org. Unknown models are skipped."""
    start, end = _today_window_utc(on_date)
    result = await session.execute(
        select(LlmUsage).where(
            LlmUsage.org_id == org_id,
            LlmUsage.created_at >= start,
            LlmUsage.created_at <= end,
        )
    )
    total = Decimal("0")
    for (row,) in result.all():
        # Server defaults set these to 0 on insert; coerce None defensively in
        # case we're operating on a row that hasn't been flushed.
        u = Usage(
            input_tokens=row.input_tokens or 0,
            output_tokens=row.output_tokens or 0,
            cache_creation_tokens=row.cache_creation_tokens or 0,
            cache_read_tokens=row.cache_read_tokens or 0,
            model=row.model,
        )
        try:
            total += usage_cost_gbp(u)
        except UnknownModelError:
            continue
    return total


async def is_within_daily_budget(
    session: AsyncSession,
    *,
    org_id: str,
    limit_gbp: Decimal = DAILY_BUDGET_GBP,
    on_date: date | None = None,
) -> bool:
    """True if the org is under the daily GBP cost cap."""
    cost = await daily_cost_gbp_for_org(session, org_id=org_id, on_date=on_date)
    return cost < limit_gbp


__all__ = [
    "DAILY_BUDGET_GBP",
    "GBP_PER_USD",
    "MODEL_PRICING",
    "UnknownModelError",
    "daily_cost_gbp_for_org",
    "is_within_daily_budget",
    "log_usage",
    "usage_cost_gbp",
    "usage_cost_usd",
]
