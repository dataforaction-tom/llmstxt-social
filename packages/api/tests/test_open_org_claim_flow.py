"""Tests for the magic-link claim flow used by the profile generator.

When the generator finishes, the API sends the owner an email with a link
that does two things in one click: signs them in (existing magic-link flow)
and binds them as the owner of the freshly generated org profile.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest import mock

import pytest


# --- Model schema -----------------------------------------------------------


def test_magic_link_token_has_org_id_column():
    """``org_id`` is the only delta — no schema-wide rewrite needed."""
    from llmstxt_api.models import MagicLinkToken

    columns = MagicLinkToken.__table__.columns
    assert "org_id" in columns
    assert columns["org_id"].nullable is True


def test_org_profile_has_generation_status_columns():
    from llmstxt_api.models import OrgProfile

    columns = OrgProfile.__table__.columns
    assert "generation_status" in columns
    assert columns["generation_status"].nullable is False
    assert "generation_error" in columns
    assert columns["generation_error"].nullable is True


# --- create_claim_token helper ---------------------------------------------


@pytest.mark.asyncio
async def test_create_claim_token_writes_org_id_and_returns_raw_token():
    from llmstxt_api.models import MagicLinkToken
    from llmstxt_api.routes.open_org_auth import create_claim_token

    session = mock.AsyncMock()
    raw, row = await create_claim_token(
        session, email="owner@example.com", org_id="GB-CHC-1234567"
    )

    assert isinstance(raw, str)
    assert len(raw) >= 32  # secrets.token_urlsafe(32) is comfortably long
    assert isinstance(row, MagicLinkToken)
    assert row.email == "owner@example.com"
    assert row.org_id == "GB-CHC-1234567"
    assert row.token == raw
    assert row.expires_at > datetime.utcnow() + timedelta(hours=1)
    session.add.assert_called_once_with(row)


@pytest.mark.asyncio
async def test_create_claim_token_normalises_email_case():
    from llmstxt_api.routes.open_org_auth import create_claim_token

    session = mock.AsyncMock()
    _, row = await create_claim_token(
        session, email="  Owner@Example.COM ", org_id="GB-CHC-1"
    )
    assert row.email == "owner@example.com"


# --- verify_magic_link claim integration -----------------------------------
#
# These exercise the existing verify route with a token that carries an
# org_id. The route must (a) sign the user in (existing behaviour) and
# (b) call grant_org_admin so the user becomes owner of the org.


@pytest.mark.asyncio
async def test_verify_grants_org_admin_when_token_has_org_id():
    from llmstxt_api.models import MagicLinkToken, User
    from llmstxt_api.routes.auth import verify_magic_link
    from llmstxt_api.schemas import VerifyTokenRequest

    user_id = uuid.uuid4()
    user = User(id=user_id, email="owner@example.com", created_at=datetime.utcnow())
    magic_token = MagicLinkToken(
        id=uuid.uuid4(),
        email="owner@example.com",
        token="raw-token-abc",
        org_id="GB-CHC-1234567",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        used=False,
    )

    session = mock.AsyncMock()
    # First execute() returns the magic-link token; second returns the user.
    token_result = mock.MagicMock()
    token_result.scalar_one_or_none.return_value = magic_token
    user_result = mock.MagicMock()
    user_result.scalar_one_or_none.return_value = user
    session.execute.side_effect = [token_result, user_result]

    grant_mock = mock.AsyncMock()
    response = mock.MagicMock()

    with mock.patch(
        "llmstxt_api.routes.open_org_auth.grant_org_admin", grant_mock
    ):
        await verify_magic_link(
            VerifyTokenRequest(token="raw-token-abc"), response, session
        )

    grant_mock.assert_awaited_once()
    call = grant_mock.await_args
    assert call.kwargs["user_id"] == user_id
    assert call.kwargs["org_id"] == "GB-CHC-1234567"
    assert call.kwargs["role"] == "owner"


@pytest.mark.asyncio
async def test_verify_does_not_grant_when_token_has_no_org_id():
    """The existing login flow stays untouched — no spurious grants."""
    from llmstxt_api.models import MagicLinkToken, User
    from llmstxt_api.routes.auth import verify_magic_link
    from llmstxt_api.schemas import VerifyTokenRequest

    user = User(
        id=uuid.uuid4(), email="owner@example.com", created_at=datetime.utcnow()
    )
    magic_token = MagicLinkToken(
        id=uuid.uuid4(),
        email="owner@example.com",
        token="raw-token-xyz",
        org_id=None,
        expires_at=datetime.utcnow() + timedelta(hours=1),
        used=False,
    )

    session = mock.AsyncMock()
    token_result = mock.MagicMock()
    token_result.scalar_one_or_none.return_value = magic_token
    user_result = mock.MagicMock()
    user_result.scalar_one_or_none.return_value = user
    session.execute.side_effect = [token_result, user_result]

    grant_mock = mock.AsyncMock()
    response = mock.MagicMock()

    with mock.patch(
        "llmstxt_api.routes.open_org_auth.grant_org_admin", grant_mock
    ):
        await verify_magic_link(
            VerifyTokenRequest(token="raw-token-xyz"), response, session
        )

    grant_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_verify_is_idempotent_when_admin_grant_already_exists():
    """A user clicking the same claim link twice (or claiming after they've
    already been granted) must not error — second-time grant must be a no-op."""
    from sqlalchemy.exc import IntegrityError

    from llmstxt_api.models import MagicLinkToken, User
    from llmstxt_api.routes.auth import verify_magic_link
    from llmstxt_api.schemas import VerifyTokenRequest

    user = User(
        id=uuid.uuid4(), email="owner@example.com", created_at=datetime.utcnow()
    )
    magic_token = MagicLinkToken(
        id=uuid.uuid4(),
        email="owner@example.com",
        token="raw-token-dupe",
        org_id="GB-CHC-1234567",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        used=False,
    )

    session = mock.AsyncMock()
    token_result = mock.MagicMock()
    token_result.scalar_one_or_none.return_value = magic_token
    user_result = mock.MagicMock()
    user_result.scalar_one_or_none.return_value = user
    session.execute.side_effect = [token_result, user_result]

    grant_mock = mock.AsyncMock(
        side_effect=IntegrityError("INSERT", {}, Exception("duplicate"))
    )
    response = mock.MagicMock()

    with mock.patch(
        "llmstxt_api.routes.open_org_auth.grant_org_admin", grant_mock
    ):
        # Must not raise.
        await verify_magic_link(
            VerifyTokenRequest(token="raw-token-dupe"), response, session
        )


@pytest.mark.asyncio
async def test_verify_returns_claim_org_id_when_token_carries_one():
    """The verify response surfaces the token's org_id so the frontend can
    redirect a freshly-claimed owner straight into that org's editor."""
    from llmstxt_api.models import MagicLinkToken, User
    from llmstxt_api.routes.auth import verify_magic_link
    from llmstxt_api.schemas import VerifyTokenRequest

    user = User(
        id=uuid.uuid4(), email="owner@example.com", created_at=datetime.utcnow()
    )
    magic_token = MagicLinkToken(
        id=uuid.uuid4(),
        email="owner@example.com",
        token="raw-token-claim",
        org_id="GB-CHC-1234567",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        used=False,
    )

    session = mock.AsyncMock()
    token_result = mock.MagicMock()
    token_result.scalar_one_or_none.return_value = magic_token
    user_result = mock.MagicMock()
    user_result.scalar_one_or_none.return_value = user
    session.execute.side_effect = [token_result, user_result]

    grant_mock = mock.AsyncMock()
    response = mock.MagicMock()

    with mock.patch(
        "llmstxt_api.routes.open_org_auth.grant_org_admin", grant_mock
    ):
        result = await verify_magic_link(
            VerifyTokenRequest(token="raw-token-claim"), response, session
        )

    assert result.claim_org_id == "GB-CHC-1234567"


@pytest.mark.asyncio
async def test_verify_claim_org_id_is_none_for_plain_login():
    """A normal (non-claim) login leaves ``claim_org_id`` unset."""
    from llmstxt_api.models import MagicLinkToken, User
    from llmstxt_api.routes.auth import verify_magic_link
    from llmstxt_api.schemas import VerifyTokenRequest

    user = User(
        id=uuid.uuid4(), email="owner@example.com", created_at=datetime.utcnow()
    )
    magic_token = MagicLinkToken(
        id=uuid.uuid4(),
        email="owner@example.com",
        token="raw-token-plain",
        org_id=None,
        expires_at=datetime.utcnow() + timedelta(hours=1),
        used=False,
    )

    session = mock.AsyncMock()
    token_result = mock.MagicMock()
    token_result.scalar_one_or_none.return_value = magic_token
    user_result = mock.MagicMock()
    user_result.scalar_one_or_none.return_value = user
    session.execute.side_effect = [token_result, user_result]

    response = mock.MagicMock()
    result = await verify_magic_link(
        VerifyTokenRequest(token="raw-token-plain"), response, session
    )

    assert result.claim_org_id is None
