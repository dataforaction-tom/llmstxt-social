"""Tests for Charity Commission enricher."""

import pytest
from llmstxt_social.enrichers.charity_commission import (
    find_charity_number,
    _parse_api_response,
)
from llmstxt_social.extractor import ExtractedPage, PageType


def test_find_charity_number_from_pages():
    """Test finding charity number from extracted pages."""
    pages = [
        ExtractedPage(
            url="https://example.org/about",
            title="About Us",
            description=None,
            headings=[],
            body_text="We are a registered charity number 1234567 in England and Wales.",
            page_type=PageType.ABOUT,
            charity_number=None
        )
    ]

    result = find_charity_number(pages)
    assert result == "1234567"


def test_find_charity_number_various_formats():
    """Test finding charity number with different text formats."""
    test_cases = [
        ("Registered charity no. 123456", "123456"),
        ("Charity Commission number: 7654321", "7654321"),
        ("We are charity number 1111111", "1111111"),
        ("England and Wales charity 999999", "999999"),
    ]

    for text, expected in test_cases:
        pages = [
            ExtractedPage(
                url="https://example.org",
                title="Test",
                description=None,
                headings=[],
                body_text=text,
                page_type=PageType.HOME,
                charity_number=None
            )
        ]

        result = find_charity_number(pages)
        assert result == expected


def test_find_charity_number_from_page_attribute():
    """Test that we use the charity_number attribute if already extracted."""
    pages = [
        ExtractedPage(
            url="https://example.org",
            title="Test",
            description=None,
            headings=[],
            body_text="Some text",
            page_type=PageType.HOME,
            charity_number="1234567"
        )
    ]

    result = find_charity_number(pages)
    assert result == "1234567"


def test_parse_api_response():
    """Test parsing Charity Commission API response."""
    mock_response = {
        "charity": {
            "name": "Test Charity",
            "registrationStatus": "Registered",
            "registeredDate": "2020-01-01",
            "removedDate": None,
            "charitableObjects": "To help people in need",
            "activities": "Providing support services",
        },
        "financial": {
            "income": 100000,
            "spending": 95000,
        },
        "trustees": [
            {"name": "John Doe"},
            {"name": "Jane Smith"},
        ],
        "contact": {
            "email": "info@test.org",
            "phone": "0161 123 4567",
            "address": "123 Test Street"
        }
    }

    result = _parse_api_response(mock_response, "1234567")

    assert result is not None
    assert result.name == "Test Charity"
    assert result.number == "1234567"
    assert result.status == "Registered"
    assert result.latest_income == 100000
    assert result.latest_expenditure == 95000
    assert len(result.trustees) == 2
    assert result.contact["email"] == "info@test.org"


def test_parse_api_response_missing_fields():
    """Test parsing API response with missing fields."""
    mock_response = {
        "charity": {
            "name": "Minimal Charity",
        },
        "financial": {},
        "trustees": [],
    }

    result = _parse_api_response(mock_response, "1234567")

    assert result is not None
    assert result.name == "Minimal Charity"
    assert result.number == "1234567"
    assert result.latest_income is None
    assert result.latest_expenditure is None
    assert len(result.trustees) == 0
