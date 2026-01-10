"""LLM-based content analysis for organisations."""

import json
import os
from dataclasses import dataclass
from anthropic import Anthropic
from dotenv import load_dotenv

from .extractor import ExtractedPage

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


async def analyze_organisation(
    pages: list[ExtractedPage],
    template: str = "charity",
    model: str = "claude-sonnet-4-20250514",
    api_key: str | None = None
) -> OrganisationAnalysis | FunderAnalysis:
    """
    Use Claude to analyze the extracted pages and produce structured data.

    Args:
        pages: List of extracted pages from the website
        template: "charity" or "funder"
        model: Claude model to use
        api_key: Anthropic API key (or will use env var)

    Returns:
        OrganisationAnalysis or FunderAnalysis depending on template
    """
    # Get API key
    if api_key is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

    # Prepare the content for Claude
    content = _prepare_content(pages)

    # Choose system prompt
    system_prompt = CHARITY_SYSTEM_PROMPT if template == "charity" else FUNDER_SYSTEM_PROMPT

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
            beneficiaries=data["beneficiaries"],
            themes=data.get("themes", []),
            contact=data.get("contact", {}),
            team_info=data.get("team_info"),
            ai_guidance=data.get("ai_guidance", [])
        )
    else:  # funder
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


def _prepare_content(pages: list[ExtractedPage]) -> str:
    """Prepare page content for Claude analysis."""
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
            content_parts.append(f"\n### {page.title}\n")
            content_parts.append(f"URL: {page.url}\n")

            if page.description:
                content_parts.append(f"Description: {page.description}\n")

            if page.headings:
                content_parts.append(f"Headings: {', '.join(page.headings[:5])}\n")

            # Include first 1500 chars of body text
            body_snippet = page.body_text[:1500]
            if len(page.body_text) > 1500:
                body_snippet += "..."

            content_parts.append(f"Content: {body_snippet}\n")

            if page.contact_info:
                content_parts.append(f"Contact info found: {page.contact_info}\n")

            if page.charity_number:
                content_parts.append(f"Charity number found: {page.charity_number}\n")

    return "\n".join(content_parts)
