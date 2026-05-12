"""Tests for the rate-limit middleware's path dispatch.

We don't drive Redis here — that's an integration concern. These tests pin
the contract: which paths get rate-limited, with what bucket key prefix,
and what limit. Regression coverage against accidentally dropping a rule
when adding new ones.

See SECURITY-REVIEW.md H2 for why ``/api/auth/magic-link`` is gated.
"""

from __future__ import annotations


def test_magic_link_endpoint_is_rate_limited():
    """SECURITY-REVIEW.md H2: unauthenticated magic-link send must be capped
    per IP or the endpoint becomes an email-bomb tool."""
    from llmstxt_api.middleware.rate_limit import _rule_for

    rule = _rule_for("/api/auth/magic-link")
    assert rule is not None, "magic-link endpoint must have a rate-limit rule"
    prefix, limit, window, _bucket = rule
    assert prefix == "rate_limit:magic_link"
    assert window == 3600  # hourly
    assert limit > 0 and limit <= 20  # tight but not insane


def test_open_org_generate_is_rate_limited():
    from llmstxt_api.middleware.rate_limit import _rule_for

    rule = _rule_for("/api/open-org/generate")
    assert rule is not None
    prefix, limit, window, _ = rule
    assert prefix == "rate_limit:open_org_generate"
    assert window == 3600


def test_free_generate_is_rate_limited_daily():
    from llmstxt_api.middleware.rate_limit import _rule_for

    rule = _rule_for("/api/generate/free")
    assert rule is not None
    prefix, _, window, _ = rule
    assert prefix == "rate_limit:free"
    assert window == 86400


def test_unrelated_paths_are_not_rate_limited():
    """Sanity: paths outside the allowlist pass through without a rule."""
    from llmstxt_api.middleware.rate_limit import _rule_for

    assert _rule_for("/api/auth/verify") is None
    assert _rule_for("/api/auth/check") is None
    assert _rule_for("/api/open-org/discover") is None
    assert _rule_for("/health") is None
    assert _rule_for("/open-org/GB-CHC-1/profile.json") is None
