"""Tests for the Celery task that runs Open Org profile generation.

The task is invoked by Celery so the route returns 202 quickly. It:
  1. flips ``generation_status`` to ``generating``
  2. calls the core generator
  3. writes markdown + JSON + status ``ready`` on success
  4. logs LLM usage
  5. emails a claim link to the owner
On failure it records ``status=failed`` with the error message. Tests run the
underlying async function (``_run_generation``) directly so they're hermetic.
"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest

from llmstxt_core.llm import Usage
from llmstxt_core.open_org.generator import GenerationResult, ProfileGenerationError


@pytest.fixture
def session_maker_factory():
    """Build a fake session_maker that returns a context manager wrapping an AsyncMock session."""

    def _factory(session: mock.AsyncMock):
        manager = mock.MagicMock()
        ctx = mock.AsyncMock()
        ctx.__aenter__.return_value = session
        ctx.__aexit__.return_value = False
        manager.return_value = ctx
        return manager

    return _factory


def _profile_row(profile_id: uuid.UUID, org_id: str = "GB-CHC-1234567"):
    from llmstxt_api.open_org_models import OrgProfile

    return OrgProfile(id=profile_id, org_id=org_id, generation_status="pending")


def _query_returning(*rows):
    """Sequence of execute() return values, each unwrapping to one row."""
    return [mock.MagicMock(scalar_one_or_none=mock.MagicMock(return_value=r)) for r in rows]


@pytest.mark.asyncio
async def test_run_generation_happy_path_writes_ready_and_emails(session_maker_factory):
    from llmstxt_api.tasks import open_org_generate as task_mod

    profile_id = uuid.uuid4()
    row = _profile_row(profile_id)

    session = mock.AsyncMock()
    # execute() called twice: first to fetch the row, second by the LlmUsage write.
    # We're forgiving here — just return the row every time.
    session.execute.return_value = _query_returning(row, row)[0]
    session_maker = session_maker_factory(session)

    fake_result = GenerationResult(
        org_id="GB-CHC-1234567",
        markdown="---\nschema_version: open-org/v0.1\n---\n",
        json_payload={"schema_version": "open-org/v0.1", "identity": {"name": "X"}},
        flagged_themes=[],
        total_usage=Usage(input_tokens=100, output_tokens=50),
    )

    fake_generator = mock.AsyncMock(return_value=fake_result)
    fake_email = mock.AsyncMock()

    await task_mod._run_generation(
        profile_id=profile_id,
        charity_number="1234567",
        owner_email="owner@example.com",
        session_maker=session_maker,
        generator=fake_generator,
        send_claim_email=fake_email,
    )

    fake_generator.assert_awaited_once()
    assert row.markdown_source == fake_result.markdown
    assert row.profile_json == fake_result.json_payload
    assert row.generation_status == "ready"
    assert row.generation_error is None

    fake_email.assert_awaited_once()
    email_kwargs = fake_email.await_args.kwargs
    assert email_kwargs["email"] == "owner@example.com"
    assert email_kwargs["org_id"] == "GB-CHC-1234567"


@pytest.mark.asyncio
async def test_run_generation_marks_failed_on_generator_error(session_maker_factory):
    from llmstxt_api.tasks import open_org_generate as task_mod

    profile_id = uuid.uuid4()
    row = _profile_row(profile_id)

    session = mock.AsyncMock()
    session.execute.return_value = _query_returning(row)[0]
    session_maker = session_maker_factory(session)

    fake_generator = mock.AsyncMock(
        side_effect=ProfileGenerationError("CC says no")
    )
    fake_email = mock.AsyncMock()

    await task_mod._run_generation(
        profile_id=profile_id,
        charity_number="9999999",
        owner_email="owner@example.com",
        session_maker=session_maker,
        generator=fake_generator,
        send_claim_email=fake_email,
    )

    assert row.generation_status == "failed"
    assert row.generation_error and "CC says no" in row.generation_error
    fake_email.assert_not_awaited()  # No claim email when generation failed.


@pytest.mark.asyncio
async def test_run_generation_truncates_long_error_messages(session_maker_factory):
    from llmstxt_api.tasks import open_org_generate as task_mod

    profile_id = uuid.uuid4()
    row = _profile_row(profile_id)
    session = mock.AsyncMock()
    session.execute.return_value = _query_returning(row)[0]
    session_maker = session_maker_factory(session)

    huge = "x" * 5000
    fake_generator = mock.AsyncMock(side_effect=RuntimeError(huge))
    fake_email = mock.AsyncMock()

    await task_mod._run_generation(
        profile_id=profile_id,
        charity_number="1234567",
        owner_email="o@example.com",
        session_maker=session_maker,
        generator=fake_generator,
        send_claim_email=fake_email,
    )

    assert row.generation_status == "failed"
    assert len(row.generation_error) <= 1000


@pytest.mark.asyncio
async def test_run_generation_logs_llm_usage(session_maker_factory):
    from llmstxt_api.models import LlmUsage
    from llmstxt_api.tasks import open_org_generate as task_mod

    profile_id = uuid.uuid4()
    row = _profile_row(profile_id)
    session = mock.AsyncMock()
    session.execute.return_value = _query_returning(row)[0]
    session_maker = session_maker_factory(session)

    fake_result = GenerationResult(
        org_id="GB-CHC-1234567",
        markdown="---\nschema_version: open-org/v0.1\n---\n",
        json_payload={"schema_version": "open-org/v0.1"},
        total_usage=Usage(
            input_tokens=123,
            output_tokens=45,
            cache_creation_tokens=10,
            cache_read_tokens=5,
            model="claude-sonnet-4-20250514",
        ),
    )
    fake_generator = mock.AsyncMock(return_value=fake_result)
    fake_email = mock.AsyncMock()

    await task_mod._run_generation(
        profile_id=profile_id,
        charity_number="1234567",
        owner_email="o@example.com",
        session_maker=session_maker,
        generator=fake_generator,
        send_claim_email=fake_email,
    )

    # session.add was called at least with a LlmUsage row.
    llm_calls = [
        c for c in session.add.call_args_list if isinstance(c.args[0], LlmUsage)
    ]
    assert llm_calls, "LlmUsage row must be persisted"
    usage_row = llm_calls[0].args[0]
    assert usage_row.feature == "profile_generator"
    assert usage_row.org_id == "GB-CHC-1234567"
    assert usage_row.input_tokens == 123
    assert usage_row.output_tokens == 45


@pytest.mark.asyncio
async def test_run_generation_writes_stage_transitions(session_maker_factory):
    """Verifies the task populates generation_stage/_message/_started/_finished/_payload."""
    from llmstxt_api.tasks import open_org_generate as task_mod

    profile_id = uuid.uuid4()
    row = _profile_row(profile_id)

    session = mock.AsyncMock()
    session.execute.return_value = _query_returning(row)[0]
    session_maker = session_maker_factory(session)

    fake_result = GenerationResult(
        org_id='GB-CHC-1234567',
        markdown="---\nidentity:\n  name: X\n---\n",
        json_payload={
            'identity': {'name': 'X'},
            'mission': {
                'themes': ['t1', 't2', 't3', 't4'],
                'programmes': [{'name': 'p1'}, {'name': 'p2'}],
                'summary': 'We do good.',
            },
        },
        total_usage=Usage(
            input_tokens=10,
            output_tokens=5,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            model='claude-sonnet-4-20250514',
        ),
    )
    fake_generator = mock.AsyncMock(return_value=fake_result)

    await task_mod._run_generation(
        profile_id=profile_id,
        charity_number='1234567',
        owner_email='o@example.com',
        session_maker=session_maker,
        generator=fake_generator,
        send_claim_email=mock.AsyncMock(),
    )

    # Generation stage progressed to done.
    assert row.generation_status == 'ready'
    assert row.generation_stage == 'done'
    assert row.generation_message
    assert row.generation_started_at is not None
    assert row.generation_finished_at is not None
    # Payload carries derived counts for the done summary display.
    assert row.generation_payload is not None
    assert row.generation_payload['programmes_count'] == 2
    assert row.generation_payload['themes_count'] == 4
    assert row.generation_payload['has_summary'] is True


@pytest.mark.asyncio
async def test_run_generation_writes_error_stage_on_failure(session_maker_factory):
    from llmstxt_api.tasks import open_org_generate as task_mod

    profile_id = uuid.uuid4()
    row = _profile_row(profile_id)

    session = mock.AsyncMock()
    session.execute.return_value = _query_returning(row)[0]
    session_maker = session_maker_factory(session)

    async def boom(**kwargs):
        raise RuntimeError('kaboom')

    await task_mod._run_generation(
        profile_id=profile_id,
        charity_number='1234567',
        owner_email='o@example.com',
        session_maker=session_maker,
        generator=boom,
        send_claim_email=mock.AsyncMock(),
    )

    assert row.generation_status == 'failed'
    assert row.generation_stage == 'error'
    assert row.generation_finished_at is not None

