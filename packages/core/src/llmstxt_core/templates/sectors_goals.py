"""Sector and goal definitions for each template type.

This module defines the available sectors (sub-categories) and goals (primary objectives)
for each template type. These are used to customize llms.txt generation and assessment.
"""

from typing import TypedDict


class SectorOption(TypedDict):
    """A sector option for a template."""
    id: str
    label: str
    description: str


class GoalOption(TypedDict):
    """A goal option for a template."""
    id: str
    label: str
    prompt_context: str  # How this goal affects AI prompt generation


# =============================================================================
# CHARITY SECTORS AND GOALS
# =============================================================================

CHARITY_SECTORS: list[SectorOption] = [
    {"id": "general", "label": "General", "description": "General charity or VCSE organisation"},
    {"id": "housing", "label": "Housing & Homelessness", "description": "Housing support, homelessness prevention, and shelter services"},
    {"id": "climate", "label": "Climate & Environment", "description": "Environmental conservation, climate action, and sustainability"},
    {"id": "young_people", "label": "Young People", "description": "Youth services, education support, and young people's wellbeing"},
    {"id": "older_people", "label": "Older People", "description": "Services for older adults, age-related support, and social care"},
    {"id": "mental_health", "label": "Mental Health", "description": "Mental health support, counselling, and psychological wellbeing"},
    {"id": "disability", "label": "Disability", "description": "Disability support, advocacy, and accessibility services"},
    {"id": "education", "label": "Education & Training", "description": "Educational services, skills development, and learning support"},
    {"id": "arts_culture", "label": "Arts & Culture", "description": "Arts organisations, cultural heritage, and creative projects"},
    {"id": "animals", "label": "Animals & Wildlife", "description": "Animal welfare, wildlife conservation, and rescue services"},
    {"id": "international", "label": "International Development", "description": "International aid, development projects, and humanitarian work"},
    {"id": "health", "label": "Health & Medical", "description": "Health services, medical research, and patient support"},
    {"id": "community", "label": "Community Development", "description": "Community centres, neighbourhood projects, and local initiatives"},
    {"id": "faith", "label": "Faith & Religion", "description": "Faith-based organisations and religious charities"},
    {"id": "legal_advice", "label": "Legal & Advice", "description": "Legal aid, citizens advice, and advocacy services"},
]

CHARITY_GOALS: list[GoalOption] = [
    {
        "id": "more_donors",
        "label": "Attract More Donors",
        "prompt_context": "Emphasize impact metrics, transparency, and how donations make a difference. Highlight success stories and clear funding needs."
    },
    {
        "id": "more_service_users",
        "label": "Reach More Service Users",
        "prompt_context": "Make services easy to understand and find. Clearly explain eligibility, referral pathways, and how to access help. Remove barriers to engagement."
    },
    {
        "id": "more_volunteers",
        "label": "Recruit More Volunteers",
        "prompt_context": "Highlight volunteering opportunities, the impact volunteers make, and what the experience is like. Include practical details about commitment and support provided."
    },
    {
        "id": "partnerships",
        "label": "Build Partnerships",
        "prompt_context": "Showcase collaboration opportunities, track record of partnerships, and mutual benefits. Highlight expertise and unique capabilities."
    },
    {
        "id": "awareness",
        "label": "Raise Awareness",
        "prompt_context": "Focus on mission clarity, the problem being addressed, and compelling impact stories. Make the cause easy to understand and share."
    },
    {
        "id": "funding_applications",
        "label": "Strengthen Funding Applications",
        "prompt_context": "Ensure clear governance, impact measurement, financial transparency, and evidence of need. Make it easy for funders to assess suitability."
    },
]


# =============================================================================
# STARTUP SECTORS AND GOALS
# =============================================================================

STARTUP_SECTORS: list[SectorOption] = [
    {"id": "general", "label": "General", "description": "General startup or tech company"},
    {"id": "technology_saas", "label": "Technology / SaaS", "description": "Software-as-a-Service and technology platforms"},
    {"id": "ai_ml", "label": "AI & Machine Learning", "description": "Artificial intelligence and machine learning products"},
    {"id": "b2b_services", "label": "B2B Services", "description": "Business-to-business services and enterprise solutions"},
    {"id": "consumer", "label": "Consumer Products", "description": "Consumer-facing products and D2C brands"},
    {"id": "health_medtech", "label": "Health & Medtech", "description": "Healthcare technology and medical devices"},
    {"id": "fintech", "label": "Fintech", "description": "Financial technology and payment solutions"},
    {"id": "ecommerce", "label": "E-commerce", "description": "Online retail, marketplaces, and commerce platforms"},
    {"id": "edtech", "label": "Edtech", "description": "Educational technology and learning platforms"},
    {"id": "cleantech", "label": "Cleantech & Climate", "description": "Clean technology and climate solutions"},
    {"id": "hardware", "label": "Hardware & IoT", "description": "Physical products, devices, and IoT solutions"},
    {"id": "marketplace", "label": "Marketplace", "description": "Two-sided marketplaces and platform businesses"},
]

