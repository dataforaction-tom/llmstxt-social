"""Enrich the Open Org demo ideas and strategies with rich, schema-valid content.

The demo dataset (14 organisations, 17 ideas, 7 strategies) ships with titles
and themes only, which leaves the rendered idea/strategy detail pages sparse.
This script merges hand-authored, schema-valid content into each record's
JSON, regenerates the markdown source from it (so the editor stays in sync),
validates against the Open Org schemas, and commits.

It is **idempotent** — re-running merges the same content and produces the same
result. It only touches records that already exist; it never creates orgs.

Run inside the API container (which has DB access + the package installed):

    docker exec llmstxt-local-api-1 python /app/api/scripts/seed_openorg_demo.py
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from llmstxt_api.database import AsyncSessionLocal
from llmstxt_api.open_org_models import OrgIdea, OrgStrategy
from llmstxt_core.open_org.converter import json_to_markdown
from llmstxt_core.open_org.validator import validate_for_kind

# --------------------------------------------------------------------------- #
# Idea enrichments — keyed by (org_id, slug).
# Each entry is merged onto the existing idea_json. `status` is set from the
# schema-valid maturity enum (seed/developing/shaped/delivered) to give the
# discovery sort + status badges something meaningful to show.
# --------------------------------------------------------------------------- #

IDEA_ENRICHMENTS: dict[tuple[str, str], dict] = {
    ("GB-CHC-9000001", "community-fridge"): {
        "status": "delivered",
        "summary": "A network of community fridges that redistributes surplus food before it goes to waste.",
        "detail": (
            "We place fridges in trusted community venues — libraries, churches, "
            "community centres — and stock them with surplus from supermarkets and "
            "local growers. Anyone can take what they need, no questions asked. "
            "Volunteers run daily food-safety checks and a simple stock log."
        ),
        "place": {"description": "Bristol, citywide", "area_codes": ["E06000023"]},
        "beneficiaries": ["People in food poverty", "Low-income families", "Anyone reducing food waste"],
        "indicative_cost": {"lower": 18000, "upper": 32000, "currency": "GBP", "period": "year"},
        "evidence_base": [
            {"evidence_id": "fridge-eval-2024", "relevance": "Independent evaluation showed 22 tonnes of food redistributed in year one."},
        ],
        "collaborators": [
            {"org_name": "FareShare South West", "role": "Surplus food supply", "confirmed": True},
            {"org_name": "Bristol Green Spaces Trust", "org_id": "GB-CHC-9000002", "role": "Venue partner", "confirmed": True},
        ],
        "linked_strategy_id": "no-one-hungry-2027",
    },
    ("GB-CHC-9000001", "cooking-clubs"): {
        "status": "developing",
        "summary": "Weekly cooking clubs teaching affordable, nutritious batch-cooking on a budget.",
        "detail": (
            "Small groups cook a three-course meal together for under £1 a head, then "
            "share it around one table. Recipes are designed around the surplus our "
            "community fridges receive, closing the loop between waste and skills."
        ),
        "place": {"description": "Bristol, east and south wards", "area_codes": ["E06000023"]},
        "beneficiaries": ["Families on low incomes", "Isolated adults", "Young people leaving care"],
        "indicative_cost": {"lower": 9000, "upper": 16000, "currency": "GBP", "period": "year"},
        "connections": [
            {"org_name": "Bristol Green Spaces Trust", "org_id": "GB-CHC-9000002", "relationship": "collaborating", "mutual": True},
        ],
        "linked_strategy_id": "no-one-hungry-2027",
    },
    ("GB-CHC-9000002", "pocket-parks"): {
        "status": "shaped",
        "summary": "Turning neglected scraps of land into pocket parks designed and tended by neighbours.",
        "detail": (
            "We work street by street to convert disused corners — verges, alleys, "
            "forgotten plots — into small green spaces. Residents lead the design; we "
            "bring the tools, plants, and the permissions. Each park gets a volunteer "
            "steward and a small maintenance fund."
        ),
        "place": {"description": "Bristol, inner-city wards", "area_codes": ["E06000023"]},
        "beneficiaries": ["Residents without garden access", "Pollinators and urban wildlife"],
        "indicative_cost": {"lower": 25000, "upper": 60000, "currency": "GBP", "period": "year"},
        "collaborators": [
            {"org_name": "Bristol City Council Parks", "role": "Land access", "confirmed": False},
        ],
    },
    ("GB-CHC-9000003", "stem-clubs"): {
        "status": "delivered",
        "summary": "After-school STEM clubs that make science and engineering hands-on for 9–13s.",
        "detail": (
            "Weekly clubs in school halls where young people build, break, and "
            "investigate — from bridge-building to coding micro:bits. We deliberately "
            "recruit in schools with low progression to STEM GCSEs, and pair each club "
            "with a volunteer working in a STEM career."
        ),
        "place": {"description": "Leeds, priority wards", "area_codes": ["E08000035"]},
        "beneficiaries": ["Young people aged 9–13", "Girls under-represented in STEM"],
        "indicative_cost": {"lower": 14000, "upper": 28000, "currency": "GBP", "period": "year"},
        "evidence_base": [
            {"evidence_id": "stem-attendance-2024", "relevance": "78% of attendees reported increased confidence in science."},
        ],
        "linked_strategy_id": "every-young-person-2026",
    },
    ("GB-CHC-9000003", "youth-mentoring"): {
        "status": "developing",
        "summary": "One-to-one mentoring pairing trained volunteers with young people facing tough transitions.",
        "detail": (
            "Each young person is matched with a mentor for a year of weekly sessions — "
            "a consistent adult outside the family and school. Mentors are trained in "
            "trauma-informed practice and supervised monthly."
        ),
        "place": {"description": "Leeds, citywide", "area_codes": ["E08000035"]},
        "beneficiaries": ["Young people aged 11–18", "Those at risk of exclusion"],
        "indicative_cost": {"lower": 20000, "upper": 35000, "currency": "GBP", "period": "year"},
        "linked_strategy_id": "every-young-person-2026",
    },
    ("GB-CHC-9000004", "digital-drop-in"): {
        "status": "shaped",
        "summary": "Drop-in sessions helping adults build the digital skills modern life now assumes.",
        "detail": (
            "No appointment, no jargon. People bring their own questions — applying for "
            "Universal Credit, video-calling family, spotting scams — and a volunteer "
            "sits beside them until it clicks. We lend devices and data to those who "
            "need them between sessions."
        ),
        "place": {"description": "Manchester, libraries and community hubs", "area_codes": ["E08000003"]},
        "beneficiaries": ["Digitally excluded adults", "Older people", "Jobseekers"],
        "indicative_cost": {"lower": 12000, "upper": 22000, "currency": "GBP", "period": "year"},
        "collaborators": [
            {"org_name": "Manchester Libraries", "role": "Venue + referrals", "confirmed": True},
        ],
        "linked_strategy_id": "learning-for-all-2029",
    },
    ("GB-CHC-9000005", "esol-evenings"): {
        "status": "developing",
        "summary": "Free evening English classes for refugees and recent arrivals, with a crèche.",
        "detail": (
            "Two-hour sessions twice a week, run by trained volunteers and a qualified "
            "ESOL tutor. We hold them in the evening so people in work or training can "
            "attend, and provide a crèche so parents aren't shut out. Classes are "
            "pitched from pre-entry to Entry Level 3."
        ),
        "place": {"description": "Birmingham city centre", "area_codes": ["E08000025"]},
        "beneficiaries": ["Refugees and asylum seekers", "Recent migrants", "Parents needing childcare"],
        "indicative_cost": {"lower": 12000, "upper": 25000, "currency": "GBP", "period": "year"},
        "evidence_base": [
            {"evidence_id": "esol-progression-2024", "relevance": "64% of learners progressed at least one ESOL level."},
        ],
        "collaborators": [
            {"org_name": "Birmingham City College", "role": "Accreditation + venue", "confirmed": True},
            {"org_name": "Refugee Action", "role": "Referral partner", "confirmed": True},
        ],
    },
    ("GB-CHC-9000006", "peer-cafes"): {
        "status": "delivered",
        "summary": "Peer-led cafés where people with lived experience of mental ill-health support each other.",
        "detail": (
            "Warm, informal spaces — good coffee, no clinical feel — facilitated by "
            "people who've been there themselves. They're a stepping stone for those on "
            "waiting lists and a soft landing for those leaving services."
        ),
        "place": {"description": "Liverpool, four neighbourhood venues", "area_codes": ["E08000012"]},
        "beneficiaries": ["People experiencing mental ill-health", "People on CAMHS/IAPT waiting lists"],
        "indicative_cost": {"lower": 16000, "upper": 30000, "currency": "GBP", "period": "year"},
        "evidence_base": [
            {"evidence_id": "peer-cafe-wellbeing-2024", "relevance": "Average WEMWBS wellbeing score rose 7 points over six months."},
        ],
        "linked_strategy_id": "no-wrong-door-2028",
    },
    ("GB-CHC-9000006", "crisis-line"): {
        "status": "shaped",
        "summary": "An out-of-hours phone line answered by trained peers when other services close.",
        "detail": (
            "Evenings, nights, and weekends are when people most often reach crisis and "
            "least often find someone to talk to. Our line is answered by trained "
            "volunteers with lived experience, backed by a clinical escalation route."
        ),
        "place": {"description": "Liverpool City Region", "area_codes": ["E08000012"]},
        "beneficiaries": ["People in mental health crisis", "Carers and family members"],
        "indicative_cost": {"lower": 35000, "upper": 70000, "currency": "GBP", "period": "year"},
        "linked_strategy_id": "no-wrong-door-2028",
    },
    ("GB-CHC-9000007", "befriending"): {
        "status": "delivered",
        "summary": "A telephone befriending scheme matching volunteers with isolated older people.",
        "detail": (
            "A weekly call, same volunteer, same time — a small constant in a quiet "
            "week. We match on shared interests and train volunteers to spot when "
            "someone needs more than a chat, with a clear route to local support."
        ),
        "place": {"description": "Sheffield, citywide", "area_codes": ["E08000019"]},
        "beneficiaries": ["Isolated older people", "Housebound adults"],
        "indicative_cost": {"lower": 6000, "upper": 14000, "currency": "GBP", "period": "year"},
        "evidence_base": [
            {"evidence_id": "befriending-loneliness-2024", "relevance": "81% of matched older people reported feeling less lonely."},
        ],
    },
    ("GB-CHC-9000008", "rapid-rehousing"): {
        "status": "developing",
        "summary": "A Housing First pilot moving rough sleepers straight into homes, with support attached.",
        "detail": (
            "Instead of asking people to prove they're 'housing-ready', we house them "
            "first and wrap support around the tenancy — for as long as it takes. Our "
            "pilot follows 20 people with the most entrenched histories of rough "
            "sleeping."
        ),
        "place": {"description": "Newcastle upon Tyne", "area_codes": ["E08000021"]},
        "beneficiaries": ["People sleeping rough", "People with multiple disadvantage"],
        "indicative_cost": {"lower": 80000, "upper": 140000, "currency": "GBP", "period": "year"},
        "evidence_base": [
            {"evidence_id": "housing-first-retention-2024", "relevance": "Tenancy sustainment at 12 months is running at 85%."},
        ],
        "linked_strategy_id": "zero-rough-sleeping-2030",
    },
    ("GB-CHC-9000009", "safe-routes-to-work"): {
        "status": "seed",
        "summary": "Mapping and improving safe walking and transport routes so women can reach work and training.",
        "detail": (
            "For many women, the barrier to a job or course isn't the role — it's "
            "getting there safely after dark. We work with women to map unsafe routes, "
            "then press for lighting, bus timing, and travel support to fix them."
        ),
        "place": {"description": "Nottingham", "area_codes": ["E06000018"]},
        "beneficiaries": ["Women returning to work", "Women in training", "Shift workers"],
        "indicative_cost": {"lower": 8000, "upper": 18000, "currency": "GBP", "period": "year"},
    },
    ("GB-CHC-9000010", "oral-histories"): {
        "status": "shaped",
        "summary": "Recording the oral histories of South Wales coalfield communities before they're lost.",
        "detail": (
            "We train local volunteers to record and archive the memories of former "
            "miners and their families — work, strikes, community, loss. The archive is "
            "public, and feeds school workshops and a touring exhibition."
        ),
        "place": {"description": "South Wales valleys", "area_codes": ["W06000015"]},
        "beneficiaries": ["Older residents", "Schools and young people", "Researchers"],
        "indicative_cost": {"lower": 15000, "upper": 30000, "currency": "GBP", "period": "year"},
    },
    ("GB-CHC-9000011", "bike-library"): {
        "status": "delivered",
        "summary": "A community bike library lending bikes, with free repairs and confidence rides.",
        "detail": (
            "Borrow a bike like you'd borrow a book. We keep a fleet maintained by "
            "volunteer mechanics, run learn-to-ride and confidence sessions, and teach "
            "people to fix their own bikes so the skills stay in the community."
        ),
        "place": {"description": "Glasgow", "area_codes": ["S12000049"]},
        "beneficiaries": ["People without a bike", "New and returning cyclists", "Low-income commuters"],
        "indicative_cost": {"lower": 10000, "upper": 24000, "currency": "GBP", "period": "year"},
    },
    ("GB-CHC-9000012", "youth-group"): {
        "status": "developing",
        "summary": "A weekly group where LGBTQ+ young people can be themselves and find each other.",
        "detail": (
            "A safe, youth-led space with trained facilitators — part social, part "
            "support. We run alongside a parents' group and a clear safeguarding and "
            "referral pathway for young people who need more."
        ),
        "place": {"description": "Brighton & Hove", "area_codes": ["E06000043"]},
        "beneficiaries": ["LGBTQ+ young people aged 13–18", "Their families"],
        "indicative_cost": {"lower": 11000, "upper": 22000, "currency": "GBP", "period": "year"},
        "linked_strategy_id": "belonging-2027",
    },
    ("GB-CHC-9000013", "river-wardens"): {
        "status": "shaped",
        "summary": "A volunteer river warden network monitoring water quality and wildlife along the Wensum.",
        "detail": (
            "Trained volunteers walk set stretches of river monthly, recording water "
            "quality, invasive species, and wildlife. The data feeds a public dashboard "
            "and the Environment Agency, and the wardens become advocates for their "
            "river."
        ),
        "place": {"description": "Norwich, River Wensum", "area_codes": ["E07000148"]},
        "beneficiaries": ["Local communities", "River wildlife", "Environmental researchers"],
        "indicative_cost": {"lower": 9000, "upper": 19000, "currency": "GBP", "period": "year"},
    },
    ("GB-CHC-9000014", "blue-spaces"): {
        "status": "seed",
        "summary": "Wellbeing sessions on the water and the shore for people struggling with their mental health.",
        "detail": (
            "Time by the sea is good medicine. We run guided beach walks, paddling, and "
            "shore-based mindfulness for people referred through social prescribing, "
            "combining nature connection with peer support."
        ),
        "place": {"description": "Plymouth coast", "area_codes": ["E06000026"]},
        "beneficiaries": ["People with low-level mental ill-health", "Socially isolated adults"],
        "indicative_cost": {"lower": 7000, "upper": 16000, "currency": "GBP", "period": "year"},
        "linked_strategy_id": "living-coast-2030",
    },
}

# --------------------------------------------------------------------------- #
# Strategy enrichments — keyed by (org_id, slug).
# --------------------------------------------------------------------------- #

STRATEGY_ENRICHMENTS: dict[tuple[str, str], dict] = {
    ("GB-CHC-9000001", "no-one-hungry-2027"): {
        "status": "active",
        "summary": (
            "A three-year plan to end the need for emergency food in Bristol by tackling "
            "its causes, not just its symptoms — moving from parcels to dignity, choice, "
            "and prevention."
        ),
        "period": {"start": "2024-04-01", "end": "2027-03-31", "horizon": "2_3_years"},
        "priorities": [
            {
                "title": "Shift from food parcels to choice-based provision",
                "themes": ["food_access"],
                "maturity": "established",
                "narrative": "Replace top-down parcels with community fridges and pantries where people choose what they take.",
                "success_indicators": ["12 community fridges open", "5,000 households reached", "Parcel reliance down 40%"],
            },
            {
                "title": "Build food skills and confidence",
                "themes": ["food_access", "health"],
                "maturity": "emerging",
                "narrative": "Pair provision with cooking clubs so people leave with skills, not just a bag of food.",
                "success_indicators": ["30 cooking clubs running", "80% report cooking more from scratch"],
            },
        ],
        "not_doing": [
            {"title": "Running a traditional food bank", "rationale": "Emergency parcels treat the symptom; we're choosing to invest upstream in dignity and prevention."},
        ],
        "tensions": [
            {"title": "Dignity versus scale", "narrative": "Choice-based models are slower and costlier per head than parcels. We accept slower growth to protect dignity."},
        ],
        "learning": {"what_changed": [
            {"lesson": "Our 2023 pilot showed people wanted agency, not hand-outs — so we rebuilt the whole model around choice.", "source": "2023 pilot evaluation"},
        ]},
        "relationships": {
            "partnerships": [
                {"name": "FareShare South West", "direction": "established", "narrative": "Surplus food supply backbone."},
                {"name": "Bristol City Council", "direction": "deepening", "narrative": "Co-funder and referral route."},
            ],
            "ecosystem_position": "We convene the city's food-justice network rather than competing with it.",
            "community_mandate": "Co-designed with 200 people with direct experience of food poverty.",
        },
        "resource_model": {
            "current_funding_mix": {"grants": 55, "local_authority": 30, "community_giving": 15},
            "sustainability_direction": "diversifying",
            "resourcing_gaps": ["Core staffing for the network coordinator role is funded only to 2026."],
        },
    },
    ("GB-CHC-9000003", "every-young-person-2026"): {
        "status": "active",
        "summary": "A plan to make sure every young person in Leeds has a trusted adult, a place to belong, and a path to thrive.",
        "period": {"start": "2024-09-01", "end": "2026-08-31", "horizon": "2_3_years"},
        "priorities": [
            {
                "title": "A trusted adult for every young person who needs one",
                "themes": ["children_and_young_people", "mental_health"],
                "maturity": "established",
                "narrative": "Scale one-to-one mentoring into the schools with the highest exclusion risk.",
                "success_indicators": ["400 active mentoring matches", "Exclusions down in partner schools"],
            },
            {
                "title": "Spark curiosity through hands-on STEM",
                "themes": ["education"],
                "maturity": "mature",
                "narrative": "Sustain and deepen after-school STEM clubs, with a focus on girls' progression.",
                "success_indicators": ["20 clubs", "Girls' STEM GCSE uptake up in partner schools"],
            },
        ],
        "not_doing": [
            {"title": "Universal open-access youth clubs", "rationale": "We're focusing depth on the young people facing the steepest barriers rather than spreading thin."},
        ],
        "tensions": [
            {"title": "Targeting versus stigma", "narrative": "Focusing on high-need young people risks labelling them. We mitigate with open-invite framing."},
        ],
        "learning": {"what_changed": [
            {"lesson": "Attendance data told us relationships, not activities, drive outcomes — so mentoring became the spine of the strategy.", "source": "Programme attendance analysis"},
        ]},
        "relationships": {
            "partnerships": [
                {"name": "Leeds City Council early-help team", "direction": "established", "narrative": "Primary referral route for at-risk young people."},
                {"name": "Regional STEM employers", "direction": "new", "narrative": "Provide volunteer mentors for STEM clubs."},
            ],
            "ecosystem_position": "A delivery partner within the city's youth-work alliance.",
            "community_mandate": "Shaped by a youth advisory board that holds a third of our trustee votes.",
        },
        "resource_model": {
            "current_funding_mix": {"trusts_and_foundations": 60, "local_authority": 25, "corporate": 15},
            "sustainability_direction": "diversifying",
            "resourcing_gaps": ["Volunteer mentor recruitment can't yet keep pace with referrals."],
        },
    },
    ("GB-CHC-9000004", "learning-for-all-2029"): {
        "status": "active",
        "summary": "A long-term commitment to close the digital and skills divide across Greater Manchester.",
        "period": {"start": "2026-01-01", "end": "2029-12-31", "horizon": "3_5_years"},
        "priorities": [
            {
                "title": "No adult left offline",
                "themes": ["digital_inclusion"],
                "maturity": "emerging",
                "narrative": "Expand drop-in digital support and device lending across libraries and hubs.",
                "success_indicators": ["3,000 adults supported a year", "1,000 devices in circulation"],
            },
        ],
        "not_doing": [
            {"title": "Accredited qualifications", "rationale": "We focus on confidence and everyday digital life; accreditation is well served by FE colleges."},
        ],
        "tensions": [
            {"title": "Reach versus depth", "narrative": "Drop-ins reach many but lightly; some people need sustained one-to-one support we can't always offer."},
        ],
        "learning": {"what_changed": [
            {"lesson": "We learned device access without data is useless, so we now lend connectivity alongside hardware."},
        ]},
        "relationships": {
            "partnerships": [
                {"name": "Manchester Libraries", "direction": "established", "narrative": "Host venues and referrals."},
                {"name": "Good Things Foundation", "direction": "deepening", "narrative": "National digital-inclusion network and curriculum."},
            ],
            "ecosystem_position": "The connective tissue between device-donation schemes and frontline venues.",
            "community_mandate": "Guided by a panel of digitally-excluded residents.",
        },
        "resource_model": {
            "current_funding_mix": {"grants": 50, "corporate_in_kind": 30, "local_authority": 20},
            "sustainability_direction": "diversifying",
            "resourcing_gaps": ["Ongoing data and connectivity costs are the hardest to fund."],
        },
    },
    ("GB-CHC-9000006", "no-wrong-door-2028"): {
        "status": "active",
        "summary": "A strategy so that anyone reaching out in Liverpool for mental health support finds a door that opens — whoever they ask.",
        "period": {"start": "2025-01-01", "end": "2028-12-31", "horizon": "3_5_years"},
        "priorities": [
            {
                "title": "Peer support on every high street",
                "themes": ["mental_health", "lived_experience"],
                "maturity": "established",
                "narrative": "Grow peer-led cafés so help exists before crisis, led by people with lived experience.",
                "success_indicators": ["10 cafés", "2,000 people supported a year"],
            },
            {
                "title": "Someone to answer, out of hours",
                "themes": ["mental_health"],
                "maturity": "emerging",
                "narrative": "Stand up a peer-staffed crisis line for evenings, nights, and weekends.",
                "success_indicators": ["Line answered 7 nights a week", "<2% calls unanswered"],
            },
        ],
        "not_doing": [
            {"title": "Clinical treatment", "rationale": "We complement the NHS rather than duplicating clinical services; our edge is lived experience."},
        ],
        "tensions": [
            {"title": "Peer model versus clinical safety", "narrative": "Peer-led support must hold real risk safely. We invest heavily in training and clinical escalation."},
        ],
        "learning": {"what_changed": [
            {"lesson": "People kept falling through gaps between services, so we organised the strategy around 'no wrong door' rather than around our own programmes."},
        ]},
        "relationships": {
            "partnerships": [
                {"name": "Mersey Care NHS Trust", "direction": "deepening", "narrative": "Clinical escalation and commissioning partner."},
                {"name": "Lived-experience networks", "direction": "established", "narrative": "Co-produce and staff the peer model."},
            ],
            "ecosystem_position": "The community front-door that feeds into, and catches from, clinical services.",
            "community_mandate": "Majority of our board has lived experience of mental ill-health.",
        },
        "resource_model": {
            "current_funding_mix": {"nhs_icb_contracts": 45, "grants": 40, "community_giving": 15},
            "sustainability_direction": "concentrating",
            "resourcing_gaps": ["The crisis line needs sustained night-cover funding to launch fully."],
        },
    },
    ("GB-CHC-9000008", "zero-rough-sleeping-2030"): {
        "status": "active",
        "summary": "An ambition to end rough sleeping in Newcastle for good, built on Housing First principles.",
        "period": {"start": "2025-01-01", "end": "2030-12-31", "horizon": "5_10_years"},
        "priorities": [
            {
                "title": "Housing First, at scale",
                "themes": ["housing_and_homelessness"],
                "maturity": "emerging",
                "narrative": "Move people straight into settled homes with open-ended, wrap-around support.",
                "success_indicators": ["100 tenancies created", "85%+ sustained at 12 months"],
            },
        ],
        "not_doing": [
            {"title": "Expanding night shelters", "rationale": "Shelters manage rough sleeping; they don't end it. We're investing in homes instead."},
        ],
        "tensions": [
            {"title": "Speed versus housing supply", "narrative": "Housing First only works with homes to offer. Our pace is capped by social-housing availability."},
        ],
        "learning": {"what_changed": [
            {"lesson": "We saw 'housing-readiness' gatekeeping kept the most entrenched people on the street, so we removed the precondition entirely.", "source": "Year-one pilot review"},
        ]},
        "relationships": {
            "partnerships": [
                {"name": "Newcastle City Council", "direction": "established", "narrative": "Statutory partner and co-funder."},
                {"name": "Registered housing providers", "direction": "deepening", "narrative": "Supply the homes Housing First depends on."},
            ],
            "ecosystem_position": "Lead delivery partner for the city's rough-sleeping strategy.",
            "community_mandate": "Co-produced with people with direct experience of homelessness.",
        },
        "resource_model": {
            "current_funding_mix": {"statutory": 50, "trusts": 35, "housing_provider_contributions": 15},
            "sustainability_direction": "concentrating",
            "resourcing_gaps": ["Access to one- and two-bed social homes is the binding constraint."],
        },
    },
    ("GB-CHC-9000012", "belonging-2027"): {
        "status": "active",
        "summary": "A strategy to make Brighton & Hove a place where every LGBTQ+ person feels they belong and can thrive.",
        "period": {"start": "2024-01-01", "end": "2027-12-31", "horizon": "3_5_years"},
        "priorities": [
            {
                "title": "Safe spaces for LGBTQ+ young people",
                "themes": ["lgbtq_plus", "children_and_young_people"],
                "maturity": "established",
                "narrative": "Sustain and grow youth groups where young people can be themselves and find peers.",
                "success_indicators": ["Weekly group at capacity", "Parents' group running alongside"],
            },
        ],
        "not_doing": [
            {"title": "One-off awareness campaigns", "rationale": "We invest in sustained spaces and relationships over short-lived visibility moments."},
        ],
        "tensions": [
            {"title": "Visibility versus safety", "narrative": "Being visible builds belonging but can attract hostility; we balance pride with safeguarding."},
        ],
        "learning": {"what_changed": [
            {"lesson": "Young people told us they wanted somewhere to simply be, not to be 'a project' — so we made the youth group purely theirs."},
        ]},
        "relationships": {
            "partnerships": [
                {"name": "Local secondary schools", "direction": "established", "narrative": "Referrals and safeguarding links."},
                {"name": "CAMHS", "direction": "deepening", "narrative": "Escalation route for young people who need clinical support."},
            ],
            "ecosystem_position": "A hub connecting LGBTQ+ young people to wider support.",
            "community_mandate": "Programme co-designed with LGBTQ+ young people themselves.",
        },
        "resource_model": {
            "current_funding_mix": {"grants": 70, "community_fundraising": 20, "local_authority": 10},
            "sustainability_direction": "diversifying",
            "resourcing_gaps": ["Specialist youth-work capacity is stretched against demand."],
        },
    },
    ("GB-CHC-9000014", "living-coast-2030"): {
        "status": "active",
        "summary": "A plan for a living Plymouth coast — healthier seas, and healthier people through connection to them.",
        "period": {"start": "2025-01-01", "end": "2030-12-31", "horizon": "5_10_years"},
        "priorities": [
            {
                "title": "Blue health for wellbeing",
                "themes": ["nature_and_biodiversity", "mental_health"],
                "maturity": "seed",
                "narrative": "Use the coast as a setting for mental-health and social-prescribing programmes.",
                "success_indicators": ["Blue-spaces programme referrals embedded with GPs", "Measurable wellbeing gains"],
            },
        ],
        "not_doing": [
            {"title": "Large capital marine projects", "rationale": "Our niche is people-and-nature connection, not infrastructure better led by others."},
        ],
        "tensions": [
            {"title": "Access versus conservation", "narrative": "More people on the shore can disturb fragile habitats; we design for low-impact access."},
        ],
        "learning": {"what_changed": [
            {"lesson": "We found nature programmes worked best when paired with peer support, so wellbeing and conservation now run as one."},
        ]},
        "relationships": {
            "partnerships": [
                {"name": "Local GP practices", "direction": "new", "narrative": "Social-prescribing referral route."},
                {"name": "National Marine Aquarium", "direction": "established", "narrative": "Marine education and venue partner."},
            ],
            "ecosystem_position": "Bridging environmental and health sectors locally.",
            "community_mandate": "Shaped with coastal communities and people who've used the programmes.",
        },
        "resource_model": {
            "current_funding_mix": {"environmental_grants": 50, "health_social_prescribing": 30, "donations": 20},
            "sustainability_direction": "diversifying",
            "resourcing_gaps": ["Qualified blue-health facilitators are scarce locally."],
        },
    },
}


def _merge(base: dict | None, enrichment: dict) -> dict:
    """Shallow-merge enrichment onto base; enrichment values win."""
    merged = dict(base or {})
    merged.update(enrichment)
    return merged


async def main() -> int:
    ideas_updated = 0
    strategies_updated = 0
    errors: list[str] = []

    async with AsyncSessionLocal() as session:
        # --- ideas ---
        idea_rows = (await session.execute(select(OrgIdea))).scalars().all()
        for row in idea_rows:
            enrichment = IDEA_ENRICHMENTS.get((row.org_id, row.slug))
            if not enrichment:
                continue
            merged = _merge(row.idea_json, enrichment)
            # Required schema fields live in DB columns, not the stored JSON —
            # re-inject them so the merged document is self-contained + valid.
            merged.setdefault("schema_version", "open-org-idea/v0.1")
            merged.setdefault("id", row.slug)
            if not merged.get("themes"):
                merged["themes"] = list(row.themes or [])
            merged["status"] = enrichment.get("status") or merged.get("status") or "seed"
            try:
                validate_for_kind(merged, kind="idea")
                markdown = json_to_markdown(merged, kind="idea")
            except Exception as exc:  # noqa: BLE001 — report and skip bad records
                errors.append(f"idea {row.org_id}/{row.slug}: {exc}")
                continue
            row.idea_json = merged
            row.markdown_source = markdown
            if "status" in enrichment:
                row.status = enrichment["status"]
            ideas_updated += 1

        # --- strategies ---
        strat_rows = (await session.execute(select(OrgStrategy))).scalars().all()
        for row in strat_rows:
            enrichment = STRATEGY_ENRICHMENTS.get((row.org_id, row.slug))
            if not enrichment:
                continue
            merged = _merge(row.strategy_json, enrichment)
            merged.setdefault("schema_version", "open-org-strategy/v0.1")
            merged.setdefault("id", row.slug)
            if not merged.get("themes"):
                merged["themes"] = list(row.themes or [])
            merged["status"] = enrichment.get("status") or merged.get("status") or "active"
            try:
                validate_for_kind(merged, kind="strategy")
                markdown = json_to_markdown(merged, kind="strategy")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"strategy {row.org_id}/{row.slug}: {exc}")
                continue
            row.strategy_json = merged
            row.markdown_source = markdown
            if "status" in enrichment:
                row.status = enrichment["status"]
            strategies_updated += 1

        await session.commit()

    print(f"Enriched {ideas_updated} ideas and {strategies_updated} strategies.")
    if errors:
        print(f"\n{len(errors)} record(s) skipped due to validation/convert errors:")
        for e in errors:
            print(f"  - {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
