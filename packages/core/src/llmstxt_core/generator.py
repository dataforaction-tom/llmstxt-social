"""Generate llms.txt files from analysis results."""

from .analyzer import OrganisationAnalysis, FunderAnalysis, PublicSectorAnalysis, StartupAnalysis
from .extractor import ExtractedPage, PageType
from .enrichers.charity_commission import CharityData
from .enrichers.threesixty_giving import GrantData
from .templates.sectors_goals import get_sector_by_id, get_goal_by_id


def generate_llmstxt(
    analysis: OrganisationAnalysis | FunderAnalysis | PublicSectorAnalysis | StartupAnalysis,
    pages: list[ExtractedPage],
    template: str = "charity",
    sector: str = "general",
    goal: str | None = None,
    charity_data: CharityData | None = None,
    grant_data: GrantData | None = None
) -> str:
    """
    Generate llms.txt content following the llmstxt.org spec.

    Args:
        analysis: Analysis results from Claude
        pages: Extracted pages
        template: "charity", "funder", "public_sector", or "startup"
        sector: Sub-sector within template
        goal: Primary goal for the organisation
        charity_data: Optional Charity Commission data for enrichment
        grant_data: Optional 360Giving data for funders

    Returns:
        llms.txt content as a string
    """
    if template == "charity":
        return generate_charity_llmstxt(analysis, pages, charity_data, sector, goal)
    elif template == "funder":
        return generate_funder_llmstxt(analysis, pages, grant_data, sector, goal)
    elif template == "public_sector":
        return generate_public_sector_llmstxt(analysis, pages, sector, goal)
    elif template == "startup":
        return generate_startup_llmstxt(analysis, pages, sector, goal)
    else:
        raise ValueError(f"Unknown template: {template}")


