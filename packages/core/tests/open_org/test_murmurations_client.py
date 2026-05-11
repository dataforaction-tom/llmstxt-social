"""Tests for the Murmurations index HTTP client.

The client wraps a small number of REST calls against the Murmurations index
(validate, submit, fetch nodes by schema, delete a node). All HTTP is mocked.
"""

from __future__ import annotations

import pytest

from llmstxt_core.open_org.murmurations import (
    MurmurationsClient,
    MurmurationsError,
    MURMURATIONS_SCHEMA_NAME,
)


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: dict | list | None = None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = str(payload)

    def json(self):
        return self._payload


def _client_returning(*, responses: list, capture: list | None = None):
    """Build an http_client_factory that yields prepared responses in order."""

    iterator = iter(responses)

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def request(self, method, url, *, json=None, params=None):
            if capture is not None:
                capture.append({"method": method, "url": url, "json": json, "params": params})
            return next(iterator)

        async def post(self, url, json=None):
            return await self.request("POST", url, json=json)

        async def get(self, url, params=None):
            return await self.request("GET", url, params=params)

        async def delete(self, url):
            return await self.request("DELETE", url)

    return _Client


async def test_validate_profile_returns_true_on_200():
    factory = _client_returning(
        responses=[_FakeResponse(status_code=200, payload={"status": "valid"})]
    )
    client = MurmurationsClient(
        index_url="https://test-index.murmurations.network/v2",
        library_url="https://library.murmurations.network/v2",
        http_client_factory=factory,
    )
    result = await client.validate_profile("https://openorg.example/p.json")
    assert result.valid is True


async def test_validate_profile_returns_false_with_errors_on_400():
    factory = _client_returning(
        responses=[
            _FakeResponse(
                status_code=400,
                payload={"errors": [{"detail": "name is required"}]},
            )
        ]
    )
    client = MurmurationsClient(
        index_url="https://test-index.murmurations.network/v2",
        library_url="https://library.murmurations.network/v2",
        http_client_factory=factory,
    )
    result = await client.validate_profile("https://openorg.example/p.json")
    assert result.valid is False
    assert any("name is required" in e for e in result.errors)


async def test_validate_profile_raises_on_5xx():
    factory = _client_returning(
        responses=[_FakeResponse(status_code=503, payload={"error": "unavailable"})]
    )
    client = MurmurationsClient(
        index_url="https://test-index.murmurations.network/v2",
        library_url="https://library.murmurations.network/v2",
        http_client_factory=factory,
    )
    with pytest.raises(MurmurationsError):
        await client.validate_profile("https://openorg.example/p.json")


async def test_submit_node_returns_node_id_on_success():
    factory = _client_returning(
        responses=[
            _FakeResponse(
                status_code=200,
                payload={
                    "data": {"node_id": "abc-123", "status": "posted"},
                },
            )
        ]
    )
    client = MurmurationsClient(
        index_url="https://test-index.murmurations.network/v2",
        library_url="https://library.murmurations.network/v2",
        http_client_factory=factory,
    )
    result = await client.submit_node("https://openorg.example/p.json")
    assert result.node_id == "abc-123"
    assert result.status == "posted"


async def test_submit_node_handles_response_status_other_than_posted():
    """The index can return ``received`` or ``validation_failed`` etc.; pass through."""
    factory = _client_returning(
        responses=[
            _FakeResponse(
                status_code=200,
                payload={"data": {"node_id": "abc", "status": "validation_failed"}},
            )
        ]
    )
    client = MurmurationsClient(
        index_url="https://test-index.murmurations.network/v2",
        library_url="https://library.murmurations.network/v2",
        http_client_factory=factory,
    )
    result = await client.submit_node("https://openorg.example/p.json")
    assert result.status == "validation_failed"


async def test_submit_node_raises_on_5xx_for_retry():
    factory = _client_returning(
        responses=[_FakeResponse(status_code=500)]
    )
    client = MurmurationsClient(
        index_url="https://test-index.murmurations.network/v2",
        library_url="https://library.murmurations.network/v2",
        http_client_factory=factory,
    )
    with pytest.raises(MurmurationsError):
        await client.submit_node("https://openorg.example/p.json")


async def test_fetch_nodes_by_schema_returns_data_array():
    factory = _client_returning(
        responses=[
            _FakeResponse(
                status_code=200,
                payload={
                    "data": [
                        {"profile_url": "https://a.example/p.json", "node_id": "n1"},
                        {"profile_url": "https://b.example/p.json", "node_id": "n2"},
                    ],
                    "meta": {"total_pages": 1},
                },
            )
        ]
    )
    client = MurmurationsClient(
        index_url="https://test-index.murmurations.network/v2",
        library_url="https://library.murmurations.network/v2",
        http_client_factory=factory,
    )
    nodes = await client.fetch_nodes_by_schema(MURMURATIONS_SCHEMA_NAME)
    assert len(nodes) == 2
    assert nodes[0]["node_id"] == "n1"


async def test_fetch_nodes_by_schema_passes_query_param():
    capture: list = []
    factory = _client_returning(
        responses=[
            _FakeResponse(
                status_code=200,
                payload={"data": [], "meta": {"total_pages": 1}},
            )
        ],
        capture=capture,
    )
    client = MurmurationsClient(
        index_url="https://test-index.murmurations.network/v2",
        library_url="https://library.murmurations.network/v2",
        http_client_factory=factory,
    )
    await client.fetch_nodes_by_schema(MURMURATIONS_SCHEMA_NAME)
    assert capture[0]["params"]["schema"] == MURMURATIONS_SCHEMA_NAME


async def test_delete_node_returns_silently_on_200():
    factory = _client_returning(
        responses=[_FakeResponse(status_code=200, payload={"status": "deleted"})]
    )
    client = MurmurationsClient(
        index_url="https://test-index.murmurations.network/v2",
        library_url="https://library.murmurations.network/v2",
        http_client_factory=factory,
    )
    # No exception, no return — fire and forget.
    await client.delete_node("abc-123")


async def test_delete_node_raises_on_5xx():
    factory = _client_returning(
        responses=[_FakeResponse(status_code=503)]
    )
    client = MurmurationsClient(
        index_url="https://test-index.murmurations.network/v2",
        library_url="https://library.murmurations.network/v2",
        http_client_factory=factory,
    )
    with pytest.raises(MurmurationsError):
        await client.delete_node("abc-123")