STARTUP_GOALS: list[GoalOption] = [
    {
        "id": "more_customers",
        "label": "Acquire More Customers",
        "prompt_context": "Emphasize product benefits, use cases, and customer success stories. Make the value proposition crystal clear and highlight competitive advantages."
    },
    {
        "id": "investor_interest",
        "label": "Attract Investors",
        "prompt_context": "Highlight traction metrics, market opportunity, team credentials, and growth potential. Include funding stage and what makes this investment compelling."
    },
    {
        "id": "partnerships",
        "label": "Build Partnerships",
        "prompt_context": "Focus on integration capabilities, API availability, and partner benefits. Showcase existing partnerships and collaboration opportunities."
    },
    {
        "id": "talent",
        "label": "Attract Talent",
        "prompt_context": "Showcase company culture, mission, growth opportunities, and what makes working here special. Highlight the team and tech stack."
    },
    {
        "id": "brand_awareness",
        "label": "Build Brand Awareness",
        "prompt_context": "Focus on unique value proposition, thought leadership, and market positioning. Make the brand memorable and differentiated."
    },
    {
        "id": "enterprise_sales",
        "label": "Enterprise Sales",
        "prompt_context": "Emphasize security, compliance, scalability, and enterprise features. Include case studies and ROI metrics relevant to enterprise buyers."
    },
]


# =============================================================================
# FUNDER SECTORS AND GOALS
# =============================================================================

FUNDER_SECTORS: list[SectorOption] = [
    {"id": "general", "label": "General", "description": "General funder or foundation"},
    {"id": "corporate", "label": "Corporate Foundation", "description": "Corporate philanthropic foundation or CSR programme"},
    {"id": "family", "label": "Family Foundation", "description": "Private family foundation"},
    {"id": "community", "label": "Community Foundation", "description": "Community-based foundation serving a geographic area"},
    {"id": "government", "label": "Government Grants", "description": "Government funding programmes and public grants"},
    {"id": "lottery", "label": "Lottery Funding", "description": "National lottery and similar public funding bodies"},
    {"id": "trust", "label": "Charitable Trust", "description": "Independent charitable trust"},
    {"id": "philanthropy", "label": "Philanthropic Network", "description": "Philanthropic network or giving circle"},
]

FUNDER_GOALS: list[GoalOption] = [
    {
        "id": "quality_applications",
        "label": "Receive Quality Applications",
        "prompt_context": "Clearly explain eligibility criteria, what makes a strong application, and common reasons for rejection. Help applicants self-select appropriately."
    },
    {
        "id": "diverse_applicants",
        "label": "Attract Diverse Applicants",
        "prompt_context": "Emphasize accessibility of the application process, support available for first-time applicants, and commitment to equity. Remove jargon and barriers."
    },
    {
        "id": "impact_measurement",
        "label": "Improve Impact Measurement",
        "prompt_context": "Clearly explain reporting requirements, outcomes framework, and how impact will be measured. Set clear expectations for grantees."
    },
    {
        "id": "funding_awareness",
        "label": "Increase Funding Awareness",
        "prompt_context": "Make funding opportunities easy to discover and understand. Highlight the range of support available and upcoming deadlines."
    },
    {
        "id": "strategic_alignment",
        "label": "Find Strategic Alignment",
        "prompt_context": "Clearly articulate funding priorities, theory of change, and strategic focus areas. Help potential grantees understand fit."
    },
]


# =============================================================================
# PUBLIC SECTOR SECTORS AND GOALS
# =============================================================================