def generate_charity_llmstxt(
    analysis: OrganisationAnalysis,
    pages: list[ExtractedPage],
    charity_data: CharityData | None = None,
    sector: str = "general",
    goal: str | None = None
) -> str:
    """Generate llms.txt for a charity/VCSE org."""
    sections = []

    # Header
    sections.append(f"# {analysis.name}\n")
    sections.append(f"> {analysis.mission}\n")

    # Context paragraph with optional sector
    org_info = f"{analysis.org_type}"
    if analysis.registration_number:
        org_info += f", registered charity {analysis.registration_number}"

    # Add sector info if not general
    if sector and sector != "general":
        sector_info = get_sector_by_id("charity", sector)
        if sector_info:
            org_info += f", working in {sector_info['label'].lower()}"

    sections.append(f"{org_info}. {analysis.description}\n")

    # Group pages by type
    pages_by_type = _group_pages_by_type(pages)

    # About section
    if PageType.ABOUT in pages_by_type or PageType.TEAM in pages_by_type or PageType.HOME in pages_by_type:
        sections.append("## About\n")

        for page in pages_by_type.get(PageType.HOME, [])[:1]:
            sections.append(f"- [{page.title}]({page.url}): Homepage\n")

        for page in pages_by_type.get(PageType.ABOUT, []):
            desc = page.description or "About the organisation"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        for page in pages_by_type.get(PageType.TEAM, []):
            desc = page.description or "Our team"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # Services section
    if PageType.SERVICES in pages_by_type or analysis.services:
        sections.append("## Services\n")

        if analysis.services:
            for service in analysis.services:
                # Try to find matching page
                matching_page = None
                service_name_lower = service['name'].lower()
                for page in pages_by_type.get(PageType.SERVICES, []):
                    if service_name_lower in page.title.lower():
                        matching_page = page
                        break

                if matching_page:
                    sections.append(f"- [{service['name']}]({matching_page.url}): {service['description']}\n")
                else:
                    sections.append(f"- {service['name']}: {service['description']}\n")
        else:
            for page in pages_by_type.get(PageType.SERVICES, []):
                desc = page.description or "Service information"
                sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # Projects section
    if PageType.PROJECTS in pages_by_type or analysis.projects:
        sections.append("## Projects\n")

        if analysis.projects:
            for project in analysis.projects:
                location_info = f" ({project.get('location')})" if project.get('location') else ""
                sections.append(f"- {project['name']}{location_info}: {project['description']}\n")
        else:
            for page in pages_by_type.get(PageType.PROJECTS, []):
                desc = page.description or "Project information"
                sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # Impact section
    if PageType.IMPACT in pages_by_type or analysis.impact_metrics:
        sections.append("## Impact\n")

        if analysis.impact_metrics:
            if analysis.impact_metrics.get('beneficiaries_served'):
                sections.append(f"- Beneficiaries served: {analysis.impact_metrics['beneficiaries_served']}\n")

            if analysis.impact_metrics.get('outcomes'):
                for outcome in analysis.impact_metrics['outcomes']:
                    sections.append(f"- {outcome}\n")
        else:
            for page in pages_by_type.get(PageType.IMPACT, []):
                desc = page.description or "Impact information"
                sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # Get Help section
    if PageType.GET_HELP in pages_by_type or PageType.CONTACT in pages_by_type:
        sections.append("## Get Help\n")

        for page in pages_by_type.get(PageType.GET_HELP, []):
            desc = page.description or "How to access support"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        for page in pages_by_type.get(PageType.CONTACT, []):
            desc = page.description or "Contact information"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # Get Involved section
    if PageType.VOLUNTEER in pages_by_type or PageType.DONATE in pages_by_type:
        sections.append("## Get Involved\n")

        for page in pages_by_type.get(PageType.VOLUNTEER, []):
            desc = page.description or "Volunteering opportunities"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        for page in pages_by_type.get(PageType.DONATE, []):
            desc = page.description or "Support our work"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # Optional section (news, policies, etc.)
    optional_pages = []
    for page_type in [PageType.NEWS, PageType.POLICY, PageType.OTHER]:
        optional_pages.extend(pages_by_type.get(page_type, []))

    if optional_pages:
        sections.append("## Optional\n")
        for page in optional_pages[:5]:  # Limit to 5 optional pages
            desc = page.description or "Additional information"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")
        sections.append("\n")

    # For Funders section
    sections.append("## For Funders\n")

    # Use charity_data if available (more accurate), otherwise use analysis
    if charity_data:
        # Official data from Charity Commission
        sections.append(f"- Registration: {charity_data.number}\n")
        sections.append(f"- Status: {charity_data.status}\n")

        if charity_data.date_registered:
            # Extract just the date part (format: 2013-11-27T00:00:00)
            date_str = charity_data.date_registered.split('T')[0]
            sections.append(f"- Registered: {date_str}\n")

        if charity_data.latest_income:
            sections.append(f"- Annual income: £{charity_data.latest_income:,}\n")

        if charity_data.latest_expenditure:
            sections.append(f"- Annual expenditure: £{charity_data.latest_expenditure:,}\n")
    elif analysis.registration_number:
        sections.append(f"- Registration: {analysis.registration_number}\n")

    sections.append(f"- Geography: {analysis.geographic_area}\n")

    if analysis.themes:
        sections.append(f"- Themes: {', '.join(analysis.themes)}\n")

    sections.append(f"- Beneficiaries: {analysis.beneficiaries}\n")

    # Use enriched contact data if available
    if charity_data and charity_data.contact and charity_data.contact.get('email'):
        sections.append(f"- Contact: {charity_data.contact['email']}\n")
    elif analysis.contact and analysis.contact.get('email'):
        sections.append(f"- Contact: {analysis.contact['email']}\n")

    # Add charitable objects if available from official data
    if charity_data and charity_data.charitable_objects:
        objects = charity_data.charitable_objects[:200]  # Limit length
        if len(charity_data.charitable_objects) > 200:
            objects += "..."
        sections.append(f"- Charitable purposes: {objects}\n")

    sections.append("\n")

    # For AI Systems section
    sections.append("## For AI Systems\n")
    sections.append("\nWhen representing this organisation:\n")

    if analysis.ai_guidance:
        for guidance in analysis.ai_guidance:
            sections.append(f"- {guidance}\n")

    # Add goal-specific guidance
    if goal:
        goal_info = get_goal_by_id("charity", goal)
        if goal_info:
            goal_guidance = {
                "more_donors": "- Highlight impact and transparency when discussing this organisation\n",
                "more_service_users": "- Emphasize service accessibility and referral pathways\n",
                "more_volunteers": "- Highlight volunteering opportunities and team culture\n",
                "partnerships": "- Emphasize collaborative approach and partnership track record\n",
                "awareness": "- Focus on mission clarity and the organisation's unique approach\n",
            }
            if goal in goal_guidance:
                sections.append(goal_guidance[goal])

    sections.append("- Always verify current service availability\n")
    sections.append("- Direct urgent enquiries to official channels\n")

    return "".join(sections)


