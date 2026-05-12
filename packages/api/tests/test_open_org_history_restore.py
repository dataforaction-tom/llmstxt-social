"""Tests for the POST /api/open-org/{org_id}/history/{version_id}/restore route.

Restore is non-destructive: the past snapshot becomes the current markdown
source, and a NEW version row is appended pointing to it. Old versions
remain in place.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


VALID_PROFILE_MD = """---
schema_version: open-org/v0.1
identity:
  name: "Acme Aid"
  registration:
    charity_commission_ew: "1234567"
mission:
  themes:
    - older_people
---

## Mission

We help older people.
"""


@pytest.fixture
def app_with_admin_routes():
    from llmstxt_api.database import get_db
    from llmstxt_api.routes.open_org_admin import router
    from llmstxt_api.routes.open_org_auth import require_org_admin

    app = FastAPI()
    app.include_router(router)

    session = mock.AsyncMock()
    app.dependency_overrides[get_db] = lambda: session

    fake_admin = mock.MagicMock()
    fake_admin.user_id = uuid.uuid4()
    fake_admin.role = "owner"
    app.dependency_overrides[require_org_admin] = lambda: fake_admin

    app.state.mock_session = session
    app.state.fake_admin = fake_admin
    return app


def _execute_sequence(session, values):
    """Wire session.execute to return scalar_one_or_none from each value in order."""
    results = []
    for v in values:
        r = mock.MagicMock()
        r.scalar_one_or_none.return_value = v
        results.append(r)
    session.execute.side_effect = results


def test_restore_applies_snapshot_and_appends_new_version(app_with_admin_routes):
    from llmstxt_api.open_org_models import OrgProfile, OrgVersion

    profile = OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        markdown_source="(current markdown — different)",
        profile_json={"identity": {"name": "Acme Aid (current)"}},
        published=True,
    )
    version = OrgVersion(
        id=uuid.uuid4(),
        parent_kind="profile",
        parent_id=profile.id,
        markdown_snapshot=VALID_PROFILE_MD,
        created_at=datetime.utcnow(),
    )
    _execute_sequence(app_with_admin_routes.state.mock_session, [profile, version])

    task_mock = mock.MagicMock()
    task_mock.delay.return_value = mock.MagicMock(id="task-resubmit")
    with mock.patch(
        "llmstxt_api.routes.open_org_admin.submit_to_murmurations_task",
        task_mock,
    ):
        client = TestClient(app_with_admin_routes)
        response = client.post(
            f"/api/open-org/GB-CHC-1234567/history/{version.id}/restore"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["org_id"] == "GB-CHC-1234567"
    assert body["restored_from_version"] == str(version.id)
    assert body["new_version_id"] != str(version.id)  # a fresh row

    # Profile state was updated to the snapshot
    assert profile.markdown_source == VALID_PROFILE_MD
    assert profile.profile_json["identity"]["name"] == "Acme Aid"

    # A new version was added (db.add called with the new OrgVersion)
    add_calls = app_with_admin_routes.state.mock_session.add.call_args_list
    assert any(isinstance(call.args[0], OrgVersion) for call in add_calls)

    # Resubmit fired because the profile was published
    task_mock.delay.assert_called_once()


def test_restore_returns_404_when_profile_missing(app_with_admin_routes):
    _execute_sequence(app_with_admin_routes.state.mock_session, [None])

    client = TestClient(app_with_admin_routes)
    response = client.post(
        f"/api/open-org/GB-CHC-MISSING/history/{uuid.uuid4()}/restore"
    )
    assert response.status_code == 404


def test_restore_returns_404_when_version_missing(app_with_admin_routes):
    from llmstxt_api.open_org_models import OrgProfile

    profile = OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        profile_json={"identity": {"name": "X"}, "mission": {"themes": ["x"]}},
        published=False,
    )
    _execute_sequence(app_with_admin_routes.state.mock_session, [profile, None])

    client = TestClient(app_with_admin_routes)
    response = client.post(
        f"/api/open-org/GB-CHC-1234567/history/{uuid.uuid4()}/restore"
    )
    assert response.status_code == 404


def test_restore_rejects_invalid_snapshot_with_400(app_with_admin_routes):
    """If the snapshot fails today's schema (e.g. v0.2 tightened a constraint),
    restore returns 400 with the converter's structured errors rather than
    persisting bad data."""
    from llmstxt_api.open_org_models import OrgProfile, OrgVersion

    profile = OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        profile_json={"identity": {"name": "X"}, "mission": {"themes": ["x"]}},
        published=False,
    )
    # Snapshot is malformed — missing required mission.themes.
    bad_md = """---
schema_version: open-org/v0.1
identity:
  name: "Bad"
  registration:
    charity_commission_ew: "1234567"
mission: {}
---
"""
    version = OrgVersion(
        id=uuid.uuid4(),
        parent_kind="profile",
        parent_id=profile.id,
        markdown_snapshot=bad_md,
    )
    _execute_sequence(app_with_admin_routes.state.mock_session, [profile, version])

    client = TestClient(app_with_admin_routes)
    response = client.post(
        f"/api/open-org/GB-CHC-1234567/history/{version.id}/restore"
    )
    assert response.status_code == 400
    assert "errors" in response.json()["detail"]


def test_restore_skips_resubmit_when_unpublished(app_with_admin_routes):
    from llmstxt_api.open_org_models import OrgProfile, OrgVersion

    profile = OrgProfile(
        id=uuid.uuid4(),
        org_id="GB-CHC-1234567",
        markdown_source="(old)",
        profile_json={"identity": {"name": "X"}, "mission": {"themes": ["x"]}},
        published=False,
    )
    version = OrgVersion(
        id=uuid.uuid4(),
        parent_kind="profile",
        parent_id=profile.id,
        markdown_snapshot=VALID_PROFILE_MD,
    )
    _execute_sequence(app_with_admin_routes.state.mock_session, [profile, version])

    task_mock = mock.MagicMock()
    with mock.patch(
        "llmstxt_api.routes.open_org_admin.submit_to_murmurations_task",
        task_mock,
    ):
        client = TestClient(app_with_admin_routes)
        response = client.post(
            f"/api/open-org/GB-CHC-1234567/history/{version.id}/restore"
        )

    assert response.status_code == 200
    task_mock.delay.assert_not_called()
