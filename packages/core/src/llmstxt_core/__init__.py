"""llmstxt-core: Core library for generating and assessing llms.txt files."""

__version__ = "0.2.0"

# Main functionality exports
from llmstxt_core.crawler import crawl_site, CrawlResult
from llmstxt_core.crawler_playwright import crawl_site_with_playwright
from llmstxt_core.extractor import extract_content, ExtractedPage, PageType
from llmstxt_core.analyzer import (
    analyze_organisation,
    OrganisationAnalysis,
    PublicSectorAnalysis,
    StartupAnalysis,
)
from llmstxt_core.generator import (
    generate_llmstxt,
    generate_charity_llmstxt,
    generate_funder_llmstxt,
    generate_public_sector_llmstxt,
    generate_startup_llmstxt,
)
from llmstxt_core.validator import validate_llmstxt, ValidationResult, ValidationLevel
from llmstxt_core.assessor import (
    LLMSTxtAssessor,
    AssessmentResult,
    AssessmentFinding,
    IssueSeverity,
)

__all__ = [
    "__version__",
    # Crawling
    "crawl_site",
    "crawl_site_with_playwright",
    "CrawlResult",
    # Extraction
    "extract_content",
    "ExtractedPage",
    "PageType",
    # Analysis
    "analyze_organisation",
    "OrganisationAnalysis",
    "PublicSectorAnalysis",
    "StartupAnalysis",
    # Generation
    "generate_llmstxt",
    "generate_charity_llmstxt",
    "generate_funder_llmstxt",
    "generate_public_sector_llmstxt",
    "generate_startup_llmstxt",
    # Validation
    "validate_llmstxt",
    "ValidationResult",
    "ValidationLevel",
    # Assessment
    "LLMSTxtAssessor",
    "AssessmentResult",
    "AssessmentFinding",
    "IssueSeverity",
]