PUBLIC_SECTOR_SECTORS: list[SectorOption] = [
    {"id": "general", "label": "General", "description": "General public sector organisation"},
    {"id": "local_authority", "label": "Local Authority", "description": "Council, borough, or local government"},
    {"id": "nhs_health", "label": "NHS & Health", "description": "NHS trusts, CCGs, and health services"},
    {"id": "education", "label": "Education", "description": "Schools, colleges, universities, and education bodies"},
    {"id": "transport", "label": "Transport", "description": "Transport authorities and infrastructure"},
    {"id": "housing", "label": "Housing", "description": "Housing authorities and registered providers"},
    {"id": "emergency_services", "label": "Emergency Services", "description": "Police, fire, ambulance, and emergency response"},
    {"id": "regulatory", "label": "Regulatory Body", "description": "Regulators, inspectorates, and oversight bodies"},
    {"id": "cultural", "label": "Cultural Institution", "description": "Museums, libraries, and cultural organisations"},
]

PUBLIC_SECTOR_GOALS: list[GoalOption] = [
    {
        "id": "service_uptake",
        "label": "Increase Service Uptake",
        "prompt_context": "Make services easy to find, understand, and access. Clearly explain eligibility and how to apply. Reduce barriers to engagement."
    },
    {
        "id": "public_engagement",
        "label": "Improve Public Engagement",
        "prompt_context": "Encourage participation, feedback, and community involvement. Make it easy for residents to have their say and get involved."
    },
    {
        "id": "compliance",
        "label": "Ensure Compliance",
        "prompt_context": "Highlight regulatory requirements, legal obligations, and compliance information. Make mandatory information clear and accessible."
    },
    {
        "id": "efficiency",
        "label": "Improve Efficiency",
        "prompt_context": "Streamline information for self-service and reduce unnecessary contact. Help users find answers quickly and complete tasks independently."
    },
    {
        "id": "transparency",
        "label": "Increase Transparency",
        "prompt_context": "Provide clear information about decision-making, spending, and performance. Support accountability and public trust."
    },
]


# =============================================================================
# MASTER LOOKUPS
# =============================================================================

TEMPLATE_SECTORS: dict[str, list[SectorOption]] = {
    "charity": CHARITY_SECTORS,
    "funder": FUNDER_SECTORS,
    "public_sector": PUBLIC_SECTOR_SECTORS,
    "startup": STARTUP_SECTORS,
}

TEMPLATE_GOALS: dict[str, list[GoalOption]] = {
    "charity": CHARITY_GOALS,
    "funder": FUNDER_GOALS,
    "public_sector": PUBLIC_SECTOR_GOALS,
    "startup": STARTUP_GOALS,
}

# Default values
DEFAULT_SECTOR = "general"

DEFAULT_GOALS: dict[str, str] = {
    "charity": "awareness",
    "funder": "quality_applications",
    "public_sector": "service_uptake",
    "startup": "more_customers",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_sectors_for_template(template: str) -> list[SectorOption]:
    """Get available sectors for a template type.

    Args:
        template: Template type (charity, funder, public_sector, startup)

    Returns:
        List of sector options for the template
    """
    return TEMPLATE_SECTORS.get(template, CHARITY_SECTORS)


def get_goals_for_template(template: str) -> list[GoalOption]:
    """Get available goals for a template type.

    Args:
        template: Template type (charity, funder, public_sector, startup)

    Returns:
        List of goal options for the template
    """
    return TEMPLATE_GOALS.get(template, CHARITY_GOALS)


def get_sector_by_id(template: str, sector_id: str) -> SectorOption | None:
    """Look up a sector by its ID.

    Args:
        template: Template type
        sector_id: Sector ID to find

    Returns:
        Sector option if found, None otherwise
    """
    sectors = get_sectors_for_template(template)
    return next((s for s in sectors if s["id"] == sector_id), None)


def get_goal_by_id(template: str, goal_id: str) -> GoalOption | None:
    """Look up a goal by its ID.

    Args:
        template: Template type
        goal_id: Goal ID to find

    Returns:
        Goal option if found, None otherwise
    """
    goals = get_goals_for_template(template)
    return next((g for g in goals if g["id"] == goal_id), None)


def get_default_goal(template: str) -> str:
    """Get the default goal for a template type.

    Args:
        template: Template type

    Returns:
        Default goal ID for the template
    """
    return DEFAULT_GOALS.get(template, "awareness")


def validate_sector(template: str, sector_id: str) -> bool:
    """Check if a sector ID is valid for a template.

    Args:
        template: Template type
        sector_id: Sector ID to validate

    Returns:
        True if valid, False otherwise
    """
    return get_sector_by_id(template, sector_id) is not None


def validate_goal(template: str, goal_id: str) -> bool:
    """Check if a goal ID is valid for a template.

    Args:
        template: Template type
        goal_id: Goal ID to validate

    Returns:
        True if valid, False otherwise
    """
    return get_goal_by_id(template, goal_id) is not None
