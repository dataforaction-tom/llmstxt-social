"""Rate limiting middleware using Redis."""

from datetime import date
from typing import Callable

from fastapi import HTTPException, Request, Response
from redis import Redis
from starlette.middleware.base import BaseHTTPMiddleware

from llmstxt_api.config import settings

# Redis client for rate limiting
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for free tier endpoints.

    Limits requests based on IP address.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limit before processing request."""

        # Only apply to /api/generate/free endpoint
        if not request.url.path.startswith("/api/generate/free"):
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Create rate limit key (per day)
        today = date.today().isoformat()
        rate_limit_key = f"rate_limit:free:{client_ip}:{today}"

        try:
            # Increment counter
            count = redis_client.incr(rate_limit_key)

            # Set expiry on first request (24 hours)
            if count == 1:
                redis_client.expire(rate_limit_key, 86400)

            # Check limit
            if count > settings.free_tier_daily_limit:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "message": f"Free tier allows {settings.free_tier_daily_limit} requests per day. Please upgrade to paid tier for unlimited access.",
                        "retry_after": "24 hours",
                    },
                )

            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(settings.free_tier_daily_limit)
            response.headers["X-RateLimit-Remaining"] = str(
                max(0, settings.free_tier_daily_limit - count)
            )
            response.headers["X-RateLimit-Reset"] = today

            return response

        except HTTPException:
            raise
        except Exception as e:
            # If Redis is down, allow request but log error
            print(f"Rate limit error: {e}")
            return await call_next(request)
