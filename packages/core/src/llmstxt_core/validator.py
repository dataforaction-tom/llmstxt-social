"""Validate llms.txt files against the specification."""

import re
from dataclasses import dataclass
from enum import Enum


class ValidationLevel(Enum):
    """Validation issue severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A single validation issue."""
    level: ValidationLevel
    message: str
    line: int | None = None


@dataclass
class ValidationResult:
    """Results from validating an llms.txt file."""
    valid: bool
    issues: list[ValidationIssue]
    spec_compliance: float
    completeness: float
    transparency_score: str | None = None


def validate_llmstxt(
    content: str,
    template: str = "charity"
) -> ValidationResult:
    """
    Validate llms.txt content against the spec.

    Args:
        content: The llms.txt file content
        template: "charity", "funder", "public_sector", or "startup"

    Returns:
        ValidationResult with issues and scores
    """
    issues = []
    lines = content.split('\n')

    # Core spec validations
    _validate_h1_heading(lines, issues)
    _validate_blockquote(lines, issues)
    _validate_sections(lines, issues)
    _validate_url_lists(lines, issues)

    # Template-specific validations
    if template == "charity":
        _validate_charity_sections(lines, issues)
    elif template == "funder":
        _validate_funder_sections(lines, issues)
    elif template == "public_sector":
        _validate_public_sector_sections(lines, issues)
    elif template == "startup":
        _validate_startup_sections(lines, issues)
    else:
        issues.append(ValidationIssue(
            level=ValidationLevel.ERROR,
            message=f"Unknown template '{template}'. Expected one of: charity, funder, public_sector, startup.",
        ))

    # Calculate scores
    spec_compliance = _calculate_spec_compliance(issues)
    completeness = _calculate_completeness(lines, template)

    # Calculate transparency score for funders
    transparency_score = None
    if template == "funder":
        transparency_score = _calculate_transparency_score(lines)

    # Determine overall validity (no ERROR level issues)
    valid = not any(issue.level == ValidationLevel.ERROR for issue in issues)

    return ValidationResult(
        valid=valid,
        issues=issues,
        spec_compliance=spec_compliance,
        completeness=completeness,
        transparency_score=transparency_score
    )


def _validate_h1_heading(lines: list[str], issues: list[ValidationIssue]) -> None:
    """Validate H1 heading exists and is first element."""
    # Skip empty lines at start
    first_non_empty_line = None
    first_non_empty_idx = 0

    for idx, line in enumerate(lines):
        if line.strip():
            first_non_empty_line = line.strip()
            first_non_empty_idx = idx
            break

    if not first_non_empty_line:
        issues.append(ValidationIssue(
            level=ValidationLevel.ERROR,
            message="File is empty",
            line=1
        ))
        return

    if not first_non_empty_line.startswith('# '):
        issues.append(ValidationIssue(
            level=ValidationLevel.ERROR,
            message="First element must be an H1 heading (# Title)",
            line=first_non_empty_idx + 1
        ))
        return

    # Check if H1 has content
    h1_content = first_non_empty_line[2:].strip()
    if not h1_content:
        issues.append(ValidationIssue(
            level=ValidationLevel.ERROR,
            message="H1 heading must have content",
            line=first_non_empty_idx + 1
        ))


def _validate_blockquote(lines: list[str], issues: list[ValidationIssue]) -> None:
    """Validate blockquote exists after H1."""
    # Find H1
    h1_idx = None
    for idx, line in enumerate(lines):
        if line.strip().startswith('# '):
            h1_idx = idx
            break

    if h1_idx is None:
        return  # Already flagged in H1 validation

    # Look for blockquote in next few lines
    found_blockquote = False
    for idx in range(h1_idx + 1, min(h1_idx + 5, len(lines))):
        line = lines[idx].strip()
        if not line:
            continue
        if line.startswith('> '):
            found_blockquote = True
            # Check if blockquote has content
            if not line[2:].strip():
                issues.append(ValidationIssue(
                    level=ValidationLevel.WARNING,
                    message="Blockquote should have meaningful content",
                    line=idx + 1
                ))
            break
        if not line.startswith('>'):
            # Found non-empty, non-blockquote line
            break

    if not found_blockquote:
        issues.append(ValidationIssue(
            level=ValidationLevel.WARNING,
            message="Should have a blockquote (>) after H1 with one-line description",
            line=h1_idx + 2
        ))


def _validate_sections(lines: list[str], issues: list[ValidationIssue]) -> None:
    """Validate that sections use H2 headings."""
    in_header = True

    for idx, line in enumerate(lines):
        stripped = line.strip()

        # Skip until we're past the header
        if in_header:
            if stripped.startswith('## '):
                in_header = False
            else:
                continue

        # Check for H3+ headings (should use H2)
        if stripped.startswith('### '):
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="Use H2 (##) for sections, not H3 or deeper",
                line=idx + 1
            ))

        # Check for additional H1 headings
        if stripped.startswith('# ') and not in_header:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                message="Only one H1 heading allowed (at the start)",
                line=idx + 1
            ))


