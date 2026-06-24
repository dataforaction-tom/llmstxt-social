# Open Org Area-Code Search & Inference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Open Org editor's free-text area-code box with a name-search control that stores the correct ONS GSS code, suggests codes from Charity Commission data, supports operating areas, and powers a working discovery area filter.

**Architecture:** A pure `search_areas()` function over the existing bundled ONS LAD table, exposed via an unauthenticated `GET /api/open-org/areas` endpoint. The guided editor gains an `area` field kind (a search combobox managing the `(primary_area, primary_area_code)` pair, plus CC suggestion chips and a "nationwide" escape) and an `area-list` kind for `operating_areas`. The discovery filter reuses the same search; the ideas-discovery `area_code` no-op is fixed.

**Tech Stack:** Python 3.11 / FastAPI / pyyaml / pytest (backend); React 18 + TypeScript + Vite + Vitest + axios (frontend).

## Global Constraints

- Backend tests: `cd packages/api && /Users/tomcwxyz/llmstxt-local/.venv/bin/python -m pytest <path> -q`; core: `cd packages/core && /Users/tomcwxyz/llmstxt-local/.venv/bin/python -m pytest <path> -q`.
- Frontend gate: `cd packages/web && npx tsc --noEmit && npx vitest run <path> && npm run lint`.
- `primary_area_code` schema pattern is `^[A-Z][0-9]{8}$` and is **optional**; `primary_area` is a required-when-present `string` (`minLength 1`).
- Area codes are ONS GSS codes; the bundled table (`packages/core/src/llmstxt_core/open_org/data/ons_lad_lookup.json`) holds `entries` as `{name_lowercase: code}` (65 entries) — LAD + UK-nation coverage only.
- Reference-data endpoint is unauthenticated (no secrets, local table). Do NOT add auth.
- Follow existing field-component patterns (`StringListField.tsx`); emit schema-valid shapes (no `{value: …}` wrapper objects).
- One commit per green task. Never `--no-verify`. Conventional Commits, no AI attribution.

---

### Task 1: `search_areas()` over the ONS table

**Files:**
- Modify: `packages/core/src/llmstxt_core/open_org/ons_geography.py`
- Test: `packages/core/tests/open_org/test_ons_geography_search.py` (create)

**Interfaces:**
- Consumes: existing `load_lookup_table()` → `dict[str,str]` (lowercased name → code), `_normalise(str)`.
- Produces: `search_areas(q: str | None, *, limit: int = 10) -> list[dict[str, str]]` returning `[{"code": "E06000005", "name": "Darlington"}, ...]`, prefix matches first then substring, both alpha-sorted, capped at `limit`. Empty/whitespace `q` → `[]`.

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/open_org/test_ons_geography_search.py
from llmstxt_core.open_org.ons_geography import search_areas


def test_empty_query_returns_empty():
    assert search_areas("") == []
    assert search_areas("   ") == []
    assert search_areas(None) == []


def test_matches_are_code_name_dicts():
    results = search_areas("england")
    assert {"code": "E92000001", "name": "England"} in results
    assert all(set(r) == {"code", "name"} for r in results)


def test_prefix_matches_rank_before_substring():
    # "wales" should surface England and Wales (substring) but rank an exact/
    # prefix "Wales" ahead of it.
    results = search_areas("wales")
    names = [r["name"] for r in results]
    assert "Wales" in names
    assert names.index("Wales") < names.index("England And Wales")


def test_normalisation_strips_throughout_prefix():
    assert search_areas("Throughout England") == search_areas("england")


def test_limit_is_capped():
    assert len(search_areas("e", limit=3)) <= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/core && /Users/tomcwxyz/llmstxt-local/.venv/bin/python -m pytest tests/open_org/test_ons_geography_search.py -q`
Expected: FAIL with `ImportError: cannot import name 'search_areas'`.

- [ ] **Step 3: Write minimal implementation**

Add to `ons_geography.py` (after `lookup_lad_code`, before `refresh_from_ons`):

```python
def search_areas(q: str | None, *, limit: int = 10) -> list[dict[str, str]]:
    """Search the LAD table by area name for the editor/discovery typeahead.

    Returns ``[{"code", "name"}, ...]`` with prefix matches first, then
    substring matches, each alpha-sorted, capped at ``limit``. Display names
    are title-cased from the lowercase table keys. Empty query → ``[]``.
    """
    if not q or not q.strip():
        return []
    needle = _normalise(q)
    if not needle:
        return []
    table = load_lookup_table()  # {name_lower: code}
    prefix: list[tuple[str, str]] = []
    substring: list[tuple[str, str]] = []
    for name_lower, code in table.items():
        if name_lower.startswith(needle):
            prefix.append((name_lower, code))
        elif needle in name_lower:
            substring.append((name_lower, code))
    ordered = sorted(prefix) + sorted(substring)
    return [
        {"code": code, "name": name.title()}
        for name, code in ordered[: max(0, limit)]
    ]
