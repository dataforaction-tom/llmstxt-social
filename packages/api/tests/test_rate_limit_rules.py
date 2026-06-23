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


def test_generate_status_polling_is_not_rate_limited():
    """The live-generate status endpoint (#18) is polled every couple of
    seconds while a generation runs. It must NOT share the expensive generate
    POST's hourly budget — otherwise a single generation exhausts the limit in
    seconds and blocks both further polls and new generations."""
    from llmstxt_api.middleware.rate_limit import _rule_for

    assert _rule_for("/api/open-org/generate/GB-CHC-1110522/status") is None


def test_rate_limit_rejection_returns_429_not_500():
    """Raising HTTPException inside a BaseHTTPMiddleware does not reach
    FastAPI's exception handler — it surfaces as a 500. The middleware must
    return a proper 429 JSON response so clients get the retry contract."""
    import llmstxt_api.middleware.rate_limit as rl
    from llmstxt_api.middleware.rate_limit import RateLimitMiddleware
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    class _OverLimitRedis:
        def incr(self, _key):
            return 10_000  # always over any configured limit

        def expire(self, _key, _ttl):
            return None

    rl.redis_client = _OverLimitRedis()

    async def _ok(_request):
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[Route("/api/open-org/generate", _ok, methods=["POST"])]
    )
    app.add_middleware(RateLimitMiddleware)
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.post("/api/open-org/generate")
    assert resp.status_code == 429
    assert resp.json()["error"] == "Rate limit exceeded"
