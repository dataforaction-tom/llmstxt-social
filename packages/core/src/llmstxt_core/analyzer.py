"""LLM-based content analysis for organisations."""

import json
import os
from dataclasses import dataclass
from anthropic import Anthropic
from dotenv import load_dotenv

from .extractor import ExtractedPage
from .templates.sectors_goals import get_sector_by_id, get_goal_by_id

# Load environment variables
load_dotenv()


@dataclass
class OrganisationAnalysis:
    """Analysis results for a charity/VCSE organisation."""
    name: str
    org_type: str
    registration_number: str | None
    mission: str
    description: str
    geographic_area: str
    services: list[dict]
    projects: list[dict] | None
    impact_metrics: dict | None
    beneficiaries: str
    themes: list[str]
    contact: dict
    team_info: str | None
    ai_guidance: list[str]


@dataclass
class FunderAnalysis:
    """Analysis results for a funder/foundation."""
    name: str
    funder_type: str
    registration_number: str | None
    mission: str
    description: str
    geographic_focus: str
    thematic_focus: list[str]
    programmes: list[dict]
    grant_sizes: dict
    who_can_apply: list[str]
    who_cannot_apply: list[str]
    application_process: str
    deadlines: str | None
    contact: dict
    success_factors: list[str]
    ai_guidance: list[str]


@dataclass
class PublicSectorAnalysis:
    """Analysis results for a public sector organisation."""
    name: str
    org_type: str
    governance: str | None
    mission: str
    description: str
    area_covered: str
    services: list[dict]
    contact: dict
    accessibility_info: str | None
    ai_guidance: list[str]


@dataclass
class StartupAnalysis:
    """Analysis results for a startup/tech company."""
    name: str
    mission: str
    description: str
    product_description: str
    target_customers: str
    business_model: str | None
    pricing_model: str | None
    stage: str | None
    funding_raised: str | None
    traction_metrics: dict | None
    team_highlights: str | None
    contact: dict
    ai_guidance: list[str]


CHARITY_SYSTEM_PROMPT = """You are analyzing a UK VCSE (voluntary, community, social enterprise) organisation's website to create an llms.txt file.

Given the extracted content from their website pages, identify and return as JSON:

{
  "name": "Full official name",
  "org_type": "charity|CIC|CIO|unincorporated|social_enterprise|other",
  "registration_number": "Charity/company number if found, else null",
  "mission": "One sentence primary mission",
  "description": "2-3 sentences expanding on mission, who they serve, what makes them distinctive",
  "geographic_area": "Area served (be specific - local authority, region, etc)",
  "services": [
    {"name": "Service name", "description": "What it is", "eligibility": "Who can access"}
  ],
  "projects": [
    {"name": "Project name", "description": "What the project does", "location": "Where it operates"}
  ],
  "impact_metrics": {
    "beneficiaries_served": "Number of people helped (if mentioned)",
    "outcomes": ["Key outcomes or achievements"]
  },
  "beneficiaries": "Who they primarily serve",
  "themes": ["theme1", "theme2"],
  "contact": {"email": "", "phone": "", "address": "", "hours": ""},
  "team_info": "Brief note on team size/structure if mentioned",
  "ai_guidance": [
    "Important things AI systems should know when representing this org",
    "E.g. preferred name, sensitive topics, common misconceptions"
  ]
}

Be concise. Extract only what's clearly stated - don't infer or hallucinate.
If information isn't available, use null.
Projects should be specific initiatives or programmes the charity runs.
Impact metrics should only include quantifiable outcomes if explicitly stated.
Themes should be broad categories like "homelessness", "mental health", "youth services", etc."""


FUNDER_SYSTEM_PROMPT = """You are analyzing a UK funder/foundation's website to create an llms.txt file.

Given the extracted content, identify and return as JSON:

{
  "name": "Full foundation/trust name",
  "funder_type": "independent|corporate|community|family|statutory",
  "registration_number": "Charity number if found",
  "mission": "One sentence on funding mission",
  "description": "2-3 sentences on approach, values, what makes them distinctive",
  "geographic_focus": "Where they fund",
  "thematic_focus": ["theme1", "theme2"],
  "programmes": [
    {"name": "Programme name", "description": "What it funds", "eligibility": "Who can apply"}
  ],
  "grant_sizes": {"min": null, "max": null, "typical": "typical range as string"},
  "who_can_apply": ["Registered charities", "CICs", etc],
  "who_cannot_apply": ["Individuals", "Organisations under 1 year old", etc],
  "application_process": "Brief description of how to apply",
  "deadlines": "Application deadlines if mentioned",
  "contact": {"email": "", "phone": "", "grants_contact": ""},
  "success_factors": [
    "What makes a strong application according to this funder"
  ],
  "ai_guidance": [
    "Important things AI should know - e.g. don't guarantee funding"
  ]
}

Be concise. Extract only what's clearly stated.
If information isn't available, use null."""