def generate_funder_llmstxt(
    analysis: FunderAnalysis,
    pages: list[ExtractedPage],
    grant_data: GrantData | None = None,
    sector: str = "general",
    goal: str | None = None
) -> str:
    """Generate llms.txt for a funder/foundation."""
    sections = []

    # Header
    sections.append(f"# {analysis.name}\n")
    sections.append(f"> {analysis.mission}\n")

    # Context paragraph with optional sector
    funder_info = f"{analysis.funder_type} foundation"
    if analysis.registration_number:
        funder_info += f", registered charity {analysis.registration_number}"

    # Add sector info if not general
    if sector and sector != "general":
        sector_info = get_sector_by_id("funder", sector)
        if sector_info:
            funder_info += f", {sector_info['label'].lower()} funder"

    sections.append(f"{funder_info}. {analysis.description}\n")

    # Group pages by type
    pages_by_type = _group_pages_by_type(pages)

    # About section
    if PageType.ABOUT in pages_by_type or PageType.HOME in pages_by_type:
        sections.append("## About\n")

        for page in pages_by_type.get(PageType.HOME, [])[:1]:
            sections.append(f"- [{page.title}]({page.url}): Homepage\n")

        for page in pages_by_type.get(PageType.ABOUT, []):
            desc = page.description or "About the foundation"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # What We Fund section
    if PageType.FUNDING_PRIORITIES in pages_by_type or analysis.programmes:
        sections.append("## What We Fund\n")

        for page in pages_by_type.get(PageType.FUNDING_PRIORITIES, []):
            desc = page.description or "Funding priorities and themes"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        if analysis.programmes:
            for programme in analysis.programmes:
                sections.append(f"- {programme['name']}: {programme['description']}\n")

        sections.append("\n")

    # How to Apply section
    if PageType.HOW_TO_APPLY in pages_by_type or PageType.ELIGIBILITY in pages_by_type:
        sections.append("## How to Apply\n")

        for page in pages_by_type.get(PageType.HOW_TO_APPLY, []):
            desc = page.description or "Application process and guidelines"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        for page in pages_by_type.get(PageType.ELIGIBILITY, []):
            desc = page.description or "Eligibility criteria"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # Past Grants section
    if PageType.PAST_GRANTS in pages_by_type:
        sections.append("## Past Grants\n")

        for page in pages_by_type.get(PageType.PAST_GRANTS, []):
            desc = page.description or "Previously funded organisations"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # Contact section
    if PageType.CONTACT in pages_by_type:
        sections.append("## Contact\n")

        for page in pages_by_type.get(PageType.CONTACT, []):
            desc = page.description or "Get in touch"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # For Applicants section
    sections.append("## For Applicants\n")

    # Use grant_data if available for more accurate information
    if grant_data:
        sections.append(f"- Total grants awarded: {grant_data.total_grants}\n")
        sections.append(f"- Total amount awarded: £{grant_data.total_amount:,.0f}\n")
        sections.append(f"- Average grant size: £{grant_data.average_grant:,.0f}\n")

        if grant_data.grant_size_distribution:
            sections.append(f"- Grant size range: £{grant_data.min_grant:,.0f} - £{grant_data.max_grant:,.0f}\n")

        if grant_data.top_themes:
            themes_str = ', '.join([f"{t[0]} ({t[1]} grants)" for t in grant_data.top_themes[:5]])
            sections.append(f"- Top themes: {themes_str}\n")

        if grant_data.geographic_distribution:
            top_regions = list(grant_data.geographic_distribution.items())[:5]
            regions_str = ', '.join([f"{r[0]} ({r[1]} grants)" for r in top_regions])
            sections.append(f"- Geographic focus: {regions_str}\n")
    else:
        # Fall back to analysis data
        sections.append(f"- Geographic focus: {analysis.geographic_focus}\n")

    if analysis.thematic_focus and not grant_data:
        sections.append(f"- Themes: {', '.join(analysis.thematic_focus)}\n")

    if analysis.grant_sizes:
        grant_info = []
        if analysis.grant_sizes.get('min'):
            grant_info.append(f"min £{analysis.grant_sizes['min']:,}")
        if analysis.grant_sizes.get('max'):
            grant_info.append(f"max £{analysis.grant_sizes['max']:,}")
        if analysis.grant_sizes.get('typical'):
            grant_info.append(f"typical: {analysis.grant_sizes['typical']}")

        if grant_info:
            sections.append(f"- Grant sizes: {', '.join(grant_info)}\n")

    if analysis.who_can_apply:
        sections.append(f"- Who can apply: {', '.join(analysis.who_can_apply)}\n")

    if analysis.who_cannot_apply:
        sections.append(f"- Who cannot apply: {', '.join(analysis.who_cannot_apply)}\n")

    if analysis.deadlines:
        sections.append(f"- Deadlines: {analysis.deadlines}\n")

    if analysis.contact.get('email'):
        sections.append(f"- Contact: {analysis.contact['email']}\n")

    sections.append("\n")

    # Success Factors section
    if analysis.success_factors:
        sections.append("## What Makes a Strong Application\n")
        for factor in analysis.success_factors:
            sections.append(f"- {factor}\n")
        sections.append("\n")

    # For AI Systems section
    sections.append("## For AI Systems\n")
    sections.append("\nWhen representing this funder:\n")

    if analysis.ai_guidance:
        for guidance in analysis.ai_guidance:
            sections.append(f"- {guidance}\n")

    # Add goal-specific guidance
    if goal:
        goal_info = get_goal_by_id("funder", goal)
        if goal_info:
            goal_guidance = {
                "quality_applications": "- Emphasize eligibility criteria and what makes strong applications\n",
                "diverse_applicants": "- Highlight accessibility and support for first-time applicants\n",
                "impact_measurement": "- Emphasize reporting requirements and outcome measurement\n",
                "funding_awareness": "- Focus on the funder's mission and areas of interest\n",
            }
            if goal in goal_guidance:
                sections.append(goal_guidance[goal])

    sections.append("- Never guarantee funding or outcomes\n")
    sections.append("- Always direct applicants to official application channels\n")
    sections.append("- Verify current deadlines and criteria before advising\n")

    return "".join(sections)