```

Add `"search_areas"` to `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/core && /Users/tomcwxyz/llmstxt-local/.venv/bin/python -m pytest tests/open_org/test_ons_geography_search.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/llmstxt_core/open_org/ons_geography.py packages/core/tests/open_org/test_ons_geography_search.py
git commit -m "feat(openorg): add search_areas() over the ONS LAD table"
```

---

### Task 2: `GET /api/open-org/areas` endpoint

**Files:**
- Modify: `packages/api/src/llmstxt_api/routes/open_org_discovery.py`
- Test: `packages/api/tests/test_open_org_areas_route.py` (create)

**Interfaces:**
- Consumes: `llmstxt_core.open_org.ons_geography.search_areas`.
- Produces: `GET /api/open-org/areas?q=<text>&limit=<n>` → `list[{code, name}]`; empty `q` → `[]`; `limit` clamped 1–25 (default 10). Unauthenticated.

- [ ] **Step 1: Write the failing test**

```python
# packages/api/tests/test_open_org_areas_route.py
from fastapi.testclient import TestClient

from llmstxt_api.main import app

client = TestClient(app)


def test_areas_search_returns_code_name_list():
    resp = client.get("/api/open-org/areas", params={"q": "england"})
    assert resp.status_code == 200
    body = resp.json()
    assert {"code": "E92000001", "name": "England"} in body


def test_areas_empty_query_returns_empty_list():
    resp = client.get("/api/open-org/areas", params={"q": ""})
    assert resp.status_code == 200
    assert resp.json() == []


def test_areas_requires_no_auth():
    # Reference data — no cookie/token set on this client.
    assert client.get("/api/open-org/areas", params={"q": "wales"}).status_code == 200


def test_areas_limit_is_clamped():
    resp = client.get("/api/open-org/areas", params={"q": "e", "limit": 3})
    assert resp.status_code == 200
    assert len(resp.json()) <= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/api && /Users/tomcwxyz/llmstxt-local/.venv/bin/python -m pytest tests/test_open_org_areas_route.py -q`
Expected: FAIL — 404 on `/api/open-org/areas`.

- [ ] **Step 3: Write minimal implementation**

In `open_org_discovery.py`: add the import near the top (with the other `llmstxt_core.open_org` imports):

```python
from llmstxt_core.open_org.ons_geography import search_areas
```

Add a response model near the other `BaseModel` definitions:

```python
class AreaResult(BaseModel):
    code: str
    name: str
