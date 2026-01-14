"""Quality assessment for llms.txt files."""

import json
import re
from dataclasses import dataclass
from enum import Enum
from anthropic import Anthropic

from .validator import validate_llmstxt, ValidationLevel
from .extractor import PageType, ExtractedPage
from .crawler import CrawlResult
from .enrichers.charity_commission import CharityData


class AssessmentCategory(Enum):
    """Categories of assessment checks."""
    STRUCTURE = "structure"
    COMPLETENESS = "completeness"
    QUALITY = "quality"
    WEBSITE_DATA = "website_data"
    SIZE_APPROPRIATE = "size_appropriate"


class IssueSeverity(Enum):
    """Severity of assessment findings."""
    CRITICAL = "critical"  # Missing required section
    MAJOR = "major"        # Quality issue affecting usefulness
    MINOR = "minor"        # Enhancement opportunity
    INFO = "info"          # Informational note


@dataclass
class AssessmentFinding:
    """A single assessment finding."""
    category: AssessmentCategory
    severity: IssueSeverity
    message: str
    section: str | None = None
    suggestion: str | None = None
    line_number: int | None = None


@dataclass
class SectionAssessment:
    """Assessment of a specific section."""
    section_name: str
    present: bool
    content_quality: float  # 0-1 score
    completeness: float  # 0-1 score
    findings: list[AssessmentFinding]


@dataclass
class WebsiteDataGaps:
    """Identified gaps in website data that affect llms.txt quality."""
    missing_page_types: list[str]  # Expected pages not found
    sitemap_detected: bool
    javascript_heavy: bool  # May need Playwright
    navigation_issues: str | None
    suggested_pages: list[str]  # URLs that should be added/improved


@dataclass
class OrganizationSize:
    """Categorization of organization by size."""
    category: str  # "small", "medium", "large", "major"
    income: int | None
    expectations: dict  # Expected sections/content based on size


@dataclass
class AssessmentResult:
    """Complete assessment results."""
    template_type: str
    overall_score: float  # 0-100
    completeness_score: float  # 0-100
    quality_score: float  # 0-100

    # Section-by-section breakdown
    section_assessments: list[SectionAssessment]

    # Findings
    findings: list[AssessmentFinding]

    # Website analysis
    website_gaps: WebsiteDataGaps | None

    # Size-based expectations (for charities)
    org_size: OrganizationSize | None

    # Recommendations
    recommendations: list[str]

    # Raw scores
    scores: dict[str, float]


