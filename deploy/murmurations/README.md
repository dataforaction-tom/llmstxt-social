# Murmurations schema submission

Files in this directory are the upstream submission package for the Murmurations Library — a federated index of organisations and projects. We register the `open_org_profile-v0.1.0` schema so any host (us, our partners, third parties) can publish Open Org profiles to a shared discovery index.

## Files

- **`open_org_profile-v0.1.0.json`** — the Murmurations schema. Defines the required fields (`linked_schemas`, `name`, `primary_url`, `tags`, `org_id_guide`) and Open Org extensions (`registration`, `primary_area`, `annual_income_band`, `strategy_themes`, `ideas_count`, `open_org_profile_url`, `schema_version`). Note this is a *thin* schema — the index only stores discovery-relevant fields. The full Open Org profile JSON is fetched separately from `open_org_profile_url`.
- **`reference_profile.json`** — a worked example matching the spec's section 3 fixture. Useful when validating a real submission against the test index.

## How to submit

1. Validate the schema locally:
   ```bash
   curl -X POST -H 'Content-Type: application/json' \
     --data @deploy/murmurations/reference_profile.json \
     https://test-index.murmurations.network/v2/validate
   ```
2. Open a PR against [MurmurationsNetwork/MurmurationsLibrary](https://github.com/MurmurationsNetwork/MurmurationsLibrary) adding `library/schemas/open_org_profile-v0.1.0.json` (path may vary; check current Library conventions before opening).
3. Notify the Murmurations team in their forum/Discord that the PR is open.
4. While waiting for upstream merge, the Phase 1 build runs against `test-index.murmurations.network` so end-to-end submission can be exercised.

## Theme tags

The `tags` array uses the Open Org controlled vocabulary of 30 theme keys. The canonical list lives at `packages/core/src/llmstxt_core/open_org/data/themes.json`. If themes are added or retired, this schema's documentation (and any Murmurations-side tooling that filters on tags) should be reviewed for impact.

## Schema versioning

We follow Murmurations' `name-vMAJOR.MINOR.PATCH` convention. Phase 1 begins at `v0.1.0`. Breaking changes (renaming or removing required fields) bump the major; additive changes bump the minor; doc-only changes bump the patch. Open Org's own `schema_version` field (`open-org/v0.1`) tracks the full-profile schema separately and may version differently.
