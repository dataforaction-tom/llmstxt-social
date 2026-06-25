"""Tests for the strategy/idea chat creator HTTP routes.

Four endpoints: create session, stream a message, finalize, get session.
All gated by org-admin auth and bounded by the per-org daily LLM budget.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock

import pytest


def _admin_for(org_id: str = "GB-CHC-1234567"):
    from llmstxt_api.open_org_models import OrgAdmin

    return OrgAdmin(user_id=uuid.uuid4(), org_id=org_id, role="owner")


def _session(*, kind: str = "strategy", org_id: str = "GB-CHC-1234567"):
    from llmstxt_api.open_org_models import CreatorSession

    now = datetime.utcnow()
    return CreatorSession(
        id=uuid.uuid4(),
        org_id=org_id,
        kind=kind,
        conversation_history=[],
        current_markdown=None,
        last_active_at=now,
        expires_at=now + timedelta(days=30),
    )


def _result(scalar):
    return mock.MagicMock(scalar_one_or_none=mock.MagicMock(return_value=scalar))


# ---------------------------------------------------------------------------
# Routing contract
# ---------------------------------------------------------------------------


def test_session_routes_carry_org_id_in_path():
    """``require_org_admin`` declares ``org_id`` with no default. If a route's
    path template omits ``{org_id}``, FastAPI binds it as a *required query*
    parameter instead — so the frontend's path-only calls 422 and the whole
    chat creator dies after session creation. Every session route must carry
    ``{org_id}`` in its path."""
    from llmstxt_api.routes.open_org_creator import router

    paths = {route.name: route.path for route in router.routes}
    assert "{org_id}" in paths["get_session"]
    assert "{org_id}" in paths["post_message"]
    assert "{org_id}" in paths["finalize_session"]


def test_get_session_route_does_not_collide_with_create_route():
    """POST /{org_id}/create/{kind} and GET /{org_id}/create/{session_id}
    share the same path *structure* (one path segment after ``create/``).
    FastAPI parameter names don't affect routing — ``{kind}`` and
    ``{session_id}`` both match any single segment — so the two routes are
    distinguished only by HTTP method. Verify they have disjoint method sets
    so a GET to the create path can't accidentally hit the POST handler and
    vice versa.
    """
    from llmstxt_api.routes.open_org_creator import router

    by_name = {route.name: route for route in router.routes}
    create = by_name["create_session"]
    get = by_name["get_session"]

    # Disjoint method sets — no ambiguity.
    assert "POST" in create.methods
    assert "GET" in get.methods
    assert "POST" not in get.methods
    assert "GET" not in create.methods


# ---------------------------------------------------------------------------
# POST /create/{kind}
# ---------------------------------------------------------------------------


async def test_create_session_creates_row_and_returns_id():
    from llmstxt_api.open_org_models import CreatorSession
    from llmstxt_api.routes.open_org_creator import create_session

    db = mock.AsyncMock()
    admin = _admin_for()
    with mock.patch(
        "llmstxt_api.routes.open_org_creator.is_within_daily_budget",
        new=mock.AsyncMock(return_value=True),
    ):
        response = await create_session(
            org_id="GB-CHC-1234567",
            kind="strategy",
            upload=None,
            db=db,
            admin=admin,
        )

    added = db.add.call_args.args[0]
    assert isinstance(added, CreatorSession)
    assert added.org_id == "GB-CHC-1234567"
    assert added.kind == "strategy"
    assert added.conversation_history == []
    assert response.kind == "strategy"
    assert response.session_id


async def test_create_session_rejects_invalid_kind():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_creator import create_session

    db = mock.AsyncMock()
    admin = _admin_for()
    with pytest.raises(HTTPException) as exc:
        await create_session(
            org_id="GB-CHC-1234567",
            kind="strategey",  # typo
            upload=None,
            db=db,
            admin=admin,
        )
    assert exc.value.status_code == 400


async def test_create_session_returns_429_when_over_daily_budget():
    """The £0.50/org/day cap applies at session creation too — otherwise an
    attacker could bypass by always opening fresh sessions."""
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_creator import create_session

    db = mock.AsyncMock()
    admin = _admin_for()
    with mock.patch(
        "llmstxt_api.routes.open_org_creator.is_within_daily_budget",
        new=mock.AsyncMock(return_value=False),
    ):
        with pytest.raises(HTTPException) as exc:
            await create_session(
                org_id="GB-CHC-1234567",
                kind="strategy",
                upload=None,
                db=db,
                admin=admin,
            )
    assert exc.value.status_code == 429


async def test_create_session_seeds_history_from_upload_text():
    """When an uploaded document is supplied, its extracted text is added as a
    primer user message so the model has context before the first question."""
    from llmstxt_api.routes.open_org_creator import create_session

    db = mock.AsyncMock()
    admin = _admin_for()

    upload = mock.AsyncMock()
    upload.filename = "current_strategy.txt"
    upload.read = mock.AsyncMock(
        return_value=b"Our existing strategy is to support older people in Norfolk."
    )

    with mock.patch(
        "llmstxt_api.routes.open_org_creator.is_within_daily_budget",
        new=mock.AsyncMock(return_value=True),
    ):
        await create_session(
            org_id="GB-CHC-1234567",
            kind="strategy",
            upload=upload,
            db=db,
            admin=admin,
        )

    added = db.add.call_args.args[0]
    history = added.conversation_history
    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert "older people" in history[0]["content"]


# ---------------------------------------------------------------------------
# GET /create/{session_id}
# ---------------------------------------------------------------------------


async def test_get_session_returns_state_for_admin_of_owning_org():
    from llmstxt_api.routes.open_org_creator import get_session

    session_row = _session()
    session_row.conversation_history = [{"role": "user", "content": "Hi"}]
    session_row.current_markdown = "---\nschema_version: open-org-strategy/v0.1\n---\n"

    db = mock.AsyncMock()
    db.execute.return_value = _result(session_row)
    admin = _admin_for()

    detail = await get_session(session_id=session_row.id, db=db, admin=admin)
    assert detail.kind == "strategy"
    assert detail.current_markdown.startswith("---")
    assert detail.conversation_history == [{"role": "user", "content": "Hi"}]


async def test_get_session_returns_404_when_missing():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_creator import get_session

    db = mock.AsyncMock()
    db.execute.return_value = _result(None)
    admin = _admin_for()

    with pytest.raises(HTTPException) as exc:
        await get_session(session_id=uuid.uuid4(), db=db, admin=admin)
    assert exc.value.status_code == 404


async def test_get_session_returns_403_when_admin_org_mismatches():
    """An admin of org A must not be able to read a session for org B."""
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_creator import get_session

    session_row = _session(org_id="GB-CHC-OTHER")
    db = mock.AsyncMock()
    db.execute.return_value = _result(session_row)
    admin = _admin_for(org_id="GB-CHC-1234567")

    with pytest.raises(HTTPException) as exc:
        await get_session(session_id=session_row.id, db=db, admin=admin)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# POST /create/{session_id}/message
# ---------------------------------------------------------------------------


async def test_post_message_returns_429_when_over_budget():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_creator import post_message, MessagePayload

    session_row = _session()
    db = mock.AsyncMock()
    db.execute.return_value = _result(session_row)
    admin = _admin_for()

    with mock.patch(
        "llmstxt_api.routes.open_org_creator.is_within_daily_budget",
        new=mock.AsyncMock(return_value=False),
    ):
        with pytest.raises(HTTPException) as exc:
            await post_message(
                session_id=session_row.id,
                payload=MessagePayload(content="hi"),
                db=db,
                admin=admin,
            )
    assert exc.value.status_code == 429


async def test_post_message_returns_404_for_unknown_session():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_creator import post_message, MessagePayload

    db = mock.AsyncMock()
    db.execute.return_value = _result(None)
    admin = _admin_for()

    with mock.patch(
        "llmstxt_api.routes.open_org_creator.is_within_daily_budget",
        new=mock.AsyncMock(return_value=True),
    ):
        with pytest.raises(HTTPException) as exc:
            await post_message(
                session_id=uuid.uuid4(),
                payload=MessagePayload(content="hi"),
                db=db,
                admin=admin,
            )
    assert exc.value.status_code == 404


async def test_post_message_emits_sse_error_event_when_llm_stream_raises():
    """If the LLM stream throws mid-turn, the client must get a structured
    ``error`` SSE event — not a silent connection drop. Without a try/except
    around the threadpool iteration the exception escapes the async generator
    after 200 + headers have already been sent, so Starlette just closes the
    socket and the browser's EventSource sees an abrupt end with no clue why.
    """
    from llmstxt_api.routes import open_org_creator as mod
    from llmstxt_api.routes.open_org_creator import post_message, MessagePayload

    session_row = _session()
    db = mock.AsyncMock()
    db.execute.return_value = _result(session_row)
    admin = _admin_for()

    # Make iterate_in_threadpool return an async generator that yields a chunk
    # then raises — simulating a mid-stream LLM failure.
    async def _exploding():
        yield "partial delta"
        raise RuntimeError("upstream blew up")

    patches = [
        mock.patch(
            "llmstxt_api.routes.open_org_creator.is_within_daily_budget",
            new=mock.AsyncMock(return_value=True),
        ),
        mock.patch.object(mod, "_load_profile", new=mock.AsyncMock(return_value=None)),
        mock.patch.object(mod, "start_turn", return_value=mock.MagicMock()),
        mock.patch.object(mod, "iterate_in_threadpool", return_value=_exploding()),
    ]
    for p in patches:
        p.start()
    try:
        response = await post_message(
            session_id=session_row.id,
            payload=MessagePayload(content="hi"),
            db=db,
            admin=admin,
        )

        # Drain the SSE stream while mocks are still active.
        chunks: list[bytes] = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
    finally:
        for p in patches:
            p.stop()

    body = b"".join(chunks).decode("utf-8")

    # The partial delta was sent before the error.
    assert "event: delta" in body
    assert "partial delta" in body
    # An error event was emitted with a message.
    assert "event: error" in body
    assert "upstream blew up" in body


async def test_post_message_returns_410_for_expired_session():
    """Sessions are 30-day-TTL — past expiry they're gone."""
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_creator import post_message, MessagePayload

    session_row = _session()
    session_row.expires_at = datetime.utcnow() - timedelta(days=1)

    db = mock.AsyncMock()
    db.execute.return_value = _result(session_row)
    admin = _admin_for()

    with mock.patch(
        "llmstxt_api.routes.open_org_creator.is_within_daily_budget",
        new=mock.AsyncMock(return_value=True),
    ):
        with pytest.raises(HTTPException) as exc:
            await post_message(
                session_id=session_row.id,
                payload=MessagePayload(content="hi"),
                db=db,
                admin=admin,
            )
    assert exc.value.status_code == 410


