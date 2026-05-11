"""Tests for POST /api/open-org/{org_id}/publish admin route.

Publishing flips ``OrgProfile.published`` to True and dispatches the
Murmurations submission Celery task. Admin-only (uses ``require_org_admin``).
"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest


def _profile(*, profile_json: dict | None = None, published: bool = False):
    from llmstxt_api.open_org_models import OrgProfile

    return OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        published=published,
        profile_json=profile_json
        or {
            "schema_version": "open-org/v0.1",
            "identity": {
                "name": "Acme Aid",
                "identifiers": {"org_id": "GB-CHC-1234567"},
            },
            "mission": {"themes": ["education"]},
        },
    )


async def test_publish_sets_published_and_queues_submission():
    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_admin import publish_profile

    profile = _profile()
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=profile)
    )

    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")
    task_mock = mock.MagicMock()
    task_mock.delay.return_value = mock.MagicMock(id="task-123")

    with mock.patch(
        "llmstxt_api.routes.open_org_admin.submit_to_murmurations_task",
        task_mock,
    ):
        response = await publish_profile("GB-CHC-1234567", db, admin)

    assert profile.published is True
    task_mock.delay.assert_called_once()
    kwargs = task_mock.delay.call_args.kwargs
    assert kwargs["profile_id"] == str(profile.id)

    assert response.org_id == "GB-CHC-1234567"
    assert response.published is True


async def test_publish_returns_404_when_profile_missing():
    from fastapi import HTTPException

    from llmstxt_api.open_org_models import OrgAdmin
    from llmstxt_api.routes.open_org_admin import publish_profile

    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=None)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-NONE", role="owner")

    with pytest.raises(HTTPException) as exc:
        await publish_profile("GB-CHC-NONE", db, admin)
    assert exc.value.status_code == 404


async def test_publish_rejects_empty_profile_with_400():
    """Can't publish a profile with no JSON body — would 404 from the public URL."""
    from fastapi import HTTPException

    from llmstxt_api.open_org_models import OrgAdmin, OrgProfile
    from llmstxt_api.routes.open_org_admin import publish_profile

    empty = OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        published=False,
        profile_json=None,
    )
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=empty)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")

    with pytest.raises(HTTPException) as exc:
        await publish_profile("GB-CHC-1234567", db, admin)
    assert exc.value.status_code == 400


async def test_put_profile_queues_resubmit_if_already_published():
    """Saving an already-published profile should re-submit to Murmurations
    so the index stays in sync with what's at the public URL."""
    from llmstxt_api.open_org_models import OrgAdmin, OrgProfile
    from llmstxt_api.routes.open_org_admin import (
        MarkdownPayload,
        put_profile_markdown,
    )

    profile = _profile(published=True)
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=profile)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")

    valid_md = (
        "---\n"
        "schema_version: open-org/v0.1\n"
        "identity:\n"
        "  name: Acme Aid\n"
        "  registration:\n"
        "    charity_commission_ew: '1234567'\n"
        "  identifiers:\n"
        "    org_id: GB-CHC-1234567\n"
        "mission:\n"
        "  themes:\n"
        "    - education\n"
        "---\n"
    )

    task_mock = mock.MagicMock()
    task_mock.delay.return_value = mock.MagicMock(id="task-resubmit")

    with mock.patch(
        "llmstxt_api.routes.open_org_admin.submit_to_murmurations_task",
        task_mock,
    ):
        await put_profile_markdown(
            "GB-CHC-1234567", MarkdownPayload(markdown=valid_md), db, admin
        )

    task_mock.delay.assert_called_once()


async def test_put_profile_does_not_queue_submit_if_unpublished():
    from llmstxt_api.open_org_models import OrgAdmin, OrgProfile
    from llmstxt_api.routes.open_org_admin import (
        MarkdownPayload,
        put_profile_markdown,
    )

    profile = _profile(published=False)
    db = mock.AsyncMock()
    db.execute.return_value = mock.MagicMock(
        scalar_one_or_none=mock.MagicMock(return_value=profile)
    )
    admin = OrgAdmin(user_id=uuid.uuid4(), org_id="GB-CHC-1234567", role="owner")

    valid_md = (
        "---\n"
        "schema_version: open-org/v0.1\n"
        "identity:\n"
        "  name: Acme Aid\n"
        "  registration:\n"
        "    charity_commission_ew: '1234567'\n"
        "  identifiers:\n"
        "    org_id: GB-CHC-1234567\n"
        "mission:\n"
        "  themes:\n"
        "    - education\n"
        "---\n"
    )

    task_mock = mock.MagicMock()
    with mock.patch(
        "llmstxt_api.routes.open_org_admin.submit_to_murmurations_task",
        task_mock,
    ):
        await put_profile_markdown(
            "GB-CHC-1234567", MarkdownPayload(markdown=valid_md), db, admin
        )

    task_mock.delay.assert_not_called()
