"""Tests for the require_org_admin dependency and admin-grant helpers."""

import uuid
from unittest import mock

import pytest


# --- require_org_admin ------------------------------------------------------

@pytest.mark.asyncio
async def test_require_org_admin_returns_admin_when_grant_exists():
    from llmstxt_api.models import User
    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_auth import require_org_admin

    user = User(id=uuid.uuid4(), email="o@example.com")
    admin = OrgAdmin(user_id=user.id, org_id="GB-CHC-1234567", role="owner")

    session = mock.AsyncMock()
    result = mock.MagicMock()
    result.scalar_one_or_none.return_value = admin
    session.execute.return_value = result

    out = await require_org_admin(org_id="GB-CHC-1234567", user=user, db=session)
    assert out is admin


@pytest.mark.asyncio
async def test_require_org_admin_raises_403_when_no_grant():
    from fastapi import HTTPException

    from llmstxt_api.models import User
    from llmstxt_api.routes.open_org_auth import require_org_admin

    user = User(id=uuid.uuid4(), email="o@example.com")
    session = mock.AsyncMock()
    result = mock.MagicMock()
    result.scalar_one_or_none.return_value = None  # not an admin
    session.execute.return_value = result

    with pytest.raises(HTTPException) as excinfo:
        await require_org_admin(org_id="GB-CHC-9999", user=user, db=session)
    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_require_org_admin_isolates_admin_grants_per_org():
    """A user with admin on org A must not be granted admin on org B."""
    from fastapi import HTTPException

    from llmstxt_api.models import User
    from llmstxt_api.routes.open_org_auth import require_org_admin

    user = User(id=uuid.uuid4(), email="o@example.com")
    session = mock.AsyncMock()
    # Query for "GB-CHC-B" returns no grant
    result = mock.MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    with pytest.raises(HTTPException) as excinfo:
        await require_org_admin(org_id="GB-CHC-B", user=user, db=session)
    assert excinfo.value.status_code == 403


# --- grant_org_admin helper -------------------------------------------------

@pytest.mark.asyncio
async def test_grant_org_admin_creates_row():
    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_auth import grant_org_admin

    session = mock.AsyncMock()
    user_id = uuid.uuid4()

    row = await grant_org_admin(
        session, user_id=user_id, org_id="GB-CHC-1234567", role="owner"
    )

    assert isinstance(row, OrgAdmin)
    assert row.user_id == user_id
    assert row.org_id == "GB-CHC-1234567"
    assert row.role == "owner"
    session.add.assert_called_once_with(row)


@pytest.mark.asyncio
async def test_grant_org_admin_defaults_to_editor_role():
    from llmstxt_api.routes.open_org_auth import grant_org_admin

    session = mock.AsyncMock()
    row = await grant_org_admin(
        session, user_id=uuid.uuid4(), org_id="GB-CHC-X"
    )
    assert row.role == "editor"


@pytest.mark.asyncio
async def test_grant_org_admin_rejects_invalid_role():
    from llmstxt_api.routes.open_org_auth import grant_org_admin

    session = mock.AsyncMock()
    with pytest.raises(ValueError, match="role"):
        await grant_org_admin(
            session, user_id=uuid.uuid4(), org_id="GB-CHC-X", role="god_mode"
        )
