"""Tests for content extraction."""

import pytest
from llmstxt_social.crawler import Page
from llmstxt_social.extractor import (
    extract_content,
    classify_page_type,
    PageType,
    _extract_charity_number,
)


def test_extract_title():
    """Test title extraction from HTML."""
    html = """
    <html>
        <head><title>Test Charity - About Us</title></head>
        <body><h1>About Our Charity</h1></body>
    </html>
    """

    page = Page(
        url="https://example.org/about",
        title="Test Charity - About Us",
        html=html,
        status_code=200
    )

    extracted = extract_content(page)
    assert extracted.title == "Test Charity - About Us"


def test_extract_charity_number():
    """Test charity number extraction."""
    test_cases = [
        ("Registered charity number: 1234567", "1234567"),
        ("Charity no. 123456", "123456"),
        ("We are a registered charity 9876543 in England and Wales", "9876543"),
        ("No charity number here", None),
    ]

    for text, expected in test_cases:
        result = _extract_charity_number(text)
        assert result == expected


def test_classify_page_type_about():
    """Test classification of about pages."""
    page_type = classify_page_type(
        url="https://example.org/about-us",
        title="About Us",
        headings=["Who We Are", "Our Mission"],
        body_text="We are a charity that helps people..."
    )
    assert page_type == PageType.ABOUT


def test_classify_page_type_contact():
    """Test classification of contact pages."""
    page_type = classify_page_type(
        url="https://example.org/contact",
        title="Contact Us",
        headings=["Get In Touch"],
        body_text="Email us at hello@example.org"
    )
    assert page_type == PageType.CONTACT


def test_classify_page_type_services():
    """Test classification of services pages."""
    page_type = classify_page_type(
        url="https://example.org/our-services",
        title="Our Services",
        headings=["What We Do"],
        body_text="We provide support services to vulnerable people"
    )
    assert page_type == PageType.SERVICES


def test_classify_page_type_home():
    """Test classification of home page."""
    page_type = classify_page_type(
        url="https://example.org/",
        title="Welcome",
        headings=["Welcome to Our Charity"],
        body_text="Homepage content"
    )
    assert page_type == PageType.HOME


def test_body_text_extraction():
    """Test that body text extraction removes navigation and scripts."""
    html = """
    <html>
        <head>
            <script>var x = 1;</script>
            <style>.foo { color: red; }</style>
        </head>
        <body>
            <nav>Skip this navigation</nav>
            <main>
                <h1>Main Content</h1>
                <p>This is the important content.</p>
            </main>
            <footer>Skip this footer</footer>
        </body>
    </html>
    """

    page = Page(
        url="https://example.org",
        title="Test",
        html=html,
        status_code=200
    )

    extracted = extract_content(page)

    # Navigation and footer should be removed
    assert "Skip this navigation" not in extracted.body_text
    assert "Skip this footer" not in extracted.body_text

    # Main content should be present
    assert "Main Content" in extracted.body_text
    assert "important content" in extracted.body_text

    # Scripts and styles should not be in body text
    assert "var x = 1" not in extracted.body_text
    assert "color: red" not in extracted.body_text
