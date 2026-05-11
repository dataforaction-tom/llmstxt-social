"""Tests for the daily external_org_cache sync task.

Pulls all nodes for our schema from the Murmurations index, upserts them into
``external_org_cache``, and deletes rows for orgs that have left the index.
"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest


def _external(org_id: str, profile_json: dict | None = None):
    from llmstxt_api.open_org_models import ExternalOrgCache

    return ExternalOrgCache(
        id=uuid.uuid4(),
        org_id=org_id,
        source_url=f"https://elsewhere.example/{org_id}",
        profile_json=profile_json or {"org_id_guide": org_id},
    )


def _session_maker_for(session):
    manager = mock.MagicMock()
    ctx = mock.AsyncMock()
    ctx.__aenter__.return_value = session
    ctx.__aexit__.return_value = False
    manager.return_value = ctx
    return manager


def _client_returning_nodes(nodes: list[dict]):
    client = mock.AsyncMock()
    client.fetch_nodes_by_schema = mock.AsyncMock(return_value=nodes)
    return client


class _SessionStub(mock.AsyncMock):
    """Async session whose execute() is configurable by call order."""

    def __init__(self):
        super().__init__()
        self._results: list = []
        self._added: list = []
        self._deleted: list = []
        self.execute = mock.AsyncMock(side_effect=self._next_result)
        self.add = mock.MagicMock(side_effect=self._added.append)
        self.delete = mock.AsyncMock(side_effect=self._record_delete)
        self.commit = mock.AsyncMock()

    def _next_result(self, *args, **kwargs):
        if not self._results:
            return mock.MagicMock(
                scalar_one_or_none=mock.MagicMock(return_value=None),
                scalars=mock.MagicMock(
                    return_value=mock.MagicMock(all=mock.MagicMock(return_value=[]))
                ),
            )
        return self._results.pop(0)

    async def _record_delete(self, row):
        self._deleted.append(row)


def _result_for_one(row):
    return mock.MagicMock(scalar_one_or_none=mock.MagicMock(return_value=row))


def _result_for_many(rows):
    return mock.MagicMock(
        scalars=mock.MagicMock(
            return_value=mock.MagicMock(all=mock.MagicMock(return_value=rows))
        )
    )


async def test_upserts_new_orgs_into_cache():
    from llmstxt_api.tasks import open_org_murmurations as task_mod

    nodes = [
        {"profile_url": "https://a.example/p.json", "node_id": "n1"},
        {"profile_url": "https://b.example/p.json", "node_id": "n2"},
    ]
    client = _client_returning_nodes(nodes)

    fetched = {
        "https://a.example/p.json": {
            "org_id_guide": "GB-CHC-1111111",
            "name": "A",
            "linked_schemas": ["open_org_profile-v0.1.0"],
        },
        "https://b.example/p.json": {
            "org_id_guide": "GB-CHC-2222222",
            "name": "B",
            "linked_schemas": ["open_org_profile-v0.1.0"],
        },
    }

    async def fetch_body(url):
        return fetched.get(url)

    session = _SessionStub()
    # For each node: select existing (None) → upsert. Then a final
    # select for stale rows returns []. That's len(nodes) + 1 results.
    session._results = [_result_for_one(None), _result_for_one(None), _result_for_many([])]

    counts = await task_mod._run_cache_sync(
        session_maker=_session_maker_for(session),
        client=client,
        fetch_profile_body=fetch_body,
    )

    assert counts == {"upserted": 2, "deleted": 0}
    assert len(session._added) == 2
    assert session._added[0].org_id == "GB-CHC-1111111"


async def test_updates_existing_org_in_place():
    from llmstxt_api.tasks import open_org_murmurations as task_mod

    existing = _external("GB-CHC-1111111", profile_json={"name": "Old"})
    nodes = [{"profile_url": "https://a.example/p.json", "node_id": "n1"}]
    client = _client_returning_nodes(nodes)

    async def fetch_body(url):
        return {"org_id_guide": "GB-CHC-1111111", "name": "New"}

    session = _SessionStub()
    session._results = [_result_for_one(existing), _result_for_many([])]

    counts = await task_mod._run_cache_sync(
        session_maker=_session_maker_for(session),
        client=client,
        fetch_profile_body=fetch_body,
    )

    assert counts["upserted"] == 1
    assert existing.profile_json["name"] == "New"
    assert session._added == []  # No new row.


async def test_deletes_orgs_no_longer_in_index():
    from llmstxt_api.tasks import open_org_murmurations as task_mod

    stale = _external("GB-CHC-9999999")
    nodes = []  # Index returns nothing — every cached row is stale.
    client = _client_returning_nodes(nodes)

    async def fetch_body(url):
        return None

    session = _SessionStub()
    session._results = [_result_for_many([stale])]

    counts = await task_mod._run_cache_sync(
        session_maker=_session_maker_for(session),
        client=client,
        fetch_profile_body=fetch_body,
    )

    assert counts == {"upserted": 0, "deleted": 1}
    assert session._deleted == [stale]


async def test_skips_nodes_without_org_id_guide():
    """A node missing org_id_guide can't be cached; skip it without erroring."""
    from llmstxt_api.tasks import open_org_murmurations as task_mod

    nodes = [{"profile_url": "https://a.example/p.json", "node_id": "n1"}]
    client = _client_returning_nodes(nodes)

    async def fetch_body(url):
        return {"name": "Anon"}  # No org_id_guide

    session = _SessionStub()
    session._results = [_result_for_many([])]  # Only the stale-row query.

    counts = await task_mod._run_cache_sync(
        session_maker=_session_maker_for(session),
        client=client,
        fetch_profile_body=fetch_body,
    )

    assert counts == {"upserted": 0, "deleted": 0}
    assert session._added == []


async def test_skips_nodes_whose_body_failed_to_fetch():
    from llmstxt_api.tasks import open_org_murmurations as task_mod

    nodes = [{"profile_url": "https://a.example/p.json", "node_id": "n1"}]
    client = _client_returning_nodes(nodes)

    async def fetch_body(url):
        return None  # Simulated fetch failure.

    session = _SessionStub()
    session._results = [_result_for_many([])]

    counts = await task_mod._run_cache_sync(
        session_maker=_session_maker_for(session),
        client=client,
        fetch_profile_body=fetch_body,
    )

    assert counts == {"upserted": 0, "deleted": 0}