def _validate_url_lists(lines: list[str], issues: list[ValidationIssue]) -> None:
    """Validate URL list formatting."""
    for idx, line in enumerate(lines):
        stripped = line.strip()

        # Check for list items
        if stripped.startswith('- '):
            # Check for URL format: [Title](url)
            if '[' in stripped and '](' in stripped and ')' in stripped:
                # Validate markdown link format
                link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
                match = re.search(link_pattern, stripped)

                if match:
                    title, url = match.groups()

                    if not title.strip():
                        issues.append(ValidationIssue(
                            level=ValidationLevel.WARNING,
                            message="Link title should not be empty",
                            line=idx + 1
                        ))

                    if not url.strip():
                        issues.append(ValidationIssue(
                            level=ValidationLevel.WARNING,
                            message="Link URL should not be empty",
                            line=idx + 1
                        ))
                    elif not url.startswith(('http://', 'https://', '/')):
                        issues.append(ValidationIssue(
                            level=ValidationLevel.INFO,
                            message="URLs should be absolute (starting with http:// or https://)",
                            line=idx + 1
                        ))


def _validate_charity_sections(lines: list[str], issues: list[ValidationIssue]) -> None:
    """Validate recommended sections for charity template."""
    content = '\n'.join(lines).lower()

    recommended_sections = [
        ("## about", "About section"),
        ("## for ai systems", "For AI Systems section"),
    ]

    for section_marker, section_name in recommended_sections:
        if section_marker not in content:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message=f"Recommended section missing: {section_name}",
            ))

    # Check for contact information
    if "contact" not in content and "@" not in content:
        issues.append(ValidationIssue(
            level=ValidationLevel.WARNING,
            message="Should include contact information",
        ))


def _validate_funder_sections(lines: list[str], issues: list[ValidationIssue]) -> None:
    """Validate recommended sections for funder template."""
    content = '\n'.join(lines).lower()

    recommended_sections = [
        ("## what we fund", "What We Fund section"),
        ("## how to apply", "How to Apply section"),
        ("## for applicants", "For Applicants section"),
        ("## for ai systems", "For AI Systems section"),
    ]

    for section_marker, section_name in recommended_sections:
        if section_marker not in content:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message=f"Recommended section missing: {section_name}",
            ))


def _validate_public_sector_sections(lines: list[str], issues: list[ValidationIssue]) -> None:
    """Validate recommended sections for public sector template."""
    content = '\n'.join(lines).lower()

    recommended_sections = [
        ("## about", "About section"),
        ("## services", "Services section"),
        ("## get help", "Get Help section"),
        ("## contact", "Contact section"),
        ("## for service users", "For Service Users section"),
        ("## for ai systems", "For AI Systems section"),
    ]

    for section_marker, section_name in recommended_sections:
        if section_marker not in content:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message=f"Recommended section missing: {section_name}",
            ))


def _validate_startup_sections(lines: list[str], issues: list[ValidationIssue]) -> None:
    """Validate recommended sections for startup template."""
    content = '\n'.join(lines).lower()

    recommended_sections = [
        ("## about", "About section"),
        ("## product/services", "Product/Services section"),
        ("## customers", "Customers section"),
        ("## pricing", "Pricing section"),
        ("## for investors", "For Investors section"),
        ("## contact", "Contact section"),
        ("## for ai systems", "For AI Systems section"),
    ]

    for section_marker, section_name in recommended_sections:
        if section_marker not in content:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message=f"Recommended section missing: {section_name}",
            ))


def _calculate_spec_compliance(issues: list[ValidationIssue]) -> float:
    """Calculate spec compliance score (0-1)."""
    if not issues:
        return 1.0

    # Weight by severity
    error_weight = 1.0
    warning_weight = 0.5
    info_weight = 0.1

    total_penalty = sum(
        error_weight if issue.level == ValidationLevel.ERROR
        else warning_weight if issue.level == ValidationLevel.WARNING
        else info_weight
        for issue in issues
    )

    # Max penalty for full non-compliance (arbitrary but reasonable)
    max_penalty = 10.0

    score = max(0.0, 1.0 - (total_penalty / max_penalty))
    return round(score, 2)


def _calculate_completeness(lines: list[str], template: str) -> float:
    """Calculate completeness score based on sections present."""
    content = '\n'.join(lines).lower()

    expected_sections_by_template = {
        "charity": [
            "## about",
            "## services",
            "## get help",
            "## get involved",
            "## for funders",
            "## for ai systems",
        ],
        "funder": [
            "## about",
            "## what we fund",
            "## how to apply",
            "## for applicants",
            "## for ai systems",
        ],
        "public_sector": [
            "## about",
            "## services",
            "## get help",
            "## contact",
            "## for service users",
            "## for ai systems",
        ],
        "startup": [
            "## about",
            "## product/services",
            "## customers",
            "## pricing",
            "## for investors",
            "## contact",
            "## for ai systems",
        ],
    }

    expected_sections = expected_sections_by_template.get(template)
    if not expected_sections:
        return 0.0

    present = sum(1 for section in expected_sections if section in content)
    score = present / len(expected_sections)

    return round(score, 2)


def _calculate_transparency_score(lines: list[str]) -> str:
    """Calculate transparency score for funders."""
    content = '\n'.join(lines).lower()

    # Basic: has required fields
    basic_fields = ["geographic focus", "contact"]
    has_basic = all(field in content for field in basic_fields)

    # Transparent: includes success factors, application process
    transparent_fields = ["success", "application", "eligibility"]
    has_transparent = has_basic and sum(1 for field in transparent_fields if field in content) >= 2

    # Open: includes grant sizes, deadlines, past grants
    open_fields = ["grant size", "deadline", "past grant"]
    has_open = has_transparent and sum(1 for field in open_fields if field in content) >= 2

    if has_open:
        return "Open"
    elif has_transparent:
        return "Transparent"
    elif has_basic:
        return "Basic"
    else:
        return "Minimal"
