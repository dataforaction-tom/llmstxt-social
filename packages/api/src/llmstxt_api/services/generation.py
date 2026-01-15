"""Generation service using llmstxt-core."""

from anthropic import Anthropic

from llmstxt_core import (
    analyze_organisation,
    crawl_site,
    extract_content,
    generate_llmstxt,
)
from llmstxt_core.assessor import LLMSTxtAssessor
from llmstxt_core.enrichers.charity_commission import fetch_charity_data, find_charity_number
from llmstxt_api.config import settings


async def generate_llmstxt_from_url(
    url: str,
    template: str = "charity",
    max_pages: int = None,
) -> str:
    """
    Generate llms.txt content from a URL.

    Args:
        url: Website URL to crawl
        template: Template type (charity, funder, public_sector, startup)
        max_pages: Maximum pages to crawl (defaults to settings)

    Returns:
        Generated llms.txt content as string
    """
    if max_pages is None:
        max_pages = settings.max_crawl_pages

    # Crawl website
    crawl_result = await crawl_site(url, max_pages=max_pages)

    # Extract content from pages
    pages = [extract_content(page) for page in crawl_result.pages]

    # Analyze with Claude
    analysis = await analyze_organisation(pages, template, api_key=settings.anthropic_api_key)

    # Generate llms.txt
    llmstxt_content = generate_llmstxt(analysis, pages, template)

    return llmstxt_content


async def generate_with_enrichment(
    url: str,
    template: str = "charity",
    max_pages: int = None,
) -> tuple[str, dict | None]:
    """
    Generate llms.txt with enrichment data (paid tier).

    Args:
        url: Website URL to crawl
        template: Template type
        max_pages: Maximum pages to crawl

    Returns:
        Tuple of (llmstxt_content, enrichment_data)
    """
    if max_pages is None:
        max_pages = settings.max_crawl_pages

    # Crawl website
    crawl_result = await crawl_site(url, max_pages=max_pages)

    # Extract content
    pages = [extract_content(page) for page in crawl_result.pages]

    # Fetch enrichment data
    enrichment_data = None
    if template == "charity" and settings.charity_commission_api_key:
        # Try to find charity number
        charity_number = find_charity_number(pages)
        if charity_number:
            enrichment_data = await fetch_charity_data(
                charity_number, api_key=settings.charity_commission_api_key
            )

    # Analyze with Claude
    analysis = await analyze_organisation(pages, template, api_key=settings.anthropic_api_key)

    # Generate llms.txt
    llmstxt_content = generate_llmstxt(analysis, pages, template)

    return llmstxt_content, enrichment_data


async def assess_llmstxt(
    llmstxt_content: str,
    template: str,
    website_url: str | None = None,
    enrichment_data: dict | None = None,
) -> dict:
    """
    Assess llms.txt quality.

    Args:
        llmstxt_content: The llms.txt content to assess
        template: Template type
        website_url: Optional website URL for context
        enrichment_data: Optional enrichment data

    Returns:
        Assessment results as dict
    """
    client = Anthropic(api_key=settings.anthropic_api_key)
    assessor = LLMSTxtAssessor(template, client)

    # Run assessment
    assessment_result = await assessor.assess(
        llmstxt_content=llmstxt_content,
        website_url=website_url,
        enrichment_data=enrichment_data,
    )

    # Compute grade from overall score
    score = assessment_result.overall_score
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"

    # Convert to dict
    return {
        "overall_score": assessment_result.overall_score,
        "completeness_score": assessment_result.completeness_score,
        "quality_score": assessment_result.quality_score,
        "grade": grade,
        "findings": [
            {
                "category": f.category.value,
                "severity": f.severity.value,
                "message": f.message,
                "suggestion": f.suggestion,
            }
            for f in assessment_result.findings
        ],
        "recommendations": assessment_result.recommendations,
        "sections": [
            {
                "name": s.name,
                "present": s.present,
                "quality": s.quality,
                "issues": s.issues,
            }
            for s in assessment_result.section_assessments
        ],
        "website_gaps": (
            {
                "missing_page_types": assessment_result.website_gaps.missing_page_types,
                "has_sitemap": assessment_result.website_gaps.has_sitemap,
                "crawl_coverage": assessment_result.website_gaps.crawl_coverage,
            }
            if assessment_result.website_gaps
            else None
        ),
    }
