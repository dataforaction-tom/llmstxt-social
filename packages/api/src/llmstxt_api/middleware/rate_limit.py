"""Rate limiting middleware using Redis."""

import logging
from datetime import date, datetime, timezone
from typing import Callable

from fastapi import HTTPException, Request, Response
from redis import Redis
from starlette.middleware.base import BaseHTTPMiddleware

from llmstxt_api.config import settings


log = logging.getLogger(__name__)


# Redis client for rate limiting
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


# Path → (key prefix, limit, window seconds, bucket-format) so multiple
# endpoints can share the middleware without bloating the dispatch logic.
def _rule_for(path: str):
    if path.startswith("/api/generate/free"):
        return (
            "rate_limit:free",
            settings.free_tier_daily_limit,
            86400,
            date.today().isoformat(),
        )
    if path.startswith("/api/open-org/generate"):
        # Hourly bucket — each generation costs real Anthropic spend; per-day
        # is too coarse to deter abuse on an unauthenticated endpoint.
        return (
            "rate_limit:open_org_generate",
            settings.open_org_generate_hourly_limit,
            3600,
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H"),
        )
    if path.startswith("/api/auth/magic-link"):
        # Unauthenticated + triggers a real Resend email per call — needs
        # a tight per-IP cap or it becomes an email-bomb against arbitrary
        # addresses. See SECURITY-REVIEW.md H2.
        return (
            "rate_limit:magic_link",
            settings.magic_link_hourly_limit,
            3600,
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H"),
        )
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiting backed by Redis.

    Currently scopes ``/api/generate/free`` (daily) and
    ``/api/open-org/generate`` (hourly). New endpoints register by adding
    a branch to :func:`_rule_for`.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        rule = _rule_for(request.url.path)
        if rule is None:
            return await call_next(request)
        prefix, limit, window_seconds, bucket = rule

        client_ip = request.client.host if request.client else "unknown"
        rate_limit_key = f"{prefix}:{client_ip}:{bucket}"

        try:
            count = redis_client.incr(rate_limit_key)
            if count == 1:
                redis_client.expire(rate_limit_key, window_seconds)

            if count > limit:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "message": (
                            f"This endpoint allows {limit} requests per "
                            f"{'hour' if window_seconds == 3600 else 'day'} per IP."
                        ),
                        "retry_after_seconds": window_seconds,
                    },
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
            response.headers["X-RateLimit-Reset"] = bucket
            return response

        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            # Fail-open if Redis is unreachable: a brief Redis outage shouldn't
            # take the whole API down. Logged at error level so it lands in a
            # log aggregator instead of being swallowed by container stdout —
            # see SECURITY-REVIEW.md M4.
            log.error("rate_limit middleware: %s", exc)
            return await call_next(request)