PUBLIC_SECTOR_SYSTEM_PROMPT = """You are analyzing a UK public sector organisation's website to create an llms.txt file.

Given the extracted content from their website pages, identify and return as JSON:

{
  "name": "Full organisation name",
  "org_type": "local_authority|nhs_trust|government_department|agency|other",
  "governance": "Brief governance structure if mentioned",
  "mission": "One sentence on their purpose/mission",
  "description": "2-3 sentences on what they do, area covered, who they serve",
  "area_covered": "Geographic area or jurisdiction",
  "services": [
    {"name": "Service name", "description": "What it provides", "eligibility": "Who can access", "category": "Service category"}
  ],
  "contact": {"email": "", "phone": "", "address": "", "hours": "", "departments": {}},
  "accessibility_info": "Information about accessibility, complaints procedures, or service standards if mentioned",
  "ai_guidance": [
    "Important things AI should know when representing this organisation",
    "E.g. how to direct urgent queries, service availability"
  ]
}

Be concise. Extract only what's clearly stated - don't infer or hallucinate.
If information isn't available, use null.
Services should be categorized where possible (e.g., "adult social care", "waste management", "planning").
Focus on practical service information that helps people access what they need."""


STARTUP_SYSTEM_PROMPT = """You are analyzing a startup/tech company's website to create an llms.txt file.

Given the extracted content from their website pages, identify and return as JSON:

{
  "name": "Company name",
  "mission": "One sentence mission or vision",
  "description": "2-3 sentences on what the company does and its unique value proposition",
  "product_description": "What the product/service is and who it's for",
  "target_customers": "Primary customer segments or personas",
  "business_model": "B2B|B2C|B2B2C|marketplace|SaaS|etc if clear",
  "pricing_model": "Brief pricing approach if publicly available (freemium, subscription, etc)",
  "stage": "pre-seed|seed|Series A|Series B|etc if mentioned",
  "funding_raised": "Total funding raised if mentioned",
  "traction_metrics": {
    "users": "User count if mentioned",
    "revenue": "Revenue info if public",
    "growth": "Growth metrics if mentioned",
    "customers": "Notable customers or case studies"
  },
  "team_highlights": "Brief note on founders/team if mentioned",
  "contact": {"email": "", "sales": "", "support": "", "investors": ""},
  "ai_guidance": [
    "Important things AI should know when representing this company",
    "E.g. correct product category, how to describe what they do"
  ]
}

Be concise. Extract only what's clearly stated - don't speculate about funding or metrics.
If information isn't available, use null.
Focus on information that would help customers understand the product and investors understand the opportunity."""


