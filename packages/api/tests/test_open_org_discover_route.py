"""Tests for the public GET /api/open-org/discover route.

The route unions OrgProfile (published) and ExternalOrgCache, applies coarse
JSONB filters, then re-filters in Python and paginates by cursor on (name,
org_id). We stub the DB so SQLAlchemy JSON path operators aren't exercised
here — those are best tested against a real Postgres in an integration suite.
"""

from __future__ import annotations

import json
import uuid
from unittest import mock

import pytest


def _local(*, org_id: str, name: str, themes: list[str] | None = None,
           area: str | None = None, area_code: str | None = None,
           geolocation: dict | None = None):
    from llmstxt_api.open_org_models import OrgProfile

    return OrgProfile(
        id=uuid.uuid4(),
        org_id=org_id,
        published=True,
        profile_json={
            "schema_version": "open-org/v0.1",
            "identity": {
                "name": name,
                "identifiers": {"org_id": org_id},
                "geography": {
                    **({"primary_area": area} if area else {}),
                    **({"primary_area_code": area_code} if area_code else {}),
                    **({"geolocation": geolocation} if geolocation else {}),
                },
            },
            "mission": {
                "themes": themes or ["education"],
                "summary": f"Summary for {name}",
            },
        },
    )


def _external(*, org_id: str, name: str, tags: list[str] | None = None,
              primary_area_code: str | None = None,
              geolocation: dict | None = None):
    from llmstxt_api.open_org_models import ExternalOrgCache

    return ExternalOrgCache(
        id=uuid.uuid4(),
        org_id=org_id,
        source_url=f"https://elsewhere.example/{org_id}",
        profile_json={
            "name": name,
            "tags": tags or ["food_access"],
            "org_id_guide": org_id,
            **({"primary_area_code": primary_area_code} if primary_area_code else {}),
            **({"geolocation": geolocation} if geolocation else {}),
            "open_org_profile_url": f"https://elsewhere.example/{org_id}/profile.json",
        },
    )


def _stub_db(*, local_rows: list, external_rows: list):
    """AsyncSession whose execute() returns local rows then external rows."""
    db = mock.AsyncMock()

    def _wrap(rows):
        return mock.MagicMock(
            scalars=mock.MagicMock(
                return_value=mock.MagicMock(all=mock.MagicMock(return_value=rows))
            )
        )

    db.execute.side_effect = [_wrap(local_rows), _wrap(external_rows)]
    return db


# ---------------------------------------------------------------------------
# Shape + ordering
# ---------------------------------------------------------------------------


async def test_unioned_results_are_returned_in_name_order():
    from llmstxt_api.routes.open_org_discovery import discover

    db = _stub_db(
        local_rows=[
            _local(org_id="GB-CHC-1", name="Zebra Foundation"),
            _local(org_id="GB-CHC-2", name="Aardvark Trust"),
        ],
        external_rows=[
            _external(org_id="GB-CHC-3", name="Magpie Collective"),
        ],
    )

    response = await discover(
        theme=None, area_code=None, q=None, cursor=None, limit=20, db=db
    )
    body = json.loads(response.body)
    names = [r["name"] for r in body["results"]]
    assert names == ["Aardvark Trust", "Magpie Collective", "Zebra Foundation"]


async def test_local_profile_wins_when_org_id_appears_in_both_tables():
    """We host the profile and trust our copy over a federated mirror."""
    from llmstxt_api.routes.open_org_discovery import discover

    db = _stub_db(
        local_rows=[
            _local(org_id="GB-CHC-1234567", name="Local Authoritative"),
        ],
        external_rows=[
            _external(org_id="GB-CHC-1234567", name="Federated Stale"),
        ],
    )

    response = await discover(
        theme=None, area_code=None, q=None, cursor=None, limit=20, db=db
    )
    body = json.loads(response.body)
    assert len(body["results"]) == 1
    assert body["results"][0]["name"] == "Local Authoritative"
    assert body["results"][0]["source"] == "local"


async def test_discovery_row_includes_canonical_profile_url():
    from llmstxt_api.routes.open_org_discovery import discover

    db = _stub_db(
        local_rows=[_local(org_id="GB-CHC-1", name="A")],
        external_rows=[_external(org_id="GB-CHC-2", name="B")],
    )

    response = await discover(
        theme=None, area_code=None, q=None, cursor=None, limit=20, db=db
    )
    body = json.loads(response.body)
    urls = {r["profile_url"] for r in body["results"]}
    assert "/open-org/GB-CHC-1/profile.json" in urls
    assert "https://elsewhere.example/GB-CHC-2/profile.json" in urls


