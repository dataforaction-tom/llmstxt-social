"""Celery tasks for Open Org creator-session housekeeping.

Phase 1 ships one task: a daily sweep that deletes ``CreatorSession`` rows
whose ``expires_at`` is in the past. Routes already reject expired sessions
with 410, but without the sweep the table grows forever.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from llmstxt_api.config import settings
from llmstxt_api.open_org_models import CreatorSession
from llmstxt_api.tasks.celery import celery_app


log = logging.getLogger(__name__)


def _build_session_maker():
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _run_eviction(*, session_maker: Any) -> int:
    """Delete expired CreatorSession rows. Returns the count deleted."""
    async with session_maker() as session:
        result = await session.execute(
            delete(CreatorSession).where(CreatorSession.expires_at < datetime.utcnow())
        )
        await session.commit()
        return int(getattr(result, "rowcount", 0) or 0)


@celery_app.task(name="open_org_evict_expired_creator_sessions", bind=True)
def evict_expired_creator_sessions_task(self):
    """Daily beat job."""
    deleted = asyncio.run(_run_eviction(session_maker=_build_session_maker()))
    log.info("Evicted %d expired creator sessions", deleted)


__all__ = ["_run_eviction", "evict_expired_creator_sessions_task"]