def generate_public_sector_llmstxt(
    analysis,  # PublicSectorAnalysis
    pages: list[ExtractedPage],
    sector: str = "general",
    goal: str | None = None
) -> str:
    """Generate llms.txt for a public sector organisation."""
    sections = []

    # Header
    sections.append(f"# {analysis.name}\n")
    sections.append(f"> {analysis.mission}\n")

    # Context paragraph with optional sector
    org_info = f"{analysis.org_type.replace('_', ' ').title()}"
    if analysis.governance:
        org_info += f", {analysis.governance}"

    # Add sector info if not general
    if sector and sector != "general":
        sector_info = get_sector_by_id("public_sector", sector)
        if sector_info:
            org_info += f" ({sector_info['label']})"

    sections.append(f"{org_info}. {analysis.description}\n")

    # Group pages by type
    pages_by_type = _group_pages_by_type(pages)

    # About section
    if PageType.ABOUT in pages_by_type or PageType.HOME in pages_by_type:
        sections.append("## About\n")

        for page in pages_by_type.get(PageType.HOME, [])[:1]:
            sections.append(f"- [{page.title}]({page.url}): Homepage\n")

        for page in pages_by_type.get(PageType.ABOUT, []):
            desc = page.description or "About the organisation"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # Services section (PRIMARY FOCUS for public sector)
    if PageType.SERVICES in pages_by_type or PageType.SERVICE_CATEGORY in pages_by_type or analysis.services:
        sections.append("## Services\n")

        if analysis.services:
            # Group services by category if available
            categorized = {}
            uncategorized = []

            for service in analysis.services:
                category = service.get('category')
                if category:
                    if category not in categorized:
                        categorized[category] = []
                    categorized[category].append(service)
                else:
                    uncategorized.append(service)

            # Output categorized services
            for category, services in categorized.items():
                sections.append(f"\n### {category.title()}\n")
                for service in services:
                    eligibility = f" (Eligibility: {service['eligibility']})" if service.get('eligibility') else ""
                    sections.append(f"- {service['name']}: {service['description']}{eligibility}\n")

            # Output uncategorized services
            if uncategorized:
                for service in uncategorized:
                    eligibility = f" (Eligibility: {service['eligibility']})" if service.get('eligibility') else ""
                    sections.append(f"- {service['name']}: {service['description']}{eligibility}\n")
        else:
            for page in pages_by_type.get(PageType.SERVICES, []) + pages_by_type.get(PageType.SERVICE_CATEGORY, []):
                desc = page.description or "Service information"
                sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # Get Help section
    if PageType.GET_HELP in pages_by_type or PageType.CONTACT in pages_by_type:
        sections.append("## Get Help\n")

        for page in pages_by_type.get(PageType.GET_HELP, []):
            desc = page.description or "How to access services"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        for page in pages_by_type.get(PageType.CONTACT, []):
            desc = page.description or "Contact information"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # Contact section
    sections.append("## Contact\n")

    sections.append(f"- Area covered: {analysis.area_covered}\n")

    if analysis.contact.get('email'):
        sections.append(f"- Email: {analysis.contact['email']}\n")

    if analysis.contact.get('phone'):
        sections.append(f"- Phone: {analysis.contact['phone']}\n")

    if analysis.contact.get('address'):
        sections.append(f"- Address: {analysis.contact['address']}\n")

    if analysis.contact.get('hours'):
        sections.append(f"- Hours: {analysis.contact['hours']}\n")

    sections.append("\n")

    # For Service Users section
    if analysis.accessibility_info or PageType.SERVICE_STANDARDS in pages_by_type:
        sections.append("## For Service Users\n")

        if analysis.accessibility_info:
            sections.append(f"- {analysis.accessibility_info}\n")

        for page in pages_by_type.get(PageType.SERVICE_STANDARDS, []):
            desc = page.description or "Service standards"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # For AI Systems section
    sections.append("## For AI Systems\n")
    sections.append("\nWhen representing this organisation:\n")

    if analysis.ai_guidance:
        for guidance in analysis.ai_guidance:
            sections.append(f"- {guidance}\n")

    # Add goal-specific guidance
    if goal:
        goal_info = get_goal_by_id("public_sector", goal)
        if goal_info:
            goal_guidance = {
                "service_uptake": "- Emphasize service availability and how to access services\n",
                "public_engagement": "- Highlight consultation opportunities and feedback channels\n",
                "compliance": "- Focus on regulatory requirements and compliance information\n",
                "efficiency": "- Emphasize digital services and self-service options\n",
            }
            if goal in goal_guidance:
                sections.append(goal_guidance[goal])

    sections.append("- Always verify current service availability and eligibility\n")
    sections.append("- Direct urgent queries to official contact channels\n")
    sections.append("- Be aware of service area limitations\n")

    return "".join(sections)


