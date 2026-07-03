"""Lamplight CRM enricher — read outcome/impact data via Data Connect.

Lamplight is a UK service-delivery CRM where outcomes are core data
(WEMWBS, Outcome Stars, custom measurements tracked over time). The API
is gated behind paid add-on modules:

- **Publishing Module** — HTTP API with API key, can create
  profiles/relationships/referrals.
- **Data Connect** — read-only OData-like feed with generated credentials,
  used for Power BI/Excel exports.

This module builds a client abstraction that works against the Data
Connect OData feed pattern. The client is structured so that when a real
Lamplight instance is connected (with credentials) it works; for now it
works against a mockable HTTP interface.

Auth is via an ``X-Lamplight-Key: {api_key}`` header. OData feeds wrap
records in a top-level ``value`` array.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx


# Valid measurement types tracked by Lamplight outcomes.
MEASUREMENT_TYPES = frozenset(
    {"WEMWBS", "OUTCOME_STAR", "CORE", "PHQ6", "GAD7", "CUSTOM"}
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class LamplightOutcome:
    """A single outcome measurement for a person.

    Attributes:
        outcome_id: Unique outcome record id.
        person_id: The Lamplight profile/person id.
        measurement_type: One of WEMWBS, OUTCOME_STAR, CORE, PHQ6, GAD7, CUSTOM.
        value: The numeric measurement value.
        date: ISO date string (YYYY-MM-DD).
        notes: Free-text notes, may be ``None``.
    """

    outcome_id: str
    person_id: str
    measurement_type: str
    value: float
    date: str
    notes: str | None = None


@dataclass
class LamplightWorkRecord:
    """A single work/session record for a person.

    Attributes:
        record_id: Unique work record id.
        person_id: The Lamplight profile/person id.
        type: The work type (e.g. "1-2-1 session", "Group activity").
        date: ISO date string (YYYY-MM-DD).
        project: The project/programme name.
        notes: Free-text notes, may be ``None``.
    """

    record_id: str
    person_id: str
    type: str
    date: str
    project: str
    notes: str | None = None


@dataclass
class LamplightProfile:
    """A Lamplight profile/person with nested outcomes and work records.

    Attributes:
        profile_id: The Lamplight profile/person id.
        name: Display name.
        tags: List of tag labels.
        outcomes: Outcome measurements for this person.
        work_records: Work/session records for this person.
    """

    profile_id: str
    name: str
    tags: list[str]
    outcomes: list[LamplightOutcome] = field(default_factory=list)
    work_records: list[LamplightWorkRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LamplightClient:
    """Async client for reading data from Lamplight's Data Connect feed.

    The client is mockable: pass an ``http_client_factory`` returning any
    object with an async ``get(url, headers=...)`` method and async context
    manager protocol (``__aenter__`` / ``__aexit__``). By default a
    ``httpx.AsyncClient`` is used.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        http_client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._http_client_factory = http_client_factory or httpx.AsyncClient

    # -- internals --------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {"X-Lamplight-Key": self.api_key}

    async def _get(self, path: str) -> httpx.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        async with self._http_client_factory() as client:
            return await client.get(url, headers=self._headers())

    # -- public API -------------------------------------------------------

    async def get_profile(self, profile_id: str) -> LamplightProfile | None:
        """Fetch a single profile by id.

        Returns ``None`` on 404 or network error.
        """
        try:
            resp = await self._get(f"profiles/{profile_id}")
        except httpx.HTTPError:
            return None
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            return None
        data = resp.json()
        if not data.get("name"):
            return None
        return LamplightProfile(
            profile_id=str(data.get("id", profile_id)),
            name=data.get("name", ""),
            tags=list(data.get("tags", []) or []),
            outcomes=[],
            work_records=[],
        )

    async def get_outcomes(self, profile_id: str) -> list[LamplightOutcome]:
        """Fetch all outcome measurements for a profile.

        Returns an empty list on error or no outcomes.
        """
        try:
            resp = await self._get(f"profiles/{profile_id}/outcomes")
        except httpx.HTTPError:
            return []
        if resp.status_code >= 400:
            return []
        data = resp.json()
        records = data.get("value", []) if isinstance(data, dict) else data
        return [_parse_outcome(r) for r in records]

    async def get_work_records(self, profile_id: str) -> list[LamplightWorkRecord]:
        """Fetch all work/session records for a profile.

        Returns an empty list on error or no records.
        """
        try:
            resp = await self._get(f"profiles/{profile_id}/work_records")
        except httpx.HTTPError:
            return []
        if resp.status_code >= 400:
            return []
        data = resp.json()
        records = data.get("value", []) if isinstance(data, dict) else data
        return [_parse_work_record(r) for r in records]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_outcome(raw: dict) -> LamplightOutcome:
    return LamplightOutcome(
        outcome_id=str(raw.get("id", "")),
        person_id=str(raw.get("person_id", "")),
        measurement_type=str(raw.get("measurement_type", "CUSTOM")),
        value=raw.get("value", 0),
        date=str(raw.get("date", "")),
        notes=raw.get("notes"),
    )


