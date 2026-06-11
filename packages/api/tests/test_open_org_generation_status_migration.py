"""Smoke test: the new migration's columns are reachable from the ORM model."""

from __future__ import annotations


def test_orgprofile_has_generation_stage_columns():
    from llmstxt_api.open_org_models import OrgProfile

    cols = {col.name for col in OrgProfile.__table__.columns}
    assert {
        "generation_stage",
        "generation_message",
        "generation_payload",
        "generation_started_at",
        "generation_finished_at",
    }.issubset(cols)
