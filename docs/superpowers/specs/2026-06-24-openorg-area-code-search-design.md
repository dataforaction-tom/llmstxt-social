# Open Org — area-code search & inference

> Status: approved design · 2026-06-24
> Scope: editor area field (primary + operating areas), CC-driven suggestions,
> working discovery area filter.

## Problem

The Open Org profile editor exposes `identity.geography.primary_area_code` as a
**free-text box**. The codes are ONS GSS codes (`^[A-Z][0-9]{8}$`, e.g.
`E06000005`) — not something a user can type from memory, and an unconstrained
box invites invalid values. The data to do better already exists:

- `llmstxt_core.open_org.ons_geography` bundles a Local Authority District (LAD)
  lookup: `load_lookup_table()` (area-name → GSS code), `lookup_lad_code()`,
  `load_centroid_table()`.
- The Charity Commission enricher returns `area_of_operation: list[str]` (free
  text), and the generator already attempts CC → code inference at generation
  time — but coverage is LAD-only and sparse, and CC areas are often regions or
  "England and Wales" with no single LAD code.
- The discovery area filter currently takes a raw `area_code`; the
  `/discover/ideas` variant ignores it entirely (a known no-op).

## Goals

1. Replace the free-text primary-area-code box with a **name search** that
   stores the GSS code.
2. Use CC data to **suggest** area codes as one-tap chips the user confirms.
3. Support **operating areas** (the schema's `operating_areas` string array).
4. Make the **discovery area filter** work via the same search.

## Non-goals (YAGNI)

- Auto-setting `geolocation` from the area centroid — geolocation is already
  derived at publish time from postcode/centroid.
- Live ONS refresh — the bundled LAD table is sufficient.
- Per-item codes on `operating_areas` — the schema is `string[]`; we store
  area **names** there.

## Key design point: area is a (name, code) pair

The schema stores `primary_area` (text, `minLength 1`) and `primary_area_code`
(GSS code, optional) **separately**. The area field manages them together:
selecting "Darlington" sets `primary_area="Darlington"` **and**
`primary_area_code="E06000005"`. The text field carries the display name, so no
reverse code→name lookup is needed, and the "nationwide" case is just text with
an empty code.

## Components

### 1. `ons_geography.search_areas(q, limit=10) -> list[dict]`
Pure function over the LAD table. Returns `[{"code": "E06000005", "name":
"Darlington"}, ...]`, preserving original-case display names. Reuses
`_normalise` (strips "Throughout/Across/…" prefixes) for matching. Substring /
prefix match on the normalised name, case-insensitive, capped at `limit`. Empty
or whitespace `q` returns `[]`.

*Data note:* `load_lookup_table()` lowercases its keys; `search_areas` reads the
raw entries to keep display casing (add a `load_display_table()` helper or read
the raw dict directly).

### 2. `GET /api/open-org/areas?q=<text>&limit=<n>`
Thin route in `open_org_discovery.py` (or a small `open_org_areas.py`) returning
`search_areas` output. **Unauthenticated** read-only reference data (no secrets,
local table, cheap). Validates `q` length; clamps `limit` (default 10, max 25).
Powers both the editor typeahead and the discovery filter.

### 3. Guided editor — new `area` field kind
A search-as-you-type combobox (debounced) hitting `/api/open-org/areas`:
- On select → write the `(primary_area, primary_area_code)` pair into the
  document via the existing bridge.
- **Suggestion chips:** derive candidate names from the profile's existing
  `primary_area` + `operating_areas` text (CC-sourced at generation); run each
  through the search and show the top hit as a one-tap chip
  ("Set Darlington · E06000005").
- **"Nationwide / not a specific area"** toggle: keeps `primary_area` text,
  clears `primary_area_code` (optional in schema).
- **Operating areas:** a multi-add variant of the same search that appends the
  selected area **name** to the `operating_areas` array (reuse/extend the
  existing `StringListField` with an optional search source).

### 4. Discovery filter
Replace the free-text area input with the same combobox (search by name → filter
by `area_code`). Fix the `/discover/ideas` `area_code` application so it filters
(surface `primary_area_code` on the idea row and apply it), matching the org
discovery behaviour.

## Data flow

```
Generation (existing):  CC area_of_operation ──▶ primary_area (text)
                                              └─▶ primary_area_code (if LAD match)
                                              └─▶ operating_areas (names)

Editor:  user types ──▶ GET /areas?q ──▶ pick ──▶ {primary_area, primary_area_code}
         CC names ────▶ GET /areas?q (top hit) ──▶ suggestion chip ──▶ same pair
         nationwide ─▶ primary_area kept, code cleared

Discovery: user types ──▶ GET /areas?q ──▶ pick code ──▶ filter by area_code
```

## Error handling / edges

- No matches → empty list; the field shows "no matching area — try a council
  name, or choose Nationwide".
- Endpoint failure → the field degrades to letting the user keep existing text;
  never blocks the editor.
- Invalid stored code (legacy/free-text) → still displayed via `primary_area`
  text; re-selecting fixes the code.

## Testing

- `search_areas`: match, prefix-strip normalisation, case-insensitivity, limit
  clamp, empty `q`.
- Route: 200 + shape, empty `q` → `[]`, `limit` clamp.
- Editor `area` field: select sets the pair; chip sets the pair; nationwide
  clears the code; operating-areas add appends a name.
- Discovery: area filter narrows org results; `/discover/ideas` honours
  `area_code` (regression for the no-op).

## Out-of-scope follow-ups

- Centroid → `geolocation` autofill on area select (nice-to-have for map pins).
- Welsh/Scottish/NI coverage beyond the bundled LAD table.
