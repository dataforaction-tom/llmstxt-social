"""Celery tasks for Murmurations index integration.

Two tasks live here:

* :func:`submit_to_murmurations_task` — validate + submit a single profile to
  the Murmurations index. Dispatched from the publish route and from the PUT
  admin route when an already-published profile is saved.
* :func:`sync_external_org_cache_task` — daily beat job that pulls all nodes
  for our schema, upserts them into ``external_org_cache``, and deletes rows
  no longer in the index.

Both tasks split into an async ``_run_*`` core that takes injected
collaborators (so tests can run offline) and a thin Celery wrapper that wires
the production implementations.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Awaitable, Callable

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from llmstxt_api.config import settings
from llmstxt_api.open_org_models import ExternalOrgCache, OrgProfile
from llmstxt_api.tasks.celery import celery_app
from llmstxt_core.open_org.murmurations import (
    MURMURATIONS_SCHEMA_NAME,
    MurmurationsClient,
    MurmurationsError,
)


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Production collaborators
# ---------------------------------------------------------------------------


def _build_session_maker():
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _build_client() -> MurmurationsClient:
    return MurmurationsClient(
        index_url=settings.murmurations_index_url,
        library_url=settings.murmurations_library_url,
    )


# ---------------------------------------------------------------------------
# Submit task
# ---------------------------------------------------------------------------


async def _run_submission(
    *,
    profile_id: uuid.UUID,
    session_maker: Any,
    client: MurmurationsClient,
    frontend_base_url: str,
) -> None:
    """Validate + submit a profile to the Murmurations index.

    Status transitions: pending → validated → posted (happy path).
    Validation failure: → failed (and we don't submit).
    Transient (5xx) errors raise so Celery's retry logic owns them — the row
    stays at the previous status until a retry succeeds or finally fails.
    """
    async with session_maker() as session:
        profile = await _fetch_profile(session, profile_id)
        if profile is None:
            log.warning("submit task: profile %s not found", profile_id)
            return
        if not profile.published:
            log.info("submit task: profile %s unpublished, skipping", profile.org_id)
            return

        url = f"{frontend_base_url.rstrip('/')}/open-org/{profile.org_id}/murmurations.json"

        validation = await client.validate_profile(url)
        if not validation.valid:
            profile.murmurations_status = "failed"
            await session.commit()
            log.warning(
                "submit task: validation failed for %s — %s",
                profile.org_id,
                "; ".join(validation.errors),
            )
            return
        profile.murmurations_status = "validated"
        await session.commit()

        result = await client.submit_node(url)
        profile.murmurations_node_id = result.node_id
        # Index may return ``posted``, ``received``, or an error status; we
        # store whatever it says so the operator can see edge cases.
        profile.murmurations_status = (
            "posted" if result.status == "posted" else result.status
        )
        await session.commit()


async def _fetch_profile(session: AsyncSession, profile_id: uuid.UUID) -> OrgProfile | None:
    result = await session.execute(
        select(OrgProfile).where(OrgProfile.id == profile_id)
    )
    return result.scalar_one_or_none()


@celery_app.task(
    name="open_org_submit_to_murmurations",
    bind=True,
    autoretry_for=(MurmurationsError,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
)
def submit_to_murmurations_task(self, *, profile_id: str):
    """Celery wrapper. Retries on transient :class:`MurmurationsError`."""
    asyncio.run(
        _run_submission(
            profile_id=uuid.UUID(profile_id),
            session_maker=_build_session_maker(),
            client=_build_client(),
            frontend_base_url=settings.frontend_url,
        )
    )


# ---------------------------------------------------------------------------
# Daily cache sync task
# ---------------------------------------------------------------------------


async def _run_cache_sync(
    *,
    session_maker: Any,
    client: MurmurationsClient,
    fetch_profile_body: Callable[[str], Awaitable[dict | None]],
) -> dict[str, int]:
    """Pull all nodes for our schema; upsert + delete missing rows.

    Returns counts ``{upserted, deleted}`` for observability.
    """
    nodes = await client.fetch_nodes_by_schema(MURMURATIONS_SCHEMA_NAME)

    seen_org_ids: set[str] = set()
    upserted = 0

    async with session_maker() as session:
        for node in nodes:
            profile_url = node.get("profile_url")
            if not profile_url:
                continue
            payload = await fetch_profile_body(profile_url)
            if not isinstance(payload, dict):
                continue
            org_id = payload.get("org_id_guide") or payload.get("org_id")
            if not isinstance(org_id, str) or not org_id:
                continue
            seen_org_ids.add(org_id)

            existing_result = await session.execute(
                select(ExternalOrgCache).where(ExternalOrgCache.org_id == org_id)
            )
            existing = existing_result.scalar_one_or_none()
            if existing is None:
                session.add(
                    ExternalOrgCache(
                        org_id=org_id,
                        source_url=profile_url,
                        profile_json=payload,
                    )
                )
            else:
                existing.source_url = profile_url
                existing.profile_json = payload
            upserted += 1

        await session.commit()

        # Delete rows that have left the index. Restrict to rows we know came
        # from Murmurations — for Phase 1 the only producer is this task, so
        # any row missing from ``seen_org_ids`` is stale.
        delete_result = await session.execute(
            select(ExternalOrgCache).where(
                ExternalOrgCache.org_id.notin_(seen_org_ids or ["__never__"])
            )
        )
        stale = delete_result.scalars().all()
        deleted = 0
        for row in stale:
            await session.delete(row)
            deleted += 1
        await session.commit()

    return {"upserted": upserted, "deleted": deleted}


async def _default_fetch_profile_body(url: str) -> dict | None:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            response = await http.get(url)
    except Exception as exc:  # noqa: BLE001
        log.warning("cache sync: fetch failed for %s: %s", url, exc)
        return None
    if response.status_code != 200:
        return None
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        return None
    return body if isinstance(body, dict) else None


@celery_app.task(name="open_org_sync_external_cache", bind=True)
def sync_external_org_cache_task(self):
    """Daily beat job. Idempotent: upserts + deletes-missing in one pass."""
    asyncio.run(
        _run_cache_sync(
            session_maker=_build_session_maker(),
            client=_build_client(),
            fetch_profile_body=_default_fetch_profile_body,
        )
    )


# ---------------------------------------------------------------------------
# Node-delete task (dispatched from the unpublish admin route)
# ---------------------------------------------------------------------------


async def _run_node_delete(
    *,
    profile_id: uuid.UUID,
    session_maker: Any,
    client: MurmurationsClient,
) -> None:
    """Remove the Murmurations index node for ``profile_id``.

    No-op when the profile has no node_id on file (never submitted).
    5xx propagates so Celery's retry handles transient failures cleanly —
    the row's ``murmurations_node_id`` is left in place until success so
    the retry knows what to delete.
    """
    async with session_maker() as session:
        result = await session.execute(
            select(OrgProfile).where(OrgProfile.id == profile_id)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            log.warning("node-delete: profile %s not found", profile_id)
            return
        node_id = profile.murmurations_node_id
        if not node_id:
            log.info("node-delete: profile %s has no node_id, skipping", profile_id)
            return

        await client.delete_node(node_id)

        profile.murmurations_node_id = None
        profile.murmurations_status = "deleted"
        await session.commit()


@celery_app.task(
    name="open_org_delete_from_murmurations",
    bind=True,
    autoretry_for=(MurmurationsError,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
)
def delete_from_murmurations_task(self, *, profile_id: str):
    """Celery wrapper. Retries on transient :class:`MurmurationsError`."""
    asyncio.run(
        _run_node_delete(
            profile_id=uuid.UUID(profile_id),
            session_maker=_build_session_maker(),
            client=_build_client(),
        )
    )


# ---------------------------------------------------------------------------
# Weekly health-check task — re-validate published profiles
# ---------------------------------------------------------------------------


async def _run_health_check(
    *,
    session_maker: Any,
    client: MurmurationsClient,
    frontend_base_url: str,
) -> dict[str, int]:
    """Re-validate every published profile against the live Murmurations
    schema and flag drift.

    Catches the case where the upstream schema tightened, or a profile's
    derived JSON contains fields the index doesn't accept any more. The
    federated envelope is rebuilt on the fly via the public route, so we
    validate by the profile URL rather than re-uploading the JSON.

    Returns ``{checked, drifted, errored}`` for observability.
    """
    base = frontend_base_url.rstrip("/")
    checked = 0
    drifted = 0
    errored = 0

    async with session_maker() as session:
        result = await session.execute(
            select(OrgProfile).where(OrgProfile.published.is_(True))
        )
        profiles = result.scalars().all()

        for profile in profiles:
            checked += 1
            url = f"{base}/open-org/{profile.org_id}/murmurations.json"
            try:
                validation = await client.validate_profile(url)
            except MurmurationsError as exc:
                log.warning(
                    "health-check: transient error validating %s: %s",
                    profile.org_id,
                    exc,
                )
                errored += 1
                continue

            if not validation.get("valid"):
                profile.murmurations_status = "drift"
                drifted += 1
            elif profile.murmurations_status == "drift":
                # Recovered from a previous drift run.
                profile.murmurations_status = "validated"

        await session.commit()

    return {"checked": checked, "drifted": drifted, "errored": errored}


@celery_app.task(name="open_org_health_check_murmurations", bind=True)
def health_check_murmurations_task(self):
    """Celery wrapper. Returns the per-run counts so the result backend
    can surface them in beat logs."""
    return asyncio.run(
        _run_health_check(
            session_maker=_build_session_maker(),
            client=_build_client(),
            frontend_base_url=settings.frontend_url,
        )
    )


__all__ = [
    "_run_submission",
    "_run_cache_sync",
    "_run_node_delete",
    "_run_health_check",
    "delete_from_murmurations_task",
    "health_check_murmurations_task",
    "submit_to_murmurations_task",
    "sync_external_org_cache_task",
]
