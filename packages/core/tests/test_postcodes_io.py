"""Tests for the postcodes.io geolocation enricher.

postcodes.io is a free public API; tests inject a fake httpx client so they
stay offline and deterministic.
"""

from __future__ import annotations

import pytest

from llmstxt_core.enrichers.postcodes_io import (
    PostcodesIoError,
    lookup_geolocation,
)


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _client_factory(*, status_code: int, payload: dict | None = None):
    response = _FakeResponse(status_code=status_code, payload=payload)

    class _Client:
        def __init__(self, *args, **kwargs):
            self.last_url: str | None = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            self.last_url = url
            return response

    return _Client


async def test_returns_lat_lon_on_success():
    factory = _client_factory(
        status_code=200,
        payload={
            "status": 200,
            "result": {"latitude": 52.6074, "longitude": 1.7295},
        },
    )
    result = await lookup_geolocation("NR30 1QH", http_client_factory=factory)
    assert result == (52.6074, 1.7295)


async def test_uppercases_and_trims_postcode_in_url():
    factory = _client_factory(
        status_code=200,
        payload={"result": {"latitude": 1.0, "longitude": 2.0}},
    )
    # Wrap factory so we can inspect the constructed URL.
    holder = {}

    class _CaptureClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            holder["url"] = url
            return _FakeResponse(
                status_code=200,
                payload={"result": {"latitude": 1.0, "longitude": 2.0}},
            )

    await lookup_geolocation("  nr30 1qh  ", http_client_factory=_CaptureClient)
    assert "NR30%201QH" in holder["url"] or "NR30 1QH" in holder["url"]


async def test_returns_none_for_unknown_postcode():
    """postcodes.io returns 404 for unknown postcodes; we map to None."""
    factory = _client_factory(status_code=404)
    result = await lookup_geolocation("ZZ99 9ZZ", http_client_factory=factory)
    assert result is None


async def test_returns_none_for_empty_input_without_calling_api():
    """Empty/whitespace postcodes must not hit the network."""
    calls = []

    class _ShouldNotBeCalled:
        def __init__(self, *args, **kwargs):
            calls.append("init")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            calls.append("get")
            return _FakeResponse(status_code=200)

    assert await lookup_geolocation("", http_client_factory=_ShouldNotBeCalled) is None
    assert await lookup_geolocation("   ", http_client_factory=_ShouldNotBeCalled) is None
    assert await lookup_geolocation(None, http_client_factory=_ShouldNotBeCalled) is None
    assert calls == []


async def test_raises_on_5xx_so_caller_can_retry():
    """Transient upstream failures bubble up — the Celery task decides
    whether to retry."""
    factory = _client_factory(status_code=503)
    with pytest.raises(PostcodesIoError):
        await lookup_geolocation("SW1A 1AA", http_client_factory=factory)


async def test_returns_none_when_payload_is_missing_coordinates():
    """Defensive: malformed responses don't blow up the caller."""
    factory = _client_factory(
        status_code=200, payload={"result": {"district": "Westminster"}}
    )
    result = await lookup_geolocation("SW1A 1AA", http_client_factory=factory)
    assert result is None