# ---------------------------------------------------------------------------
# POST /create/{session_id}/finalize
# ---------------------------------------------------------------------------


_STRATEGY_MD = (
    "---\n"
    "schema_version: open-org-strategy/v0.1\n"
    "id: riverside-2030\n"
    "status: draft\n"
    "name: Riverside 2030\n"
    "themes:\n"
    "  - community_development\n"
    "---\n"
    "\n## Summary\n\nA plan for the next five years.\n"
)


async def test_finalize_creates_strategy_row_with_slug_from_frontmatter():
    from llmstxt_api.open_org_models import OrgStrategy
    from llmstxt_api.routes.open_org_creator import finalize_session

    session_row = _session()
    session_row.current_markdown = _STRATEGY_MD

    db = mock.AsyncMock()
    db.execute.return_value = _result(session_row)
    admin = _admin_for()

    response = await finalize_session(
        session_id=session_row.id, db=db, admin=admin
    )

    added = db.add.call_args.args[0]
    assert isinstance(added, OrgStrategy)
    assert added.org_id == "GB-CHC-1234567"
    assert added.slug == "riverside-2030"
    assert added.markdown_source == _STRATEGY_MD
    assert response.kind == "strategy"
    assert response.slug == "riverside-2030"


async def test_finalize_returns_400_when_markdown_missing():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_creator import finalize_session

    session_row = _session()
    session_row.current_markdown = None
    db = mock.AsyncMock()
    db.execute.return_value = _result(session_row)
    admin = _admin_for()

    with pytest.raises(HTTPException) as exc:
        await finalize_session(session_id=session_row.id, db=db, admin=admin)
    assert exc.value.status_code == 400


