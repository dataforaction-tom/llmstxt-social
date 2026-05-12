"""Tests for strategy/idea publish + unpublish admin routes.

These mirror the profile publish/unpublish routes (see
``test_open_org_publish_route.py``), but don't trigger Murmurations
submission/deletion — strategies and ideas aren't individually indexed in
Phase 1. Counts in the federated envelope catch up via the daily sync
beat or the next profile save.

Admin-only via ``require_org_admin``. Both routes 404 on missing rows,
and publish 400s on an empty record_json body (parity with profile).
"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest


def _strategy(*, strategy_json: dict | None = None, published: bool = False):
    from llmstxt_api.open_org_models import OrgStrategy

    return OrgStrategy(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        slug="2025-2028",
        published=published,
        strategy_json=strategy_json
        or {
            "schema_version": "open-org-strategy/v0.1",
            "id": "2025-2028",
            "status": "active",
            "themes": ["education"],
        },
    )


def _idea(*, idea_json: dict | None = None, published: bool = False):
    from llmstxt_api.open_org_models import OrgIdea

    return OrgIdea(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        slug="literacy-pop-up",
        published=published,
        idea_json=idea_json
        or {
            "schema_version": "open-org-idea/v0.1",
            "id": "literacy-pop-up",
            "status": "seed",
            "themes": ["education"],
        },
    )


# --- strategy publish -------------------------------------------------------


async def test_publish_strategy_sets_published_true():
    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_admin import publish_strategy

    strategy = _strategy()
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=strategy)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")

    response = await publish_strategy("GB-CHC-1234567", "2025-2028", db, admin)

    assert strategy.published is True
    assert response.org_id == "GB-CHC-1234567"
    assert response.slug == "2025-2028"
    assert response.schema_kind == "strategy"
    assert response.published is True


async def test_publish_strategy_returns_404_when_missing():
    from fastapi import HTTPException

    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_admin import publish_strategy

    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=None)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")

    with pytest.raises(HTTPException) as exc:
        await publish_strategy("GB-CHC-1234567", "nope", db, admin)
    assert exc.value.status_code == 404


async def test_publish_strategy_rejects_empty_record_with_400():
    from fastapi import HTTPException

    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_admin import publish_strategy

    empty = _strategy(strategy_json=None)
    empty.strategy_json = None
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=empty)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")

    with pytest.raises(HTTPException) as exc:
        await publish_strategy("GB-CHC-1234567", "2025-2028", db, admin)
    assert exc.value.status_code == 400


# --- strategy unpublish -----------------------------------------------------


async def test_unpublish_strategy_sets_published_false():
    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_admin import unpublish_strategy

    strategy = _strategy(published=True)
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=strategy)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")

    response = await unpublish_strategy("GB-CHC-1234567", "2025-2028", db, admin)

    assert strategy.published is False
    assert response.published is False
    assert response.schema_kind == "strategy"


async def test_unpublish_strategy_returns_404_when_missing():
    from fastapi import HTTPException

    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_admin import unpublish_strategy

    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=None)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")

    with pytest.raises(HTTPException) as exc:
        await unpublish_strategy("GB-CHC-1234567", "nope", db, admin)
    assert exc.value.status_code == 404


# --- idea publish -----------------------------------------------------------


async def test_publish_idea_sets_published_true():
    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_admin import publish_idea

    idea = _idea()
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=idea)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")

    response = await publish_idea("GB-CHC-1234567", "literacy-pop-up", db, admin)

    assert idea.published is True
    assert response.org_id == "GB-CHC-1234567"
    assert response.slug == "literacy-pop-up"
    assert response.schema_kind == "idea"
    assert response.published is True


async def test_publish_idea_rejects_empty_record_with_400():
    from fastapi import HTTPException

    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_admin import publish_idea

    empty = _idea()
    empty.idea_json = None
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=empty)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")

    with pytest.raises(HTTPException) as exc:
        await publish_idea("GB-CHC-1234567", "literacy-pop-up", db, admin)
    assert exc.value.status_code == 400


# --- idea unpublish ---------------------------------------------------------


async def test_unpublish_idea_sets_published_false():
    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_admin import unpublish_idea

    idea = _idea(published=True)
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=idea)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")

    response = await unpublish_idea("GB-CHC-1234567", "literacy-pop-up", db, admin)

    assert idea.published is False
    assert response.published is False
    assert response.schema_kind == "idea"


async def test_unpublish_idea_returns_404_when_missing():
    from fastapi import HTTPException

    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_admin import unpublish_idea

    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=None)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")

    with pytest.raises(HTTPException) as exc:
        await unpublish_idea("GB-CHC-1234567", "nope", db, admin)
    assert exc.value.status_code == 404


# --- GET .md surfaces published flag ----------------------------------------


async def test_get_strategy_md_includes_published_flag():
    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_admin import get_strategy_markdown

    strategy = _strategy(published=True)
    strategy.markdown_source = "---\nschema_version: open-org-strategy/v0.1\n---\n"
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=strategy)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")

    response = await get_strategy_markdown(
        "GB-CHC-1234567", "2025-2028", db, admin
    )
    assert response.published is True
    assert response.schema_kind == "strategy"


async def test_get_idea_md_includes_published_flag():
    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_admin import get_idea_markdown

    idea = _idea(published=False)
    idea.markdown_source = "---\nschema_version: open-org-idea/v0.1\n---\n"
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=idea)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")

    response = await get_idea_markdown(
        "GB-CHC-1234567", "literacy-pop-up", db, admin
    )
    assert response.published is False
    assert response.schema_kind == "idea"
