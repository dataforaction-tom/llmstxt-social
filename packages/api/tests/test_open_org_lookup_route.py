"""Tests for GET /api/open-org/lookup/{number}."""

from __future__ import annotations

from unittest import mock

import pytest


@pytest.mark.asyncio
async def test_lookup_returns_name_and_address():
    from llmstxt_api.routes.open_org_generate import lookup_charity
    from llmstxt_core.enrichers.charity_commission import CharityData

    cd = CharityData(
        name="The Trussell Trust",
        number="1110522",
        status="Registered",
        date_registered="2005-04-19",
        date_removed=None,
        latest_income=None,
        latest_expenditure=None,
        charitable_objects=None,
        activities=None,
        trustees=[],
        contact={"address": {"line1": "Unit 9", "line2": "Ashfield Trading Estate", "postcode": "SP2 7HL"}},
    )
    with mock.patch(
        "llmstxt_api.routes.open_org_generate.fetch_charity_data",
        new=mock.AsyncMock(return_value=cd),
    ):
        response = await lookup_charity(number="1110522")

    assert response.name == "The Trussell Trust"
    assert response.registered_address is not None
    assert "Ashfield" in response.registered_address


@pytest.mark.asyncio
async def test_lookup_handles_prejoined_string_address():
    """The real CC enricher stores ``contact['address']`` as a single
    comma-joined string, not a dict. The route must pass it through rather
    than treating it as a mapping."""
    from llmstxt_api.routes.open_org_generate import lookup_charity
    from llmstxt_core.enrichers.charity_commission import CharityData

    cd = CharityData(
        name="The Trussell Trust",
        number="1110522",
        status="Registered",
        date_registered="2005-04-19",
        date_removed=None,
        latest_income=None,
        latest_expenditure=None,
        charitable_objects=None,
        activities=None,
        trustees=[],
        contact={"address": "Unit 9, Ashfield Trading Estate, Salisbury, SP2 7HL"},
    )
    with mock.patch(
        "llmstxt_api.routes.open_org_generate.fetch_charity_data",
        new=mock.AsyncMock(return_value=cd),
    ):
        response = await lookup_charity(number="1110522")

    assert response.registered_address == "Unit 9, Ashfield Trading Estate, Salisbury, SP2 7HL"


@pytest.mark.asyncio
async def test_lookup_404_when_not_found():
    from fastapi import HTTPException
    from llmstxt_api.routes.open_org_generate import lookup_charity

    with mock.patch(
        "llmstxt_api.routes.open_org_generate.fetch_charity_data",
        new=mock.AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as exc:
            await lookup_charity(number="9999999")
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_lookup_rejects_invalid_format():
    from fastapi import HTTPException
    from llmstxt_api.routes.open_org_generate import lookup_charity

    with pytest.raises(HTTPException) as exc:
        await lookup_charity(number="abc")
    assert exc.value.status_code == 400
