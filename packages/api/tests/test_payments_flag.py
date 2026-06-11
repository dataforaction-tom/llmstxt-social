"""Tests for the PAYMENTS_ENABLED kill switch.

When off (the default), the full pipeline (enrichment + assessment) is free:
/api/generate/free queues the full-pipeline task, and the one-time payment
endpoints refuse with 403. The Stripe webhook and subscriptions routes are
deliberately untouched — monitoring stays paid.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest import mock

import pytest


# --- Settings ---------------------------------------------------------------


def test_payments_disabled_by_default():
    from llmstxt_api.config import Settings

    assert Settings().payments_enabled is False


def test_payments_enabled_via_env(monkeypatch):
    from llmstxt_api.config import Settings

    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    assert Settings().payments_enabled is True
