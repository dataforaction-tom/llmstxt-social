"""Tests for llms.txt generation."""

import pytest
from llmstxt_social.analyzer import OrganisationAnalysis, FunderAnalysis
from llmstxt_social.extractor import ExtractedPage, PageType
from llmstxt_social.generator import generate_charity_llmstxt, generate_funder_llmstxt


def test_generate_charity_llmstxt():
    """Test charity llms.txt generation."""
    analysis = OrganisationAnalysis(
        name="Test Charity",
        org_type="charity",
        registration_number="1234567",
        mission="Helping people in need",
        description="We provide support to vulnerable communities through direct services.",
        geographic_area="Greater Manchester",
        services=[
            {
                "name": "Support Service",
                "description": "Direct support for individuals",
                "eligibility": "Adults 18+"
            }
        ],
        beneficiaries="Vulnerable adults",
        themes=["social care", "community support"],
        contact={"email": "hello@test.org", "phone": "0161 123 4567"},
        team_info="15 staff members",
        ai_guidance=["Always verify service availability"]
    )

    pages = [
        ExtractedPage(
            url="https://test.org",
            title="Home",
            description="Homepage",
            headings=["Welcome"],
            body_text="Welcome to our charity",
            page_type=PageType.HOME,
        ),
        ExtractedPage(
            url="https://test.org/about",
            title="About Us",
            description="Learn about our work",
            headings=["Who We Are"],
            body_text="About our charity",
            page_type=PageType.ABOUT,
        ),
    ]

    result = generate_charity_llmstxt(analysis, pages)

    # Check structure
    assert result.startswith("# Test Charity")
    assert "> Helping people in need" in result
    assert "charity number 1234567" in result
    assert "## About" in result
    assert "## For Funders" in result
    assert "## For AI Systems" in result

    # Check content
    assert "Greater Manchester" in result
    assert "hello@test.org" in result or "Contact" in result
    assert "Always verify service availability" in result


def test_generate_funder_llmstxt():
    """Test funder llms.txt generation."""
    analysis = FunderAnalysis(
        name="Test Foundation",
        funder_type="independent",
        registration_number="7654321",
        mission="Supporting grassroots projects",
        description="We fund community initiatives across the region.",
        geographic_focus="West Yorkshire",
        thematic_focus=["community development", "youth"],
        programmes=[
            {
                "name": "Small Grants",
                "description": "Up to £5,000 for community projects",
                "eligibility": "Registered charities and CICs"
            }
        ],
        grant_sizes={"min": 1000, "max": 25000, "typical": "£5,000-£10,000"},
        who_can_apply=["Registered charities", "CICs"],
        who_cannot_apply=["Individuals", "Political organisations"],
        application_process="Online application form",
        deadlines="Quarterly",
        contact={"email": "grants@foundation.org"},
        success_factors=["Clear community need", "Strong governance"],
        ai_guidance=["Never guarantee funding"]
    )

    pages = [
        ExtractedPage(
            url="https://foundation.org",
            title="Home",
            description="Homepage",
            headings=["Welcome"],
            body_text="Welcome",
            page_type=PageType.HOME,
        ),
    ]

    result = generate_funder_llmstxt(analysis, pages)

    # Check structure
    assert result.startswith("# Test Foundation")
    assert "> Supporting grassroots projects" in result
    assert "independent foundation" in result
    assert "## About" in result
    assert "## For Applicants" in result
    assert "## For AI Systems" in result

    # Check content
    assert "West Yorkshire" in result
    assert "Never guarantee funding" in result
    assert "£1,000" in result or "£25,000" in result