async def test_results_label_source_local_or_federated():
    from llmstxt_api.routes.open_org_discovery import discover

    db = _stub_db(
        local_rows=[_local(org_id="GB-CHC-1", name="Local Org")],
        external_rows=[_external(org_id="GB-CHC-2", name="Federated Org")],
    )

    body = json.loads(
        (await discover(
            theme=None, area_code=None, q=None, cursor=None, limit=20, db=db
        )).body
    )
    by_name = {r["name"]: r for r in body["results"]}
    assert by_name["Local Org"]["source"] == "local"
    assert by_name["Federated Org"]["source"] == "federated"


# ---------------------------------------------------------------------------
# Filters (Python-side fallback — JSONB filter exercised in integration tests)
# ---------------------------------------------------------------------------


async def test_theme_filter_excludes_orgs_without_the_theme():
    from llmstxt_api.routes.open_org_discovery import discover

    db = _stub_db(
        local_rows=[
            _local(org_id="GB-CHC-1", name="Education Org", themes=["education"]),
            _local(org_id="GB-CHC-2", name="Health Org", themes=["health"]),
        ],
        external_rows=[],
    )

    body = json.loads(
        (await discover(
            theme="education", area_code=None, q=None, cursor=None, limit=20, db=db
        )).body
    )
    names = [r["name"] for r in body["results"]]
    assert names == ["Education Org"]


async def test_area_code_filter():
    from llmstxt_api.routes.open_org_discovery import discover

    db = _stub_db(
        local_rows=[
            _local(org_id="GB-CHC-1", name="Norfolk", area_code="E07000145"),
            _local(org_id="GB-CHC-2", name="London", area_code="E09000033"),
        ],
        external_rows=[],
    )

    body = json.loads(
        (await discover(
            theme=None, area_code="E07000145", q=None, cursor=None, limit=20, db=db
        )).body
    )
    assert [r["name"] for r in body["results"]] == ["Norfolk"]


async def test_free_text_search_matches_name_or_area():
    from llmstxt_api.routes.open_org_discovery import discover

    db = _stub_db(
        local_rows=[
            _local(
                org_id="GB-CHC-1",
                name="Riverside Community Trust",
                area="Great Yarmouth",
            ),
            _local(
                org_id="GB-CHC-2",
                name="Hilltop Foundation",
                area="Birmingham",
            ),
        ],
        external_rows=[],
    )

    body = json.loads(
        (await discover(
            theme=None, area_code=None, q="yarmouth", cursor=None, limit=20, db=db
        )).body
    )
    assert [r["name"] for r in body["results"]] == ["Riverside Community Trust"]


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


async def test_pagination_returns_cursor_when_more_rows_exist():
    from llmstxt_api.routes.open_org_discovery import discover

    db = _stub_db(
        local_rows=[
            _local(org_id=f"GB-CHC-{i}", name=f"Org {i:02d}") for i in range(1, 6)
        ],
        external_rows=[],
    )

    body = json.loads(
        (await discover(
            theme=None, area_code=None, q=None, cursor=None, limit=3, db=db
        )).body
    )
    assert len(body["results"]) == 3
    assert body["next_cursor"] is not None


async def test_pagination_omits_cursor_on_final_page():
    from llmstxt_api.routes.open_org_discovery import discover

    db = _stub_db(
        local_rows=[
            _local(org_id=f"GB-CHC-{i}", name=f"Org {i}") for i in range(1, 4)
        ],
        external_rows=[],
    )

    body = json.loads(
        (await discover(
            theme=None, area_code=None, q=None, cursor=None, limit=10, db=db
        )).body
    )
    assert body["next_cursor"] is None


async def test_pagination_cursor_resumes_after_last_row():
    from llmstxt_api.routes.open_org_discovery import discover

    rows = [
        _local(org_id=f"GB-CHC-{i:02d}", name=f"Org {i:02d}") for i in range(1, 6)
    ]
    db1 = _stub_db(local_rows=rows, external_rows=[])

    page1 = json.loads(
        (await discover(
            theme=None, area_code=None, q=None, cursor=None, limit=2, db=db1
        )).body
    )
    assert [r["name"] for r in page1["results"]] == ["Org 01", "Org 02"]
    cursor = page1["next_cursor"]
    assert cursor

    db2 = _stub_db(local_rows=rows, external_rows=[])
    page2 = json.loads(
        (await discover(
            theme=None, area_code=None, q=None, cursor=cursor, limit=2, db=db2
        )).body
    )
    assert [r["name"] for r in page2["results"]] == ["Org 03", "Org 04"]


async def test_malformed_cursor_returns_first_page_not_error():
    """A bad cursor (corrupted querystring) shouldn't break the feature."""
    from llmstxt_api.routes.open_org_discovery import discover

    db = _stub_db(
        local_rows=[_local(org_id="GB-CHC-1", name="A"), _local(org_id="GB-CHC-2", name="B")],
        external_rows=[],
    )

    body = json.loads(
        (await discover(
            theme=None, area_code=None, q=None, cursor="not-base64!", limit=10, db=db
        )).body
    )
    assert len(body["results"]) == 2