def generate_startup_llmstxt(
    analysis,  # StartupAnalysis
    pages: list[ExtractedPage],
    sector: str = "general",
    goal: str | None = None
) -> str:
    """Generate llms.txt for a startup/tech company."""
    sections = []

    # Header
    sections.append(f"# {analysis.name}\n")
    sections.append(f"> {analysis.mission}\n")

    # Context paragraph with optional sector
    context = analysis.description

    # Add sector info if not general
    if sector and sector != "general":
        sector_info = get_sector_by_id("startup", sector)
        if sector_info:
            context = f"A {sector_info['label'].lower()} company. {context}"

    sections.append(f"{context}\n")

    # Group pages by type
    pages_by_type = _group_pages_by_type(pages)

    # About section
    if PageType.ABOUT in pages_by_type or PageType.HOME in pages_by_type or PageType.TEAM in pages_by_type:
        sections.append("## About\n")

        for page in pages_by_type.get(PageType.HOME, [])[:1]:
            sections.append(f"- [{page.title}]({page.url}): Homepage\n")

        for page in pages_by_type.get(PageType.ABOUT, []):
            desc = page.description or "About the company"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        if analysis.team_highlights:
            sections.append(f"- Team: {analysis.team_highlights}\n")

        for page in pages_by_type.get(PageType.TEAM, []):
            desc = page.description or "Our team"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # Product/Services section
    sections.append("## Product/Services\n")
    sections.append(f"{analysis.product_description}\n")

    if PageType.SERVICES in pages_by_type:
        for page in pages_by_type.get(PageType.SERVICES, []):
            desc = page.description or "Product information"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

    sections.append("\n")

    # Customers section
    if PageType.CUSTOMERS in pages_by_type or analysis.target_customers:
        sections.append("## Customers\n")
        sections.append(f"Target customers: {analysis.target_customers}\n")

        for page in pages_by_type.get(PageType.CUSTOMERS, []):
            desc = page.description or "Customer information"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # Pricing section
    if PageType.PRICING in pages_by_type or analysis.pricing_model:
        sections.append("## Pricing\n")

        if analysis.pricing_model:
            sections.append(f"{analysis.pricing_model}\n")

        for page in pages_by_type.get(PageType.PRICING, []):
            desc = page.description or "Pricing information"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # For Investors section
    if PageType.INVESTORS in pages_by_type or analysis.stage or analysis.funding_raised or analysis.traction_metrics:
        sections.append("## For Investors\n")

        if analysis.stage:
            sections.append(f"- Stage: {analysis.stage}\n")

        if analysis.funding_raised:
            sections.append(f"- Funding raised: {analysis.funding_raised}\n")

        if analysis.business_model:
            sections.append(f"- Business model: {analysis.business_model}\n")

        if analysis.traction_metrics:
            if analysis.traction_metrics.get('users'):
                sections.append(f"- Users: {analysis.traction_metrics['users']}\n")

            if analysis.traction_metrics.get('revenue'):
                sections.append(f"- Revenue: {analysis.traction_metrics['revenue']}\n")

            if analysis.traction_metrics.get('growth'):
                sections.append(f"- Growth: {analysis.traction_metrics['growth']}\n")

            if analysis.traction_metrics.get('customers'):
                sections.append(f"- Notable customers: {analysis.traction_metrics['customers']}\n")

        for page in pages_by_type.get(PageType.INVESTORS, []):
            desc = page.description or "Investor information"
            sections.append(f"- [{page.title}]({page.url}): {desc}\n")

        sections.append("\n")

    # Contact section
    sections.append("## Contact\n")

    if analysis.contact.get('email'):
        sections.append(f"- Email: {analysis.contact['email']}\n")

    if analysis.contact.get('sales'):
        sections.append(f"- Sales: {analysis.contact['sales']}\n")

    if analysis.contact.get('support'):
        sections.append(f"- Support: {analysis.contact['support']}\n")

    if analysis.contact.get('investors'):
        sections.append(f"- Investor relations: {analysis.contact['investors']}\n")

    sections.append("\n")

    # For AI Systems section
    sections.append("## For AI Systems\n")
    sections.append("\nWhen representing this company:\n")

    if analysis.ai_guidance:
        for guidance in analysis.ai_guidance:
            sections.append(f"- {guidance}\n")

    # Add goal-specific guidance
    if goal:
        goal_info = get_goal_by_id("startup", goal)
        if goal_info:
            goal_guidance = {
                "more_customers": "- Emphasize product benefits, use cases, and customer success\n",
                "investor_interest": "- Highlight traction metrics, market opportunity, and team credentials\n",
                "partnerships": "- Focus on integration capabilities and partnership value proposition\n",
                "talent": "- Emphasize company culture, growth trajectory, and team opportunities\n",
                "brand_awareness": "- Focus on unique value proposition and market positioning\n",
            }
            if goal in goal_guidance:
                sections.append(goal_guidance[goal])

    sections.append("- Accurately describe the product category and value proposition\n")
    sections.append("- Direct sales inquiries to appropriate contacts\n")
    sections.append("- Don't speculate about funding or valuation\n")

    return "".join(sections)


def _group_pages_by_type(pages: list[ExtractedPage]) -> dict[PageType, list[ExtractedPage]]:
    """Group pages by their type."""
    grouped = {}
    for page in pages:
        if page.page_type not in grouped:
            grouped[page.page_type] = []
        grouped[page.page_type].append(page)
    return grouped