class LLMSTxtAssessor:
    """Assesses llms.txt files for completeness and quality."""

    # Template definitions
    TEMPLATE_DEFINITIONS = {
        "charity": {
            "required_sections": ["About", "Services", "For Funders", "For AI Systems"],
            "optional_sections": ["Projects", "Impact", "Get Help", "Get Involved"],
            "page_types": {
                "About": [PageType.ABOUT, PageType.HOME, PageType.TEAM],
                "Services": [PageType.SERVICES],
                "Projects": [PageType.PROJECTS],
                "Impact": [PageType.IMPACT],
                "Get Help": [PageType.GET_HELP, PageType.CONTACT],
                "Get Involved": [PageType.VOLUNTEER, PageType.DONATE],
            }
        },
        "funder": {
            "required_sections": ["About", "What We Fund", "For Applicants", "For AI Systems"],
            "optional_sections": ["How to Apply", "Past Grants"],
            "page_types": {
                "About": [PageType.ABOUT, PageType.HOME],
                "What We Fund": [PageType.FUNDING_PRIORITIES],
                "How to Apply": [PageType.HOW_TO_APPLY, PageType.ELIGIBILITY],
                "Past Grants": [PageType.PAST_GRANTS],
            }
        },
        "public_sector": {
            "required_sections": ["About", "Services", "Contact", "For AI Systems"],
            "optional_sections": ["Get Help", "For Service Users"],
            "page_types": {
                "About": [PageType.ABOUT, PageType.HOME],
                "Services": [PageType.SERVICES, PageType.SERVICE_CATEGORY],
                "Get Help": [PageType.GET_HELP, PageType.CONTACT],
            }
        },
        "startup": {
            "required_sections": ["About", "Product/Services", "Contact", "For AI Systems"],
            "optional_sections": ["Customers", "Pricing", "For Investors"],
            "page_types": {
                "About": [PageType.ABOUT, PageType.HOME, PageType.TEAM],
                "Product/Services": [PageType.SERVICES],
                "Customers": [PageType.CUSTOMERS],
                "Pricing": [PageType.PRICING],
                "For Investors": [PageType.INVESTORS],
            }
        }
    }

    # Size-based expectations for charities
    SIZE_EXPECTATIONS = {
        "small": {  # <£100k
            "required": ["About", "Services", "Contact"],
            "recommended": ["Get Help", "For Funders"],
            "min_services": 1,
            "projects_expected": False,
            "impact_metrics_expected": False
        },
        "medium": {  # £100k-£1M
            "required": ["About", "Services", "Get Help", "For Funders"],
            "recommended": ["Projects", "Get Involved", "Impact"],
            "min_services": 2,
            "projects_expected": True,
            "impact_metrics_expected": False
        },
        "large": {  # £1M-£10M
            "required": ["About", "Services", "Projects", "Impact", "Get Help", "For Funders"],
            "recommended": ["Get Involved"],
            "min_services": 3,
            "projects_expected": True,
            "impact_metrics_expected": True
        },
        "major": {  # >£10M
            "required": ["About", "Services", "Projects", "Impact", "Get Help", "Get Involved", "For Funders"],
            "recommended": [],
            "min_services": 5,
            "projects_expected": True,
            "impact_metrics_expected": True,
            "multiple_projects_expected": True
        }
    }

    def __init__(self, template_type: str, anthropic_client: Anthropic | None = None):
        """
        Initialize the assessor.

        Args:
            template_type: "charity", "funder", "public_sector", or "startup"
            anthropic_client: Optional Anthropic client for AI quality analysis
        """
        self.template_type = template_type
        self.template_def = self.TEMPLATE_DEFINITIONS.get(template_type, self.TEMPLATE_DEFINITIONS["charity"])
        self.client = anthropic_client

    async def assess(
        self,
        llmstxt_content: str,
        website_url: str | None = None,
        crawl_result: CrawlResult | None = None,
        enrichment_data: CharityData | None = None
    ) -> AssessmentResult:
        """
        Comprehensive assessment of llms.txt file.

        Args:
            llmstxt_content: The llms.txt file content
            website_url: Optional website URL to compare against
            crawl_result: Optional crawl data for website gap analysis
            enrichment_data: Optional enrichment data for sizing

        Returns:
            AssessmentResult with scores, findings, and recommendations
        """
        findings = []
        section_assessments = []

        # 1. Parse the llms.txt file
        parsed = self._parse_llmstxt(llmstxt_content)

        # 2. Run existing validator for structural checks
        validation_result = validate_llmstxt(llmstxt_content, self.template_type)
        for issue in validation_result.issues:
            severity = IssueSeverity.CRITICAL if issue.level == ValidationLevel.ERROR else \
                      IssueSeverity.MAJOR if issue.level == ValidationLevel.WARNING else \
                      IssueSeverity.INFO
            findings.append(AssessmentFinding(
                category=AssessmentCategory.STRUCTURE,
                severity=severity,
                message=issue.message,
                section=None,
                suggestion=None,
                line_number=issue.line
            ))

        # 3. Rule-based completeness checks
        completeness_findings = self._check_completeness(parsed)
        findings.extend(completeness_findings)

        # 4. Section-by-section assessment
        for section in self.template_def["required_sections"] + self.template_def["optional_sections"]:
            assessment = self._assess_section(section, parsed)
            section_assessments.append(assessment)
            findings.extend(assessment.findings)

        # 5. Size-based expectations (charities only)
        org_size = None
        if self.template_type == "charity" and enrichment_data:
            org_size = self._categorize_size(enrichment_data)
            size_findings = self._check_size_expectations(parsed, org_size)
            findings.extend(size_findings)

        # 6. Website gap analysis
        website_gaps = None
        if crawl_result:
            from .extractor import extract_content
            extracted_pages = [extract_content(p) for p in crawl_result.pages]
            website_gaps = self._analyze_website_gaps(parsed, crawl_result, extracted_pages)
            gap_findings = self._website_gap_findings(website_gaps)
            findings.extend(gap_findings)

        # 7. AI-powered quality analysis
        if self.client:
            quality_findings = await self._ai_quality_analysis(llmstxt_content, parsed)
            findings.extend(quality_findings)

        # 8. Calculate scores
        scores = self._calculate_scores(section_assessments, findings, org_size)

        # 9. Generate recommendations
        recommendations = self._generate_recommendations(findings, website_gaps, org_size)

        return AssessmentResult(
            template_type=self.template_type,
            overall_score=scores["overall"],
            completeness_score=scores["completeness"],
            quality_score=scores["quality"],
            section_assessments=section_assessments,
            findings=findings,
            website_gaps=website_gaps,
            org_size=org_size,
            recommendations=recommendations,
            scores=scores
        )

    def _parse_llmstxt(self, content: str) -> dict:
        """Parse llms.txt content into sections."""
        lines = content.split('\n')
        parsed = {
            "title": None,
            "mission": None,
            "sections": {}
        }

        current_section = None
        current_content = []

        for line in lines:
            # H1 title
            if line.startswith('# '):
                parsed["title"] = line[2:].strip()
            # Blockquote mission
            elif line.startswith('> '):
                parsed["mission"] = line[2:].strip()
            # H2 section
            elif line.startswith('## '):
                if current_section:
                    parsed["sections"][current_section] = '\n'.join(current_content)
                current_section = line[3:].strip()
                current_content = []
            # Content line
            elif current_section:
                current_content.append(line)

        # Add last section
        if current_section:
            parsed["sections"][current_section] = '\n'.join(current_content)

        return parsed

    def _check_completeness(self, parsed: dict) -> list[AssessmentFinding]:
        """Check completeness of required sections."""
        findings = []

        for section in self.template_def["required_sections"]:
            if section not in parsed["sections"]:
                findings.append(AssessmentFinding(
                    category=AssessmentCategory.COMPLETENESS,
                    severity=IssueSeverity.CRITICAL,
                    message=f"Required section '{section}' is missing",
                    section=section,
                    suggestion=f"Add '{section}' section with relevant content for your organization"
                ))
            elif not parsed["sections"][section].strip():
                findings.append(AssessmentFinding(
                    category=AssessmentCategory.COMPLETENESS,
                    severity=IssueSeverity.MAJOR,
                    message=f"Section '{section}' is present but empty",
                    section=section,
                    suggestion=f"Add content to the '{section}' section"
                ))

        return findings

    def _assess_section(self, section_name: str, parsed: dict) -> SectionAssessment:
        """Assess a specific section."""
        present = section_name in parsed["sections"]
        findings = []

        if not present:
            content_quality = 0.0
            completeness = 0.0
        else:
            content = parsed["sections"][section_name]
            lines = [l.strip() for l in content.split('\n') if l.strip()]

            # Basic completeness check (has content)
            if len(lines) == 0:
                completeness = 0.0
            elif len(lines) < 2:
                completeness = 0.3
            elif len(lines) < 4:
                completeness = 0.6
            else:
                completeness = 1.0

            # Basic quality check (has links, structured content)
            has_links = any('[' in line and '](' in line for line in lines)
            has_list_items = any(line.startswith('-') for line in lines)

            if has_links and has_list_items:
                content_quality = 1.0
            elif has_links or has_list_items:
                content_quality = 0.7
            else:
                content_quality = 0.4

        return SectionAssessment(
            section_name=section_name,
            present=present,
            content_quality=content_quality,
            completeness=completeness,
            findings=findings
        )

    def _categorize_size(self, charity_data: CharityData) -> OrganizationSize:
        """Categorize charity by size based on income."""
        income = charity_data.latest_income or 0

        if income < 100_000:
            category = "small"
        elif income < 1_000_000:
            category = "medium"
        elif income < 10_000_000:
            category = "large"
        else:
            category = "major"

        expectations = self.SIZE_EXPECTATIONS[category]

        return OrganizationSize(
            category=category,
            income=income,
            expectations=expectations
        )

    def _check_size_expectations(self, parsed: dict, org_size: OrganizationSize) -> list[AssessmentFinding]:
        """Check charity-specific expectations based on size."""
        findings = []
        expectations = org_size.expectations

        # Check required sections for size
        for section in expectations["required"]:
            if section not in parsed["sections"]:
                findings.append(AssessmentFinding(
                    category=AssessmentCategory.SIZE_APPROPRIATE,
                    severity=IssueSeverity.MAJOR,
                    message=f"Section '{section}' expected for {org_size.category} charity (£{org_size.income:,} income)",
                    section=section,
                    suggestion=f"Add '{section}' section - organizations of your size typically include this"
                ))

        # Check service count
        services_content = parsed["sections"].get("Services", "")
        service_count = len([l for l in services_content.split('\n') if l.strip().startswith('-')])

        if service_count < expectations["min_services"]:
            findings.append(AssessmentFinding(
                category=AssessmentCategory.SIZE_APPROPRIATE,
                severity=IssueSeverity.MINOR,
                message=f"Expected at least {expectations['min_services']} services for {org_size.category} charity, found {service_count}",
                section="Services",
                suggestion="Add more service descriptions or ensure all major services are listed"
            ))

        # Check projects expectation
        if expectations.get("projects_expected") and "Projects" not in parsed["sections"]:
            findings.append(AssessmentFinding(
                category=AssessmentCategory.SIZE_APPROPRIATE,
                severity=IssueSeverity.MAJOR,
                message=f"Projects section expected for {org_size.category} charity",
                section="Projects",
                suggestion="Add a Projects section describing your active initiatives"
            ))

        # Check impact metrics expectation
        if expectations.get("impact_metrics_expected") and "Impact" not in parsed["sections"]:
            findings.append(AssessmentFinding(
                category=AssessmentCategory.SIZE_APPROPRIATE,
                severity=IssueSeverity.MAJOR,
                message=f"Impact section expected for {org_size.category} charity",
                section="Impact",
                suggestion="Add an Impact section with outcomes and metrics"
            ))

        return findings

    def _analyze_website_gaps(self, parsed: dict, crawl_result: CrawlResult, extracted_pages: list[ExtractedPage]) -> WebsiteDataGaps:
        """Identify what's missing from the website that affects llms.txt quality."""

        # Find which page types exist
        found_page_types = set(p.page_type for p in extracted_pages)

        missing_page_types = []
        suggested_pages = []

        # Check for expected page types based on sections
        for section, expected_types in self.template_def.get("page_types", {}).items():
            if section in self.template_def["required_sections"]:
                if not any(pt in found_page_types for pt in expected_types):
                    missing_page_types.append(section)

                    # Generate suggestions
                    if section == "Services":
                        suggested_pages.append("Create a dedicated /services or /what-we-do page")
                    elif section == "Projects":
                        suggested_pages.append("Add a /projects or /our-work page with project details")
                    elif section == "Impact":
                        suggested_pages.append("Add an /impact or /our-impact page with outcomes data")
                    elif section == "Pricing":
                        suggested_pages.append("Add a /pricing page with transparent pricing information")
                    elif section == "Customers":
                        suggested_pages.append("Add a /customers or /case-studies page")

        # Check sitemap
        sitemap_detected = len(crawl_result.sitemap_urls) > 0
        if not sitemap_detected:
            suggested_pages.append("Add a sitemap.xml file to help with content discovery")

        return WebsiteDataGaps(
            missing_page_types=missing_page_types,
            sitemap_detected=sitemap_detected,
            javascript_heavy=False,  # Could detect this from crawl
            navigation_issues=None,
            suggested_pages=suggested_pages
        )

    def _website_gap_findings(self, website_gaps: WebsiteDataGaps) -> list[AssessmentFinding]:
        """Convert website gaps to findings."""
        findings = []

        for missing_type in website_gaps.missing_page_types:
            findings.append(AssessmentFinding(
                category=AssessmentCategory.WEBSITE_DATA,
                severity=IssueSeverity.MAJOR,
                message=f"Website appears to be missing {missing_type} page(s)",
                section=missing_type,
                suggestion=f"Add {missing_type} page(s) to your website to improve llms.txt completeness"
            ))

        if not website_gaps.sitemap_detected:
            findings.append(AssessmentFinding(
                category=AssessmentCategory.WEBSITE_DATA,
                severity=IssueSeverity.INFO,
                message="No sitemap.xml detected",
                section=None,
                suggestion="Add a sitemap.xml to help with content discovery"
            ))

        return findings

    async def _ai_quality_analysis(self, llmstxt_content: str, parsed: dict) -> list[AssessmentFinding]:
        """Use Claude to assess content quality."""

        QUALITY_ANALYSIS_PROMPT = f"""You are assessing the quality of an llms.txt file for a {self.template_type} organization.

llms.txt content:
{llmstxt_content}

Assess the quality on these dimensions:

1. **Clarity**: Are descriptions clear and understandable?
2. **Usefulness**: Would this help AI systems represent the organization accurately?
3. **Completeness**: Are descriptions sufficiently detailed?
4. **Accuracy concerns**: Any red flags or inconsistencies?
5. **Voice/tone**: Appropriate for the organization type?

For each issue found, provide:
- Which section has the issue
- What the problem is
- Why it matters
- How to fix it
- Severity (critical/major/minor/info)

Return as JSON array:
[
  {{
    "section": "Services",
    "issue": "Descriptions are too vague",
    "why_matters": "AI systems won't understand what services are actually offered",
    "suggestion": "Add specific details about what each service involves",
    "severity": "major"
  }}
]

Only return the JSON array, no other text."""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": QUALITY_ANALYSIS_PROMPT}]
            )

            # Parse response
            response_text = message.content[0].text

            # Extract JSON (handle potential markdown code blocks)
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_text = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_text = response_text.strip()

            issues = json.loads(json_text)

            findings = []
            for issue in issues:
                findings.append(AssessmentFinding(
                    category=AssessmentCategory.QUALITY,
                    severity=IssueSeverity[issue["severity"].upper()],
                    message=f"{issue['issue']} - {issue['why_matters']}",
                    section=issue.get("section"),
                    suggestion=issue["suggestion"]
                ))

            return findings

        except Exception as e:
            # If AI analysis fails, return empty list
            return []

    def _calculate_scores(
        self,
        section_assessments: list[SectionAssessment],
        findings: list[AssessmentFinding],
        org_size: OrganizationSize | None
    ) -> dict[str, float]:
        """Calculate various quality scores."""

        # Completeness score (0-100)
        total_required = len(self.template_def["required_sections"])
        sections_present = sum(1 for s in section_assessments if s.present and s.section_name in self.template_def["required_sections"])
        base_completeness = (sections_present / total_required) * 100 if total_required > 0 else 0

        # Adjust for content quality within sections
        if section_assessments:
            avg_section_completeness = sum(s.completeness for s in section_assessments) / len(section_assessments)
            completeness_score = (base_completeness * 0.6) + (avg_section_completeness * 100 * 0.4)
        else:
            completeness_score = base_completeness

        # Quality score (0-100)
        quality_score = 100.0
        severity_weights = {
            IssueSeverity.CRITICAL: 15,
            IssueSeverity.MAJOR: 10,
            IssueSeverity.MINOR: 5,
            IssueSeverity.INFO: 0
        }

        for finding in findings:
            if finding.category in [AssessmentCategory.QUALITY, AssessmentCategory.COMPLETENESS]:
                quality_score -= severity_weights[finding.severity]

        quality_score = max(0, min(100, quality_score))

        # Overall score (weighted average)
        overall_score = (completeness_score * 0.5) + (quality_score * 0.5)

        # Size-appropriateness bonus (charities only)
        if org_size:
            size_findings = [f for f in findings if f.category == AssessmentCategory.SIZE_APPROPRIATE]
            if len(size_findings) == 0:
                overall_score = min(100, overall_score * 1.1)  # 10% bonus

        # Structure score
        structure_findings = [f for f in findings if f.category == AssessmentCategory.STRUCTURE]
        structure_score = max(0, 100 - (len(structure_findings) * 10))

        return {
            "overall": round(overall_score, 1),
            "completeness": round(completeness_score, 1),
            "quality": round(quality_score, 1),
            "structure": round(structure_score, 1)
        }

    def _generate_recommendations(
        self,
        findings: list[AssessmentFinding],
        website_gaps: WebsiteDataGaps | None,
        org_size: OrganizationSize | None
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Group findings by severity
        critical_findings = [f for f in findings if f.severity == IssueSeverity.CRITICAL]
        major_findings = [f for f in findings if f.severity == IssueSeverity.MAJOR]

        # Priority 1: Critical issues
        if critical_findings:
            recommendations.append(f"Fix {len(critical_findings)} critical issue(s): " + ", ".join(set(f.section or "structure" for f in critical_findings)))

        # Priority 2: Major quality/completeness issues
        if major_findings:
            major_by_category = {}
            for f in major_findings:
                cat = f.category.value
                if cat not in major_by_category:
                    major_by_category[cat] = []
                major_by_category[cat].append(f)

            for category, issues in major_by_category.items():
                if category == "completeness":
                    recommendations.append(f"Add missing sections: " + ", ".join(set(f.section for f in issues if f.section)))
                elif category == "quality":
                    recommendations.append(f"Improve content quality in: " + ", ".join(set(f.section for f in issues if f.section)))

        # Priority 3: Website improvements
        if website_gaps and website_gaps.suggested_pages:
            recommendations.append("Website improvements: " + website_gaps.suggested_pages[0])

        # Priority 4: Size-specific recommendations
        if org_size:
            if org_size.category in ["large", "major"]:
                if not any("Impact" in str(f.section) for f in findings):
                    pass  # Already has impact
                else:
                    recommendations.append("Add impact metrics and outcomes data (expected for organizations of your size)")

        # If no recommendations, add generic one
        if not recommendations:
            recommendations.append("Your llms.txt file is in good shape! Consider adding more detail to existing sections.")

        return recommendations[:5]  # Limit to top 5 recommendations
