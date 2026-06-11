"""Tests for GET /api/open-org/generate/{org_id}/status."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest import mock

import pytest


@pytest.mark.asyncio
async def test_status_returns_current_stage_for_known_org():
    from llmstxt_api.open_org_models import OrgProfile
    from llmstxt_api.routes.open_org_generate import generate_status

    row = mock.MagicMock(spec=OrgProfile)
    row.org_id = "GB-CHC-1234567"
    row.generation_status = "generating"
    row.generation_stage = "drafting"
    row.generation_message = "Drafting your profile…"
    row.generation_payload = None
    row.generation_started_at = datetime.utcnow() - timedelta(seconds=12)
    row.generation_finished_at = None

    db = mock.AsyncMock()
    fetched = mock.MagicMock()
    fetched.scalar_one_or_none.return_value = row
    db.execute = mock.AsyncMock(return_value=fetched)

    response = await generate_status(org_id="GB-CHC-1234567", db=db)

    assert response.status == "generating"
    assert response.stage == "drafting"
    assert response.message == "Drafting your profile…"
    assert response.elapsed_ms >= 12_000


@pytest.mark.asyncio
async def test_status_404_on_unknown_org():
    from fastapi import HTTPException
    from llmstxt_api.routes.open_org_generate import generate_status

    db = mock.AsyncMock()
    fetched = mock.MagicMock()
    fetched.scalar_one_or_none.return_value = None
    db.execute = mock.AsyncMock(return_value=fetched)

    with pytest.raises(HTTPException) as exc:
        await generate_status(org_id="GB-CHC-9999999", db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_status_returns_payload_on_done():
    from llmstxt_api.open_org_models import OrgProfile
    from llmstxt_api.routes.open_org_generate import generate_status

    row = mock.MagicMock(spec=OrgProfile)
    row.org_id = "GB-CHC-1"
    row.generation_status = "ready"
    row.generation_stage = "done"
    row.generation_message = "Draft ready."
    row.generation_payload = {"themes_count": 4, "programmes_count": 14, "has_summary": True}
    row.generation_started_at = datetime.utcnow() - timedelta(seconds=47)
    row.generation_finished_at = datetime.utcnow()

    db = mock.AsyncMock()
    fetched = mock.MagicMock()
    fetched.scalar_one_or_none.return_value = row
    db.execute = mock.AsyncMock(return_value=fetched)

    response = await generate_status(org_id="GB-CHC-1", db=db)

    assert response.status == "ready"
    assert response.payload == {"themes_count": 4, "programmes_count": 14, "has_summary": True}
    assert response.elapsed_ms >= 47_000
