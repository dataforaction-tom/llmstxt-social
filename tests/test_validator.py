"""Tests for llms.txt validation."""

import pytest
from llmstxt_social.validator import validate_llmstxt, ValidationLevel


def test_validate_valid_charity():
    """Test validation of a valid charity llms.txt."""
    content = """# Test Charity

> Helping people in need

Registered charity 1234567. We provide support services.

## About

- [About Us](https://example.org/about): Learn about our work

## Services

- [Support Service](https://example.org/services): Direct support

## For Funders

- Contact: hello@example.org

## For AI Systems

- Always verify service availability
"""

    result = validate_llmstxt(content, template="charity")

    assert result.valid
    assert result.spec_compliance >= 0.8
    assert len([i for i in result.issues if i.level == ValidationLevel.ERROR]) == 0


def test_validate_missing_h1():
    """Test validation catches missing H1."""
    content = """This is just text without a heading.

## About

Some content here.
"""

    result = validate_llmstxt(content)

    assert not result.valid
    assert any(
        issue.level == ValidationLevel.ERROR and "H1" in issue.message
        for issue in result.issues
    )


def test_validate_missing_blockquote():
    """Test validation warns about missing blockquote."""
    content = """# Test Charity

Registered charity. This should be a blockquote.

## About

- [About](https://example.org): About us
"""

    result = validate_llmstxt(content)

    # Should have warning about missing blockquote
    assert any(
        issue.level == ValidationLevel.WARNING and "blockquote" in issue.message.lower()
        for issue in result.issues
    )


def test_validate_multiple_h1():
    """Test validation catches multiple H1 headings."""
    content = """# First Heading

> Description

# Second Heading

This should not be allowed.
"""

    result = validate_llmstxt(content)

    assert not result.valid
    assert any(
        issue.level == ValidationLevel.ERROR and "H1" in issue.message
        for issue in result.issues
    )


def test_validate_charity_completeness():
    """Test completeness score for charity template."""
    # Complete version
    complete_content = """# Test Charity

> Mission

Description

## About
- [About](https://example.org): About

## Services
- [Service](https://example.org): Service

## Get Help
- [Help](https://example.org): Help

## Get Involved
- [Volunteer](https://example.org): Volunteer

## For Funders
- Contact: test@example.org

## For AI Systems
- Guidance here
"""

    result = validate_llmstxt(complete_content, template="charity")
    assert result.completeness >= 0.9

    # Minimal version
    minimal_content = """# Test Charity

> Mission

Description

## About
- [About](https://example.org): About
"""

    result = validate_llmstxt(minimal_content, template="charity")
    assert result.completeness < 0.5


def test_validate_funder_transparency():
    """Test transparency scoring for funders."""
    # Open transparency
    open_content = """# Test Foundation

> Mission

Description

## About
- [About](https://example.org): About

## What We Fund
- [Priorities](https://example.org): Priorities

## How to Apply
- [Apply](https://example.org): Application process

## For Applicants
- Geographic focus: UK
- Grant sizes: min £1,000, max £10,000
- Contact: grants@example.org
- Deadlines: Quarterly
- Success rate: 25%

## For AI Systems
- Never guarantee funding
"""

    result = validate_llmstxt(open_content, template="funder")
    assert result.transparency_score in ["Transparent", "Open"]

    # Minimal transparency
    minimal_content = """# Test Foundation

> Mission

Description

## About
- [About](https://example.org): About
"""

    result = validate_llmstxt(minimal_content, template="funder")
    assert result.transparency_score in ["Minimal", "Basic"]