async def test_finalize_returns_400_when_markdown_invalid():
    from fastapi import HTTPException

    from llmstxt_api.routes.open_org_creator import finalize_session

    session_row = _session()
    session_row.current_markdown = (
        "---\nschema_version: open-org-strategy/v0.1\nid: x\n---\n"  # No themes; invalid.
    )

    db = mock.AsyncMock()
    db.execute.return_value = _result(session_row)
    admin = _admin_for()

    with pytest.raises(HTTPException) as exc:
        await finalize_session(session_id=session_row.id, db=db, admin=admin)
    assert exc.value.status_code == 400


async def test_finalize_returns_409_on_duplicate_slug():
    """A slug colliding with an existing record must surface as 409, not a 500.

    The LLM derives slugs from the title, so repeats are easy; without a guard
    the unique constraint raises IntegrityError -> unhandled 500.
    """
    from fastapi import HTTPException
    from sqlalchemy.exc import IntegrityError

    from llmstxt_api.routes.open_org_creator import finalize_session

    session_row = _session()
    session_row.current_markdown = _STRATEGY_MD
    db = mock.AsyncMock()
    db.execute.return_value = _result(session_row)
    db.commit.side_effect = IntegrityError("INSERT", {}, Exception("duplicate slug"))
    admin = _admin_for()

    with pytest.raises(HTTPException) as exc:
        await finalize_session(session_id=session_row.id, db=db, admin=admin)

    assert exc.value.status_code == 409
    db.rollback.assert_awaited()