def _parse_work_record(raw: dict) -> LamplightWorkRecord:
    return LamplightWorkRecord(
        record_id=str(raw.get("id", "")),
        person_id=str(raw.get("person_id", "")),
        type=str(raw.get("type", "")),
        date=str(raw.get("date", "")),
        project=str(raw.get("project", "")),
        notes=raw.get("notes"),
    )


# ---------------------------------------------------------------------------
# Evidence mapping
# ---------------------------------------------------------------------------


def outcomes_to_evidence(outcomes: list[LamplightOutcome]) -> list[dict]:
    """Map outcome measurements to ``evidence[]`` items.

    Groups outcomes by ``measurement_type``, then for each group calculates
    the baseline (first chronological value) → follow-up (last chronological
    value) change and the count of measurements (``n``).

    Each group becomes a single evidence item with ``evidence_type`` of
    ``outcome_data`` and an ``outcomes`` list containing one summary dict::

        {
            "metric": "WEMWBS",
            "baseline": 40,
            "follow_up": 56,
            "change": 16,
            "n": 2,
        }
    """
    if not outcomes:
        return []

    groups: dict[str, list[LamplightOutcome]] = defaultdict(list)
    for o in outcomes:
        groups[o.measurement_type].append(o)

    items: list[dict] = []
    for metric, group in groups.items():
        # Sort by date to get baseline → follow-up ordering.
        ordered = sorted(group, key=lambda o: o.date)
        baseline = ordered[0].value
        follow_up = ordered[-1].value
        change = follow_up - baseline
        items.append(
            {
                "evidence_id": f"lamplight-outcome-{metric.lower()}",
                "title": f"Lamplight outcome data: {metric}",
                "evidence_type": "outcome_data",
                "date": ordered[-1].date,
                "url": None,
                "themes": [],
                "outcomes": [
                    {
                        "metric": metric,
                        "baseline": baseline,
                        "follow_up": follow_up,
                        "change": change,
                        "n": len(ordered),
                    }
                ],
            }
        )
    return items


def work_records_to_evidence(work_records: list[LamplightWorkRecord]) -> list[dict]:
    """Map work records to ``evidence[]`` items as case studies.

    Each work record becomes one evidence item with ``evidence_type`` of
    ``case_study``.
    """
    items: list[dict] = []
    for r in work_records:
        title = f"{r.project}: {r.type}" if r.project else r.type
        items.append(
            {
                "evidence_id": f"lamplight-work-{r.record_id}",
                "title": title,
                "evidence_type": "case_study",
                "date": r.date,
                "url": None,
                "themes": [],
                "description": r.notes or "",
                "record_id": r.record_id,
            }
        )
    return items