async def analyze_organisation(
    pages: list[ExtractedPage],
    template: str = "charity",
    sector: str = "general",
    goal: str | None = None,
    model: str = "claude-sonnet-4-20250514",
    api_key: str | None = None
) -> OrganisationAnalysis | FunderAnalysis | PublicSectorAnalysis | StartupAnalysis:
    """
    Use Claude to analyze the extracted pages and produce structured data.

    Args:
        pages: List of extracted pages from the website
        template: "charity", "funder", "public_sector", or "startup"
        sector: Sub-sector within template (e.g., "housing", "mental_health")
        goal: Primary goal (e.g., "more_donors", "more_customers")
        model: Claude model to use
        api_key: Anthropic API key (or will use env var)

    Returns:
        OrganisationAnalysis, FunderAnalysis, PublicSectorAnalysis, or StartupAnalysis depending on template
    """
    # Get API key
    if api_key is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

    # Prepare the content for Claude
    content = _prepare_content(pages)

    # Choose base system prompt
    prompt_map = {
        "charity": CHARITY_SYSTEM_PROMPT,
        "funder": FUNDER_SYSTEM_PROMPT,
        "public_sector": PUBLIC_SECTOR_SYSTEM_PROMPT,
        "startup": STARTUP_SYSTEM_PROMPT
    }
    system_prompt = prompt_map.get(template, CHARITY_SYSTEM_PROMPT)

    # Add sector context if not "general"
    if sector and sector != "general":
        sector_info = get_sector_by_id(template, sector)
        if sector_info:
            system_prompt += f"""

SECTOR CONTEXT: This is a {sector_info['label']} organisation. Pay special attention to:
- Sector-specific terminology and services relevant to {sector_info['description'].lower()}
- Common stakeholders and beneficiaries in this sector
- Typical services and programmes offered by {sector_info['label'].lower()} organisations"""

    # Add goal context
    if goal:
        goal_info = get_goal_by_id(template, goal)
        if goal_info:
            system_prompt += f"""

PRIMARY GOAL CONTEXT: This organisation wants to {goal_info['label'].lower()}.
{goal_info['prompt_context']}
Ensure the extracted information supports this goal and helps the llms.txt file be most useful for this purpose."""

    # Call Claude API
    client = Anthropic(api_key=api_key)

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": content
            }
        ]
    )

    # Parse the response
    response_text = message.content[0].text

    # Extract JSON from response (handle potential markdown code blocks)
    json_text = response_text
    if "```json" in response_text:
        json_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        json_text = response_text.split("```")[1].split("```")[0].strip()

    data = json.loads(json_text)

    # Convert to appropriate dataclass
    if template == "charity":
        return OrganisationAnalysis(
            name=data["name"],
            org_type=data["org_type"],
            registration_number=data.get("registration_number"),
            mission=data["mission"],
            description=data["description"],
            geographic_area=data["geographic_area"],
            services=data.get("services", []),
            projects=data.get("projects"),
            impact_metrics=data.get("impact_metrics"),
            beneficiaries=data["beneficiaries"],
            themes=data.get("themes", []),
            contact=data.get("contact", {}),
            team_info=data.get("team_info"),
            ai_guidance=data.get("ai_guidance", [])
        )
    elif template == "funder":
        return FunderAnalysis(
            name=data["name"],
            funder_type=data["funder_type"],
            registration_number=data.get("registration_number"),
            mission=data["mission"],
            description=data["description"],
            geographic_focus=data["geographic_focus"],
            thematic_focus=data.get("thematic_focus", []),
            programmes=data.get("programmes", []),
            grant_sizes=data.get("grant_sizes", {}),
            who_can_apply=data.get("who_can_apply", []),
            who_cannot_apply=data.get("who_cannot_apply", []),
            application_process=data.get("application_process", ""),
            deadlines=data.get("deadlines"),
            contact=data.get("contact", {}),
            success_factors=data.get("success_factors", []),
            ai_guidance=data.get("ai_guidance", [])
        )
    elif template == "public_sector":
        return PublicSectorAnalysis(
            name=data["name"],
            org_type=data["org_type"],
            governance=data.get("governance"),
            mission=data["mission"],
            description=data["description"],
            area_covered=data["area_covered"],
            services=data.get("services", []),
            contact=data.get("contact", {}),
            accessibility_info=data.get("accessibility_info"),
            ai_guidance=data.get("ai_guidance", [])
        )
    else:  # startup
        return StartupAnalysis(
            name=data["name"],
            mission=data["mission"],
            description=data["description"],
            product_description=data["product_description"],
            target_customers=data["target_customers"],
            business_model=data.get("business_model"),
            pricing_model=data.get("pricing_model"),
            stage=data.get("stage"),
            funding_raised=data.get("funding_raised"),
            traction_metrics=data.get("traction_metrics"),
            team_highlights=data.get("team_highlights"),
            contact=data.get("contact", {}),
            ai_guidance=data.get("ai_guidance", [])
        )


def _prepare_content(pages: list[ExtractedPage]) -> str:
    """Prepare page content for Claude analysis."""
    if not pages:
        return "No pages were successfully crawled from this website. Please analyze based on any available context."

    content_parts = []

    # Group pages by type for better organization
    pages_by_type = {}
    for page in pages:
        page_type = page.page_type.value
        if page_type not in pages_by_type:
            pages_by_type[page_type] = []
        pages_by_type[page_type].append(page)

    # Add content for each page type
    for page_type, type_pages in pages_by_type.items():
        content_parts.append(f"\n## {page_type.upper()} PAGES\n")

        for page in type_pages:
            content_parts.append(f"\n### {page.title or 'Untitled'}\n")
            content_parts.append(f"URL: {page.url}\n")

            if page.description:
                content_parts.append(f"Description: {page.description}\n")

            if page.headings:
                content_parts.append(f"Headings: {', '.join(page.headings[:5])}\n")

            # Include first 1500 chars of body text
            body_text = page.body_text or ""
            body_snippet = body_text[:1500]
            if len(body_text) > 1500:
                body_snippet += "..."

            if body_snippet.strip():
                content_parts.append(f"Content: {body_snippet}\n")

            if page.contact_info:
                content_parts.append(f"Contact info found: {page.contact_info}\n")

            if page.charity_number:
                content_parts.append(f"Charity number found: {page.charity_number}\n")

    result = "\n".join(content_parts)
    # Ensure we never return empty content
    if not result.strip():
        return "No content could be extracted from the crawled pages. Please provide a basic analysis."

    return result