```

Add the route (place beside the `discover` route; reuses the same `router`, whose prefix is `/api/open-org`):

```python
@router.get("/areas", response_model=list[AreaResult])
async def areas(
    q: str = Query(default="", max_length=120, description="Area name to search"),
    limit: int = Query(default=10, ge=1, le=25),
) -> list[AreaResult]:
    """Search ONS LAD areas by name for the editor / discovery typeahead.

    Public reference data — no auth. Returns ``[]`` for an empty query.
    """
    return [AreaResult(**hit) for hit in search_areas(q, limit=limit)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/api && /Users/tomcwxyz/llmstxt-local/.venv/bin/python -m pytest tests/test_open_org_areas_route.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/llmstxt_api/routes/open_org_discovery.py packages/api/tests/test_open_org_areas_route.py
git commit -m "feat(openorg): GET /api/open-org/areas reference-data search endpoint"
```

---

### Task 3: Make the ideas-discovery `area_code` filter work

**Files:**
- Modify: `packages/api/src/llmstxt_api/routes/open_org_discovery.py` (`IdeaRow`, `_idea_to_row`, `_matches_idea_filters`)
- Test: `packages/api/tests/test_open_org_discover_ideas_area.py` (create)

**Interfaces:**
- Consumes: existing `IdeaRow`, `_idea_to_row(idea, profile)`, `_matches_idea_filters(row, *, q, area_code, cost_max)`.
- Produces: `IdeaRow.primary_area_code: str | None`; `_matches_idea_filters` rejects rows whose `primary_area_code` != a supplied `area_code`.

- [ ] **Step 1: Write the failing test**

```python
# packages/api/tests/test_open_org_discover_ideas_area.py
from llmstxt_api.routes.open_org_discovery import IdeaRow, _matches_idea_filters


def _row(code):
    return IdeaRow(
        org_id="GB-CHC-1",
        slug="s",
        title="t",
        summary="",
        themes=[],
        primary_area="Darlington",
        primary_area_code=code,
    )


def test_area_code_filter_keeps_matching_idea():
    assert _matches_idea_filters(
        _row("E06000005"), q=None, area_code="E06000005", cost_max=None
    )


def test_area_code_filter_drops_non_matching_idea():
    assert not _matches_idea_filters(
        _row("E08000016"), q=None, area_code="E06000005", cost_max=None
    )


def test_no_area_code_filter_keeps_all():
    assert _matches_idea_filters(_row(None), q=None, area_code=None, cost_max=None)
```

(If `IdeaRow` requires additional fields, set them to schema-valid defaults to keep the test focused on `primary_area_code`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/api && /Users/tomcwxyz/llmstxt-local/.venv/bin/python -m pytest tests/test_open_org_discover_ideas_area.py -q`
Expected: FAIL — `IdeaRow` has no `primary_area_code` (and/or area filter not applied).

- [ ] **Step 3: Write minimal implementation**

In `IdeaRow`, add beside `primary_area`:

```python
    primary_area_code: str | None = None
```

In `_idea_to_row`, where `primary_area=geography.get("primary_area")` is set, add:

```python
        primary_area_code=geography.get("primary_area_code"),
```

In `_matches_idea_filters`, add the area check (mirror `_matches_filters`):

```python
    if area_code and row.primary_area_code != area_code:
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/api && /Users/tomcwxyz/llmstxt-local/.venv/bin/python -m pytest tests/test_open_org_discover_ideas_area.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/llmstxt_api/routes/open_org_discovery.py packages/api/tests/test_open_org_discover_ideas_area.py
git commit -m "fix(openorg): apply area_code filter on /discover/ideas (was a no-op)"
```

---

### Task 4: API client `searchAreas`

**Files:**
- Modify: `packages/web/src/api/openorg.ts`
- Test: `packages/web/src/api/openorg.areas.test.ts` (create)

**Interfaces:**
- Consumes: existing `api` axios instance.
- Produces: `export interface AreaResult { code: string; name: string }` and `export async function searchAreas(q: string): Promise<AreaResult[]>` (returns `[]` for blank `q`, else `GET /api/open-org/areas?q=`).

- [ ] **Step 1: Write the failing test**

```ts
// packages/web/src/api/openorg.areas.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { searchAreas } from './openorg';

vi.mock('axios', () => {
  const get = vi.fn();
  return {
    default: { create: () => ({ get, post: vi.fn() }) },
    AxiosError: class extends Error {},
    __get: get,
  };
});

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockedGet = (await import('axios') as any).__get as ReturnType<typeof vi.fn>;

describe('searchAreas', () => {
  beforeEach(() => mockedGet.mockReset());

  it('returns [] for a blank query without calling the API', async () => {
    expect(await searchAreas('   ')).toEqual([]);
    expect(mockedGet).not.toHaveBeenCalled();
  });

  it('calls the areas endpoint and returns the results', async () => {
    mockedGet.mockResolvedValue({ data: [{ code: 'E06000005', name: 'Darlington' }] });
    const out = await searchAreas('darl');
    expect(mockedGet).toHaveBeenCalledWith('/api/open-org/areas', { params: { q: 'darl' } });
    expect(out).toEqual([{ code: 'E06000005', name: 'Darlington' }]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npx vitest run src/api/openorg.areas.test.ts`
Expected: FAIL — `searchAreas` is not exported.

- [ ] **Step 3: Write minimal implementation**

Append to `openorg.ts`:

```ts
export interface AreaResult {
  code: string;
  name: string;
}

/** Search ONS LAD areas by name (editor + discovery typeahead). */
export async function searchAreas(q: string): Promise<AreaResult[]> {
  if (!q.trim()) return [];
  const res = await api.get<AreaResult[]>('/api/open-org/areas', { params: { q } });
  return res.data;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npx vitest run src/api/openorg.areas.test.ts`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/api/openorg.ts packages/web/src/api/openorg.areas.test.ts
git commit -m "feat(web): searchAreas API client for area typeahead"
```

---

### Task 5: `AreaField` component (primary area + code pair)

**Files:**
- Create: `packages/web/src/components/openorg/guided/fields/AreaField.tsx`
- Test: `packages/web/src/components/openorg/guided/fields/AreaField.test.tsx`

**Interfaces:**
- Consumes: `searchAreas`, `AreaResult` from `../../../../api/openorg`.
- Produces: default-exported `AreaField` with props:
  ```ts
  interface AreaFieldProps {
    label: string;
    code: string;            // current primary_area_code
    name: string;            // current primary_area (display)
    suggestionNames?: string[]; // CC-derived candidate names to resolve into chips
    hint?: string;
    onSelect: (sel: { code: string; name: string }) => void;
    onClear: () => void;     // "nationwide / not a specific area"
  }
  ```

- [ ] **Step 1: Write the failing test**

```tsx
// AreaField.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AreaField from './AreaField';

vi.mock('../../../../api/openorg', () => ({
  searchAreas: vi.fn(),
}));
import { searchAreas } from '../../../../api/openorg';
const mockSearch = searchAreas as unknown as ReturnType<typeof vi.fn>;

beforeEach(() => mockSearch.mockReset());

function setup(props = {}) {
  const onSelect = vi.fn();
  const onClear = vi.fn();
  render(
    <AreaField label="Primary area" code="" name="" onSelect={onSelect} onClear={onClear} {...props} />,
  );
  return { onSelect, onClear };
}

describe('AreaField', () => {
  it('shows the current area name when set', () => {
    setup({ code: 'E06000005', name: 'Darlington' });
    expect(screen.getByDisplayValue('Darlington')).toBeInTheDocument();
  });

  it('searches as you type and selecting a result emits the pair', async () => {
    mockSearch.mockResolvedValue([{ code: 'E06000005', name: 'Darlington' }]);
    const { onSelect } = setup();
    fireEvent.change(screen.getByLabelText('Primary area'), { target: { value: 'darl' } });
    const option = await screen.findByText(/Darlington/);
    fireEvent.click(option);
    expect(onSelect).toHaveBeenCalledWith({ code: 'E06000005', name: 'Darlington' });
  });

  it('nationwide button clears the code', () => {
    const { onClear } = setup({ code: 'E06000005', name: 'Darlington' });
    fireEvent.click(screen.getByRole('button', { name: /nationwide/i }));
    expect(onClear).toHaveBeenCalled();
  });

  it('renders CC suggestion chips and clicking one emits the pair', async () => {
    mockSearch.mockResolvedValue([{ code: 'E06000005', name: 'Darlington' }]);
    const { onSelect } = setup({ suggestionNames: ['Darlington'] });
    const chip = await screen.findByRole('button', { name: /Darlington · E06000005/ });
    fireEvent.click(chip);
    expect(onSelect).toHaveBeenCalledWith({ code: 'E06000005', name: 'Darlington' });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npx vitest run src/components/openorg/guided/fields/AreaField.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```tsx
// AreaField.tsx
import { useEffect, useId, useRef, useState } from 'react';
import { searchAreas, type AreaResult } from '../../../../api/openorg';

interface AreaFieldProps {
  label: string;
  code: string;
  name: string;
  suggestionNames?: string[];
  hint?: string;
  onSelect: (sel: { code: string; name: string }) => void;
  onClear: () => void;
}

export default function AreaField({
  label,
  code,
  name,
  suggestionNames = [],
  hint,
  onSelect,
  onClear,
}: AreaFieldProps) {
  const id = useId();
  const [query, setQuery] = useState(name);
  const [results, setResults] = useState<AreaResult[]>([]);
  const [open, setOpen] = useState(false);
  const [chips, setChips] = useState<AreaResult[]>([]);
  const debounced = useRef<ReturnType<typeof setTimeout>>();

  // Keep the input in sync when the stored name changes (e.g. chip select).
  useEffect(() => setQuery(name), [name]);

  // Debounced search-as-you-type.
  useEffect(() => {
    if (debounced.current) clearTimeout(debounced.current);
    if (!open || !query.trim() || query === name) {
      setResults([]);
      return;
    }
    debounced.current = setTimeout(() => {
      searchAreas(query).then(setResults).catch(() => setResults([]));
    }, 250);
    return () => debounced.current && clearTimeout(debounced.current);
  }, [query, open, name]);

  // Resolve CC suggestion names into code chips (top hit each, deduped by code).
  useEffect(() => {
    let cancelled = false;
    Promise.all(suggestionNames.map((n) => searchAreas(n).then((r) => r[0])))
      .then((hits) => {
        if (cancelled) return;
        const seen = new Set<string>();
        const out: AreaResult[] = [];
        for (const h of hits) {
          if (h && !seen.has(h.code)) {
            seen.add(h.code);
            out.push(h);
          }
        }
        setChips(out);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [suggestionNames.join('|')]);

  const choose = (r: AreaResult) => {
    onSelect({ code: r.code, name: r.name });
    setOpen(false);
    setResults([]);
  };

  return (
    <div className="flex flex-col text-sm">
      <label id={id} className="kicker mb-2">
        {label}
      </label>
      <input
        type="text"
        aria-labelledby={id}
        aria-label={label}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        placeholder="Search a council or area name…"
        className="border border-rule bg-paper px-3 py-2 text-base text-ink focus:border-ink focus:outline-none"
      />
      {code && <span className="mt-1 text-xs text-muted">Code: {code}</span>}

      {open && results.length > 0 && (
        <ul className="mt-1 border border-rule bg-paper">
          {results.map((r) => (
            <li key={r.code}>
              <button
                type="button"
                onClick={() => choose(r)}
                className="block w-full px-3 py-2 text-left hover:bg-paper-2"
              >
                {r.name} <span className="text-xs text-muted">· {r.code}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {chips.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          <span className="text-xs text-muted">Suggested:</span>
          {chips.map((c) => (
            <button
              key={c.code}
              type="button"
              onClick={() => choose(c)}
              className="border border-rule bg-paper-2 px-2 py-1 text-xs text-ink hover:bg-paper"
            >
              {c.name} · {c.code}
            </button>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={onClear}
        className="mt-2 self-start text-xs uppercase tracking-wider text-muted hover:text-ink"
      >
        Nationwide / not a specific area
      </button>
      {hint && <span className="mt-2 text-xs italic text-muted">{hint}</span>}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npx vitest run src/components/openorg/guided/fields/AreaField.test.tsx`
Expected: PASS (4 passed). If the debounced search test flakes, the test uses `findByText` which retries; no fake timers needed because 250ms < default 1000ms RTL timeout.

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/guided/fields/AreaField.tsx packages/web/src/components/openorg/guided/fields/AreaField.test.tsx
git commit -m "feat(web): AreaField search combobox with CC chips + nationwide"
```

---

### Task 6: `AreaListField` component (operating areas)

**Files:**
- Create: `packages/web/src/components/openorg/guided/fields/AreaListField.tsx`
- Test: `packages/web/src/components/openorg/guided/fields/AreaListField.test.tsx`

**Interfaces:**
- Consumes: `searchAreas`, `AreaResult`.
- Produces: default-exported `AreaListField` with props `{ label: string; value: string[]; hint?: string; onChange: (next: string[]) => void }`. Emits a flat `string[]` of area **names** (schema-valid for `operating_areas`).

- [ ] **Step 1: Write the failing test**

```tsx
// AreaListField.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AreaListField from './AreaListField';

vi.mock('../../../../api/openorg', () => ({ searchAreas: vi.fn() }));
import { searchAreas } from '../../../../api/openorg';
const mockSearch = searchAreas as unknown as ReturnType<typeof vi.fn>;
beforeEach(() => mockSearch.mockReset());

describe('AreaListField', () => {
  it('lists current area names', () => {
    render(<AreaListField label="Also operates in" value={['Leeds', 'York']} onChange={vi.fn()} />);
    expect(screen.getByText('Leeds')).toBeInTheDocument();
    expect(screen.getByText('York')).toBeInTheDocument();
  });

  it('searching and selecting appends the area name', async () => {
    mockSearch.mockResolvedValue([{ code: 'E08000035', name: 'Leeds' }]);
    const onChange = vi.fn();
    render(<AreaListField label="Also operates in" value={[]} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('Add an area'), { target: { value: 'lee' } });
    fireEvent.click(await screen.findByText(/Leeds/));
    expect(onChange).toHaveBeenCalledWith(['Leeds']);
  });

  it('remove drops the area', () => {
    const onChange = vi.fn();
    render(<AreaListField label="Also operates in" value={['Leeds']} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /remove leeds/i }));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npx vitest run src/components/openorg/guided/fields/AreaListField.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```tsx
// AreaListField.tsx
import { useEffect, useId, useRef, useState } from 'react';
import { searchAreas, type AreaResult } from '../../../../api/openorg';

interface AreaListFieldProps {
  label: string;
  value: string[];
  onChange: (next: string[]) => void;
  hint?: string;
}

export default function AreaListField({ label, value, onChange, hint }: AreaListFieldProps) {
  const id = useId();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<AreaResult[]>([]);
  const debounced = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    if (debounced.current) clearTimeout(debounced.current);
    if (!query.trim()) {
      setResults([]);
      return;
    }
    debounced.current = setTimeout(() => {
      searchAreas(query).then(setResults).catch(() => setResults([]));
    }, 250);
    return () => debounced.current && clearTimeout(debounced.current);
  }, [query]);

  const add = (r: AreaResult) => {
    if (!value.includes(r.name)) onChange([...value, r.name]);
    setQuery('');
    setResults([]);
  };
  const remove = (name: string) => onChange(value.filter((v) => v !== name));

  return (
    <div className="flex flex-col text-sm">
      <span id={id} className="kicker mb-2">
        {label}
      </span>
      <ul className="flex flex-col gap-2" aria-labelledby={id}>
        {value.map((name) => (
          <li key={name} className="flex items-center gap-2">
            <span className="flex-1 border border-rule bg-paper px-3 py-2 text-base text-ink">{name}</span>
            <button
              type="button"
              onClick={() => remove(name)}
              aria-label={`Remove ${name}`}
              className="border border-rule px-3 text-xs uppercase tracking-wider text-muted hover:text-red-900"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
      <input
        type="text"
        aria-label="Add an area"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search a council or area name…"
        className="mt-2 border border-rule bg-paper px-3 py-2 text-base text-ink focus:border-ink focus:outline-none"
      />
      {results.length > 0 && (
        <ul className="mt-1 border border-rule bg-paper">
          {results.map((r) => (
            <li key={r.code}>
              <button
                type="button"
                onClick={() => add(r)}
                className="block w-full px-3 py-2 text-left hover:bg-paper-2"
              >
                {r.name} <span className="text-xs text-muted">· {r.code}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {hint && <span className="mt-2 text-xs italic text-muted">{hint}</span>}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npx vitest run src/components/openorg/guided/fields/AreaListField.test.tsx`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add packages/web/src/components/openorg/guided/fields/AreaListField.tsx packages/web/src/components/openorg/guided/fields/AreaListField.test.tsx
git commit -m "feat(web): AreaListField multi-add area search for operating_areas"
```

---

### Task 7: Wire `area` / `area-list` kinds into the guided editor

**Files:**
- Modify: `packages/web/src/components/openorg/guided/sections/profile.ts` (FieldKind union + FieldDef `nameKey`/`suggestFromKeys`; geography fields)
- Modify: `packages/web/src/components/openorg/guided/Section.tsx` (import + `area`/`area-list` branches)
- Test: `packages/web/src/components/openorg/guided/Section.area.test.tsx` (create)

**Interfaces:**
- Consumes: `AreaField` (Task 5), `AreaListField` (Task 6), existing `getByPath`/`setByPath`.
- Produces: `FieldKind` includes `'area' | 'area-list'`; `FieldDef` gains `nameKey?: string` and `suggestFromKeys?: string[]`. `Section` renders an `area` field that writes the `(primary_area_code, primary_area)` pair and an `area-list` writing `operating_areas`.

- [ ] **Step 1: Write the failing test**

```tsx
// Section.area.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Section from './Section';
import type { GuidedSection } from './sections/profile';
import type { ParsedSection } from './bridge';

vi.mock('../../../api/openorg', () => ({ searchAreas: vi.fn().mockResolvedValue([]) }));

const section: GuidedSection = {
  id: 'geo',
  name: 'Where you work',
  description: '',
  fields: [
    {
      key: 'identity.geography.primary_area_code',
      nameKey: 'identity.geography.primary_area',
      suggestFromKeys: ['identity.geography.primary_area'],
      label: 'Primary area',
      kind: 'area',
    },
  ],
} as GuidedSection;

function parsed(): ParsedSection {
  return {
    yaml: { identity: { geography: { primary_area: 'Darlington', primary_area_code: 'E06000005' } } },
    body: {},
  };
}

describe('Section area field', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the area field with the current name', () => {
    render(<Section section={section} parsed={parsed()} onChange={vi.fn()} vocabs={{}} />);
    expect(screen.getByDisplayValue('Darlington')).toBeInTheDocument();
  });

  it('nationwide clears the code but keeps the name', () => {
    const onChange = vi.fn();
    render(<Section section={section} parsed={parsed()} onChange={onChange} vocabs={{}} />);
    fireEvent.click(screen.getByRole('button', { name: /nationwide/i }));
    const next = onChange.mock.calls[0][0] as ParsedSection;
    const geo = (next.yaml.identity as any).geography;
    expect(geo.primary_area_code).toBe('');
    expect(geo.primary_area).toBe('Darlington');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npx vitest run src/components/openorg/guided/Section.area.test.tsx`
Expected: FAIL — `area` kind renders "Unsupported field kind".

- [ ] **Step 3: Write minimal implementation**

In `profile.ts`, extend the `FieldKind` union to include `'area'` and `'area-list'`, and add to `FieldDef`:

```ts
  nameKey?: string;          // area: companion text key for primary_area
  suggestFromKeys?: string[]; // area: keys whose text values seed CC chips
```

Replace the geography group's `primary_area` text child and add operating areas. In the profile section's geography area, set:

```ts
      {
        key: 'identity.geography.description',
        label: 'Where you work (description)',
        kind: 'textarea',
        hint: 'Briefly, the places you serve.',
      },
      {
        key: 'identity.geography.primary_area_code',
        nameKey: 'identity.geography.primary_area',
        suggestFromKeys: ['identity.geography.primary_area', 'identity.geography.operating_areas'],
        label: 'Primary area',
        kind: 'area',
        hint: 'Search a council/area; we store the official ONS code.',
      },
      {
        key: 'identity.geography.operating_areas',
        label: 'Also operates in',
        kind: 'area-list',
      },
```

(Remove the old `identity.geography` `group` field carrying `description`/`primary_area`; keep the `contact` group as-is.)

In `Section.tsx`, add the import:

```tsx
import AreaField from './fields/AreaField';
import AreaListField from './fields/AreaListField';
```

Add helper above `renderField` to gather suggestion names:

```tsx
function gatherNames(parsed: ParsedSection, keys: string[]): string[] {
  const out: string[] = [];
  for (const key of keys) {
    const v = getByPath(parsed, key);
    if (typeof v === 'string' && v.trim()) out.push(v);
    else if (Array.isArray(v)) out.push(...v.filter((x): x is string => typeof x === 'string'));
  }
  return out;
}
```

Add branches in `renderField` (before the final `return <span>…Unsupported`):

```tsx
  if (field.kind === 'area') {
    const nameKey = field.nameKey ?? field.key;
    const name = getByPath(parsed, nameKey);
    return (
      <AreaField
        key={field.key}
        label={field.label}
        code={typeof value === 'string' ? value : ''}
        name={typeof name === 'string' ? name : ''}
        suggestionNames={gatherNames(parsed, field.suggestFromKeys ?? [])}
        hint={field.hint}
        onSelect={(sel) =>
          onChange(setByPath(setByPath(parsed, field.key, sel.code), nameKey, sel.name))
        }
        onClear={() => onChange(setByPath(parsed, field.key, ''))}
      />
    );
  }
  if (field.kind === 'area-list') {
    return (
      <AreaListField
        key={field.key}
        label={field.label}
        value={Array.isArray(value) ? (value as unknown[]).filter((v): v is string => typeof v === 'string') : []}
        hint={field.hint}
        onChange={(v) => onChange(setByPath(parsed, field.key, v))}
      />
    );
  }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npx vitest run src/components/openorg/guided/Section.area.test.tsx`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the schema-consistency guard + full guided tests**

Run: `cd packages/web && npx vitest run src/components/openorg/guided && npx tsc --noEmit`
Expected: PASS, tsc clean. (If `schemaConsistency.test.ts` enumerates field kinds, add `'area'`/`'area-list'` mappings there to the string/array schema types respectively.)

- [ ] **Step 6: Commit**

```bash
git add packages/web/src/components/openorg/guided/sections/profile.ts packages/web/src/components/openorg/guided/Section.tsx packages/web/src/components/openorg/guided/Section.area.test.tsx
git commit -m "feat(web): area + area-list field kinds for geography in the guided editor"
```

---

### Task 8: Discovery filter — area search combobox

**Files:**
- Create: `packages/web/src/components/openorg/AreaSearchInput.tsx` (small shared combobox returning a selected `{code, name}`)
- Modify: `packages/web/src/pages/openorg/Discover.tsx` (replace the free-text area-code input with `AreaSearchInput`)
- Test: `packages/web/src/components/openorg/AreaSearchInput.test.tsx`

**Interfaces:**
- Consumes: `searchAreas`, `AreaResult`.
- Produces: default-exported `AreaSearchInput` with props `{ label?: string; value: string; displayName?: string; onSelect: (sel: { code: string; name: string }) => void; onClear: () => void }`.

- [ ] **Step 1: Write the failing test**

```tsx
// AreaSearchInput.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AreaSearchInput from './AreaSearchInput';

vi.mock('../../api/openorg', () => ({ searchAreas: vi.fn() }));
import { searchAreas } from '../../api/openorg';
const mockSearch = searchAreas as unknown as ReturnType<typeof vi.fn>;
beforeEach(() => mockSearch.mockReset());

describe('AreaSearchInput', () => {
  it('selecting a result emits the code/name', async () => {
    mockSearch.mockResolvedValue([{ code: 'E06000005', name: 'Darlington' }]);
    const onSelect = vi.fn();
    render(<AreaSearchInput value="" onSelect={onSelect} onClear={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/area/i), { target: { value: 'darl' } });
    fireEvent.click(await screen.findByText(/Darlington/));
    expect(onSelect).toHaveBeenCalledWith({ code: 'E06000005', name: 'Darlington' });
  });

  it('clear button resets the filter', () => {
    const onClear = vi.fn();
    render(<AreaSearchInput value="E06000005" displayName="Darlington" onSelect={vi.fn()} onClear={onClear} />);
    fireEvent.click(screen.getByRole('button', { name: /clear/i }));
    expect(onClear).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && npx vitest run src/components/openorg/AreaSearchInput.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```tsx
// AreaSearchInput.tsx
import { useEffect, useRef, useState } from 'react';
import { searchAreas, type AreaResult } from '../../api/openorg';

interface AreaSearchInputProps {
  label?: string;
  value: string;          // selected code ('' = none)
  displayName?: string;
  onSelect: (sel: { code: string; name: string }) => void;
  onClear: () => void;
}

export default function AreaSearchInput({
  label = 'Area',
  value,
  displayName = '',
  onSelect,
  onClear,
}: AreaSearchInputProps) {
  const [query, setQuery] = useState(displayName);
  const [results, setResults] = useState<AreaResult[]>([]);
  const debounced = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => setQuery(displayName), [displayName]);

  useEffect(() => {
    if (debounced.current) clearTimeout(debounced.current);
    if (!query.trim() || query === displayName) {
      setResults([]);
      return;
    }
    debounced.current = setTimeout(() => {
      searchAreas(query).then(setResults).catch(() => setResults([]));
    }, 250);
    return () => debounced.current && clearTimeout(debounced.current);
  }, [query, displayName]);

  return (
    <div className="flex flex-col text-sm">
      <input
        type="text"
        aria-label={label}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Filter by area…"
        className="border border-rule bg-paper px-3 py-2 text-base text-ink focus:border-ink focus:outline-none"
      />
      {value && (
        <button type="button" onClick={onClear} className="mt-1 self-start text-xs text-muted hover:text-ink">
          Clear area filter
        </button>
      )}
      {results.length > 0 && (
        <ul className="mt-1 border border-rule bg-paper">
          {results.map((r) => (
            <li key={r.code}>
              <button
                type="button"
                onClick={() => {
                  onSelect({ code: r.code, name: r.name });
                  setResults([]);
                }}
                className="block w-full px-3 py-2 text-left hover:bg-paper-2"
              >
                {r.name} <span className="text-xs text-muted">· {r.code}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/web && npx vitest run src/components/openorg/AreaSearchInput.test.tsx`
Expected: PASS (2 passed).

- [ ] **Step 5: Wire it into Discover.tsx**

In `Discover.tsx`, replace the free-text area-code `<input>` (the `draftAreaCode` control) with:

```tsx
<AreaSearchInput
  value={filters.area_code ?? ''}
  displayName={areaName}
  onSelect={(sel) => {
    setAreaName(sel.name);
    applyFilter({ area_code: sel.code });
  }}
  onClear={() => {
    setAreaName('');
    applyFilter({ area_code: undefined });
  }}
/>
```

Add `const [areaName, setAreaName] = useState('');` beside the other `useState` hooks, import `AreaSearchInput`, and remove the now-unused `draftAreaCode` state and its input. Keep `applyFilter` and the existing `filters.area_code` plumbing (the org discover endpoint already filters on it).

- [ ] **Step 6: Verify the page gate**

Run: `cd packages/web && npx tsc --noEmit && npx vitest run && npm run lint`
Expected: tsc clean, all vitest pass, lint clean.

- [ ] **Step 7: Commit**

```bash
git add packages/web/src/components/openorg/AreaSearchInput.tsx packages/web/src/components/openorg/AreaSearchInput.test.tsx packages/web/src/pages/openorg/Discover.tsx
git commit -m "feat(web): area-search filter on Discover (replaces free-text area code)"
```

---

### Task 9: Full-suite verification + live smoke

**Files:** none (verification only)

- [ ] **Step 1: Backend suites**

Run:
```
cd packages/core && /Users/tomcwxyz/llmstxt-local/.venv/bin/python -m pytest tests/ -q
cd packages/api && /Users/tomcwxyz/llmstxt-local/.venv/bin/python -m pytest tests/ -q
```
Expected: all green.

- [ ] **Step 2: Frontend gate**

Run: `cd packages/web && npx tsc --noEmit && npx vitest run && npm run lint`
Expected: tsc clean, all vitest pass, lint clean.

- [ ] **Step 3: Live smoke on the test stack**

The endpoint is backend-only (mounted source) — restart not needed for `packages/api`, but the new core `search_areas` requires a worker/api restart since it lives in `packages/core`:
```
docker compose -p llmstxt-test -f docker-compose.test.yml restart api
curl -s -H 'Host: openorg.good-ship.co.uk' 'http://localhost:8010/api/open-org/areas?q=darlington'
```
Expected: `[{"code":"E06000005","name":"Darlington"}]` (or similar). Rebuild the SPA image for browser testing of the editor field: `docker compose -p llmstxt-test -f docker-compose.test.yml build api && docker compose -p llmstxt-test -f docker-compose.test.yml up -d --force-recreate api`.

- [ ] **Step 4: Final commit (if any verification fixups were needed)**

```bash
git commit -am "test(openorg): area-code search end-to-end verification"
```

---

## Notes for the implementer

- **Field kinds** are dispatched in `Section.tsx::renderField`; the `area` field is the only one that writes *two* document keys (code + name) — it chains `setByPath`.
- The org `/discover` endpoint already filters on `area_code` (`_matches_filters`); only the **ideas** endpoint needed the fix (Task 3).
- Display names are title-cased from lowercase table keys — acceptable for v1 ("England And Wales" is cosmetically imperfect but unambiguous).
- Coverage is LAD + nations only; the **Nationwide / not a specific area** escape (Task 5) is the honest fallback when CC names don't resolve — it clears the code and leaves the `primary_area` text.
