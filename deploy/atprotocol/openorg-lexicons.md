# AT Protocol Lexicon Design — Open Org on Bluesky's Protocol

> Drafted: 2026-07-03
> Status: **Spec only — implementation gated on Phase 4 decision**
> Part of: Phase 2 spec (Workstream 4.2)

## Purpose

Design the AT Protocol Lexicons that would let Open Org profiles, strategies,
ideas, evidence, and signals be published as signed, portable records on
AT Protocol (Bluesky's protocol). This is design-only — no PDS, relay, or
App View is built in Phase 2.

The Lexicons map directly to the existing Open Org JSON schemas. Designing
them now means the Phase 4 build decision is informed and the migration path
is clear.

## Lexicon overview

Six Lexicons, namespaced under `uk.co.goodship.openorg`:

| NSID | Record type | Maps to |
|------|-------------|---------|
| `uk.co.goodship.openorg.profile` | record | `org_profile.schema.json` |
| `uk.co.goodship.openorg.strategy` | record | `org_strategy.schema.json` |
| `uk.co.goodship.openorg.idea` | record | `org_idea.schema.json` |
| `uk.co.goodship.openorg.evidence` | record | `evidence[]` items in profile schema |
| `uk.co.goodship.openorg.signal` | record | `OrgSignal` (funder interest) |
| `uk.co.goodship.openorg.defs` | — | Shared shapes (themes, income_bands, org_id) |

## Lexicon: `uk.co.goodship.openorg.defs`

Shared definitions referenced by other Lexicons.

```json
{
  "lexicon": 1,
  "id": "uk.co.goodship.openorg.defs",
  "defs": {
    "themeKey": {
      "type": "string",
      "enum": [
        "older_people", "children_and_young_people", "families_and_carers",
        "health", "mental_health", "disability", "social_prescribing",
        "loneliness", "food_access", "housing_and_homelessness",
        "poverty_and_financial_inclusion", "community_development",
        "volunteering", "lived_experience", "education",
        "employment_and_skills", "arts_and_culture", "heritage",
        "environment_and_climate", "nature_and_biodiversity",
        "transport_and_mobility", "digital_inclusion", "civic_participation",
        "women_and_girls", "lgbtq_plus", "race_equity",
        "refugees_and_migration", "crime_and_justice", "domestic_abuse",
        "animal_welfare"
      ]
    },
    "incomeBand": {
      "type": "string",
      "enum": [
        "under_10k", "10k-100k", "100k-250k", "250k-500k",
        "500k-1m", "1m-5m", "5m-10m", "10m-100m", "over_100m"
      ]
    },
    "orgId": {
      "type": "string",
      "pattern": "^[A-Z]{2}-[A-Z]{3}-.+$",
      "description": "org-id.guide identifier (e.g. GB-CHC-1234567)"
    },
    "geolocation": {
      "type": "object",
      "required": ["lat", "lon"],
      "properties": {
        "lat": {"type": "number", "minimum": -90, "maximum": 90},
        "lon": {"type": "number", "minimum": -180, "maximum": 180}
      }
    }
  }
}
```

## Lexicon: `uk.co.goodship.openorg.profile`

```json
{
  "lexicon": 1,
  "id": "uk.co.goodship.openorg.profile",
  "defs": {
    "main": {
      "type": "record",
      "description": "An organisation's Open Org profile.",
      "key": "tid",
      "record": {
        "type": "object",
        "required": ["name", "orgId", "themes", "schemaVersion"],
        "properties": {
          "name": {"type": "string", "minLength": 1},
          "orgId": {"type": "ref", "ref": "uk.co.goodship.openorg.defs#orgId"},
          "website": {"type": "string", "format": "uri"},
          "themes": {
            "type": "array",
            "items": {"type": "ref", "ref": "uk.co.goodship.openorg.defs#themeKey"},
            "minLength": 0
          },
          "mission": {"type": "string"},
          "incomeBand": {"type": "ref", "ref": "uk.co.goodship.openorg.defs#incomeBand"},
          "primaryArea": {"type": "string"},
          "primaryAreaCode": {"type": "string"},
          "geolocation": {"type": "ref", "ref": "uk.co.goodship.openorg.defs#geolocation"},
          "registration": {
            "type": "object",
            "properties": {
              "charityCommissionEw": {"type": "string"},
              "companiesHouse": {"type": "string"},
              "oscr": {"type": "string"},
              "ccni": {"type": "string"}
            }
          },
          "schemaVersion": {"type": "string", "const": "open-org/v0.1"},
          "createdAt": {"type": "string", "format": "datetime"},
          "updatedAt": {"type": "string", "format": "datetime"}
        }
      }
    }
  }
}
```

## Lexicon: `uk.co.goodship.openorg.strategy`

```json
{
  "lexicon": 1,
  "id": "uk.co.goodship.openorg.strategy",
  "defs": {
    "main": {
      "type": "record",
      "description": "An organisation's strategy — priorities, tensions, learning.",
      "key": "tid",
      "record": {
        "type": "object",
        "required": ["id", "status", "themes", "schemaVersion"],
        "properties": {
          "id": {"type": "string", "minLength": 1},
          "status": {"type": "string", "enum": ["draft", "active", "archived"]},
          "themes": {
            "type": "array",
            "items": {"type": "ref", "ref": "uk.co.goodship.openorg.defs#themeKey"},
            "minLength": 1
          },
          "summary": {"type": "string"},
          "periodStart": {"type": "string", "format": "date"},
          "periodEnd": {"type": "string", "format": "date"},
          "periodHorizon": {
            "type": "string",
            "enum": ["1_year", "2_3_years", "3_5_years", "5_10_years"]
          },
          "schemaVersion": {"type": "string", "const": "open-org-strategy/v0.1"},
          "createdAt": {"type": "string", "format": "datetime"},
          "updatedAt": {"type": "string", "format": "datetime"}
        }
      }
    }
  }
}
```

## Lexicon: `uk.co.goodship.openorg.idea`

```json
{
  "lexicon": 1,
  "id": "uk.co.goodship.openorg.idea",
  "defs": {
    "main": {
      "type": "record",
      "description": "An idea an organisation is developing or seeking to deliver.",
      "key": "tid",
      "record": {
        "type": "object",
        "required": ["id", "status", "themes", "schemaVersion"],
        "properties": {
          "id": {"type": "string", "minLength": 1},
          "status": {"type": "string", "enum": ["seed", "developing", "shaped", "delivered", "archived"]},
          "summary": {"type": "string"},
          "detail": {"type": "string"},
          "themes": {
            "type": "array",
            "items": {"type": "ref", "ref": "uk.co.goodship.openorg.defs#themeKey"},
            "minLength": 1
          },
          "place": {
            "type": "object",
            "properties": {
              "description": {"type": "string"},
              "areaCodes": {"type": "array", "items": {"type": "string"}},
              "geolocation": {"type": "ref", "ref": "uk.co.goodship.openorg.defs#geolocation"}
            }
          },
          "costMin": {"type": "integer"},
          "costMax": {"type": "integer"},
          "costCurrency": {"type": "string"},
          "schemaVersion": {"type": "string", "const": "open-org-idea/v0.1"},
          "createdAt": {"type": "string", "format": "datetime"},
          "updatedAt": {"type": "string", "format": "datetime"}
        }
      }
    }
  }
}
```

## Lexicon: `uk.co.goodship.openorg.evidence`

```json
{
  "lexicon": 1,
  "id": "uk.co.goodship.openorg.evidence",
  "defs": {
    "main": {
      "type": "record",
      "description": "A verified evidence item — outcome data, annual report, case study, etc.",
      "key": "tid",
      "record": {
        "type": "object",
        "required": ["evidenceId", "title", "evidenceType", "schemaVersion"],
        "properties": {
          "evidenceId": {"type": "string", "minLength": 1},
          "title": {"type": "string", "minLength": 1},
          "evidenceType": {
            "type": "string",
            "enum": ["evaluation", "outcome_data", "annual_report", "case_study",
                     "learning_reflection", "external_research", "other"]
          },
          "date": {"type": "string", "format": "date"},
          "url": {"type": "string", "format": "uri"},
          "themes": {
            "type": "array",
            "items": {"type": "ref", "ref": "uk.co.goodship.openorg.defs#themeKey"}
          },
          "outcomes": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "metric": {"type": "string"},
                "baseline": {"type": "number"},
                "followUp": {"type": "number"},
                "change": {"type": "number"},
                "n": {"type": "integer"},
                "description": {"type": "string"}
              }
            }
          },
          "hypercert": {
            "type": "object",
            "properties": {
              "tokenId": {"type": "string"},
              "chainId": {"type": "integer"},
              "transactionHash": {"type": "string"}
            }
          },
          "schemaVersion": {"type": "string", "const": "open-org-evidence/v0.1"},
          "createdAt": {"type": "string", "format": "datetime"}
        }
      }
    }
  }
}
```

## Lexicon: `uk.co.goodship.openorg.signal`

```json
{
  "lexicon": 1,
  "id": "uk.co.goodship.openorg.signal",
  "defs": {
    "main": {
      "type": "record",
      "description": "A funder signal — expression of interest in an org's idea.",
      "key": "tid",
      "record": {
        "type": "object",
        "required": ["orgId", "ideaSlug", "createdAt"],
        "properties": {
          "orgId": {"type": "ref", "ref": "uk.co.goodship.openorg.defs#orgId"},
          "ideaSlug": {"type": "string"},
          "signalType": {
            "type": "string",
            "enum": ["interest", "funding_intent", "introduction"]
          },
          "message": {"type": "string"},
          "contactName": {"type": "string"},
          "contactEmail": {"type": "string"},
          "createdAt": {"type": "string", "format": "datetime"}
        }
      }
    }
  }
}
```

## Identity model

Each organisation gets a DID (Decentralized Identifier):

**Option A: `did:plc:{id}`** — Bluesky's PLC directory
- Pros: rotation keys for portability, battle-tested at scale
- Cons: requires PLC account, dependency on Bluesky infrastructure

**Option B: `did:web:openorg.good-ship.co.uk:{org_id}`** — DNS-based
- Pros: simpler, no PLC dependency, Good Ship controls the domain
- Cons: no rotation keys, less portable

**Recommendation:** Start with `did:web` for Phase 4 simplicity. Migrate to
`did:plc` if orgs demand account portability (moving away from Good Ship's PDS).

Handle: `{org_id}.openorg.good-ship.co.uk` or a custom domain the org owns.

## Architecture (Phase 4 build)

```
                    ┌─────────────────┐
                    │   Murmurations   │
                    │   (discovery     │
                    │    index — kept) │
                    └────────┬────────┘
                             │
┌─────────┐         ┌────────┴────────┐         ┌──────────┐
│  PDS    │────────▶│     Relay        │────────▶│ App View │
│ (org    │  fire   │ (subscribes to   │  index  │ (search, │
│  repos) │  hose   │  openorg.*       │         │  graph)  │
└─────────┘         └─────────────────┘         └──────────┘
```

1. Good Ship runs a PDS (or uses a hosted one)
2. Each published profile/strategy/idea is mirrored as an AT Protocol record
3. A relay subscribes to `uk.co.goodship.openorg.*` collections
4. An App View indexes records, serves the discovery page + graph
5. Auth transitions from magic links to OAuth (atproto's OAuth flow)
6. Murmurations stays as a thin discovery index — the AT Proto relay can feed it

## Migration path

1. **Phase 4a:** Run a PDS alongside the existing FastAPI app. Mirror published
   profiles as AT Protocol records (read-only — no OAuth yet). The relay
   syncs but the App View is just the existing FastAPI discovery route.

2. **Phase 4b:** Add OAuth. Org admins authorize the Open Org app to write
   records to their repo. Magic links remain as fallback during transition.

3. **Phase 4c:** Full federation. Any PDS can host an org. The relay + App
   View handle cross-PDS discovery. Murmurations is fed from the relay.

4. **Phase 4d:** Account portability. Orgs can move PDS without losing their
   profile history. The DID document updates, the relay follows.

## Decision gate

Build the AT Protocol layer in Phase 4 only if:
- Orgs express demand for profile portability (moving away from Good Ship)
- The ecosystem matures (community Lexicon discovery, hosted PDS options)
- Murmurations hits scaling or real-time limits

If none of these conditions are met, Murmurations continues as the sole
federation layer and these Lexicons remain design-only.

## Hybrid architecture (Murmurations + AT Proto)

Both can coexist:
- **Murmurations:** pull-based discovery for aggregators that don't want a relay
- **AT Proto:** push-based real-time federation with signed, portable records

The Murmurations envelope can be generated from the AT Protocol record. The
Murmurations `open_org_profile_url` points to the same JSON the PDS repo
serves. No conflict — just two ways to discover the same data.