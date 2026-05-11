"""Tests for the additive extension of ``CharityData`` for Open Org generation.

The base enricher already covers ``name``, ``activities``, ``charitable_objects``,
trustees, and contact. Open Org Phase 1 needs four more fields the existing
parser doesn't extract: ``area_of_operation``, ``company_number``,
``latest_acc_fin_period_end_date``, and ``trustee_count``. All are optional;
absence of any of them must not break the existing call sites.
"""

from llmstxt_core.enrichers.charity_commission import (
    CharityData,
    _parse_api_response,
)


def test_charity_data_accepts_open_org_fields():
    data = CharityData(
        name="Test",
        number="1234567",
        status="Registered",
        date_registered=None,
        date_removed=None,
        latest_income=None,
        latest_expenditure=None,
        charitable_objects=None,
        activities=None,
        trustees=[],
        contact={},
        area_of_operation=["England", "Wales"],
        company_number="01234567",
        latest_acc_fin_period_end_date="2024-03-31",
        trustee_count=12,
    )
    assert data.area_of_operation == ["England", "Wales"]
    assert data.company_number == "01234567"
    assert data.latest_acc_fin_period_end_date == "2024-03-31"
    assert data.trustee_count == 12


def test_charity_data_open_org_fields_default_to_none():
    """Existing call sites that don't pass the new fields must still work."""
    data = CharityData(
        name="Test",
        number="1234567",
        status="Registered",
        date_registered=None,
        date_removed=None,
        latest_income=None,
        latest_expenditure=None,
        charitable_objects=None,
        activities=None,
        trustees=[],
        contact={},
    )
    assert data.area_of_operation is None
    assert data.company_number is None
    assert data.latest_acc_fin_period_end_date is None
    assert data.trustee_count is None


def test_parse_api_response_extracts_area_of_operation():
    """``Where`` classifications in ``who_what_where`` populate area_of_operation."""
    response = {
        "charity_name": "Test",
        "who_what_where": [
            {"classification_type": "Where", "classification_desc": "England"},
            {"classification_type": "Where", "classification_desc": "Wales"},
            {"classification_type": "What", "classification_desc": "Education"},
        ],
    }
    result = _parse_api_response(response, "1234567")
    assert result is not None
    assert result.area_of_operation == ["England", "Wales"]


def test_parse_api_response_extracts_company_number():
    response = {
        "charity_name": "Test",
        "company_registration_number": "01234567",
    }
    result = _parse_api_response(response, "1234567")
    assert result is not None
    assert result.company_number == "01234567"


def test_parse_api_response_extracts_latest_acc_fin_period_end_date():
    response = {
        "charity_name": "Test",
        "latest_acc_fin_period_end_date": "2024-03-31",
    }
    result = _parse_api_response(response, "1234567")
    assert result is not None
    assert result.latest_acc_fin_period_end_date == "2024-03-31"


def test_parse_api_response_extracts_trustee_count():
    """Trustee count comes from a dedicated field, not len(trustee_names).

    The trustees list is capped at 10 by the parser, so deriving the count from
    its length would under-count larger boards. The CC API exposes the true count
    separately.
    """
    response = {
        "charity_name": "Test",
        "trustee_count": 15,
        "trustee_names": [{"trustee_name": f"T{i}"} for i in range(20)],
    }
    result = _parse_api_response(response, "1234567")
    assert result is not None
    assert result.trustee_count == 15
    assert len(result.trustees) == 10  # Existing cap is preserved.


def test_parse_api_response_open_org_fields_missing():
    """Missing classification/company/date/count fields all default to None."""
    response = {
        "charity_name": "Minimal",
    }
    result = _parse_api_response(response, "1234567")
    assert result is not None
    assert result.area_of_operation is None
    assert result.company_number is None
    assert result.latest_acc_fin_period_end_date is None
    assert result.trustee_count is None
