/**
 * Guards the guided section specs against the JSON Schemas.
 *
 * A guided field must emit the type the schema expects at the key it writes:
 *   - text/textarea -> string leaf      - number -> integer/number leaf
 *   - string-list   -> array<string>    - card-list -> array<object>, and the
 *     cardShape must include every REQUIRED item property
 *   - group         -> object
 * Pointing a scalar control at an object/number leaf, or a card-list at a
 * string array, corrupts the document on edit (e.g. "'national' is not of type
 * 'object'", "{value: …} is not of type 'string'", "'org_name' is a required
 * property").
 *
 * The three maps below mirror the JSON Schemas in
 * packages/core/src/llmstxt_core/open_org/schemas/ — they can't be imported
 * (cross-package; the web package has no node types). Keep them in sync if the
 * schemas change. Body-heading fields are converter-mapped and out of scope.
 */
import { describe, expect, it } from 'vitest';
import { PROFILE_SECTIONS } from './profile';
import { STRATEGY_SECTIONS } from './strategy';
import { IDEA_SECTIONS } from './idea';
import type { FieldDef, FieldKind, GuidedSection } from './profile';

// Frontmatter paths whose schema type is NOT a plain string.
const NON_STRING_SCALAR: Record<string, 'object' | 'number'> = {
  'identity.registration': 'object',
  'identity.identifiers': 'object',
  'identity.contact': 'object',
  'identity.geography': 'object',
  'identity.scale': 'object',
  'mission.evidence_summary': 'object',
  'governance.board_size': 'number',
  'resource_model.current_funding_mix': 'object',
  'place.geolocation.lat': 'number',
  'place.geolocation.lon': 'number',
  'indicative_cost.lower': 'number',
  'indicative_cost.upper': 'number',
};

// Frontmatter paths that are arrays of plain strings.
const STRING_ARRAY_KEYS = ['identity.also_known_as', 'place.area_codes', 'resource_model.resourcing_gaps'];

// Frontmatter paths that are arrays of objects, with their required item props.
const ARRAY_OBJECT_REQUIRED: Record<string, string[]> = {
  'mission.programmes': ['name'],
  'governance.policies': ['name'],
  priorities: ['title'],
  'relationships.partnerships': ['name'],
  evidence_base: ['evidence_id'],
  connections: ['org_name'],
  collaborators: ['org_name'],
};

const SCALAR_COMPATIBLE: Record<'object' | 'number', FieldKind[]> = {
  object: ['group'],
  number: ['number'],
};

/** Map every frontmatter path a spec edits to its FieldDef. */
function collectFields(sections: GuidedSection[]): Map<string, FieldDef> {
  const out = new Map<string, FieldDef>();
  const visit = (field: FieldDef, basePath: string) => {
    const isFrontmatter = field.key === field.key.toLowerCase() && !/\s/.test(field.key);
    if (!basePath && !isFrontmatter) return; // body heading
    const fullPath = basePath ? `${basePath}.${field.key}` : field.key;
    out.set(fullPath, field);
    if (field.kind === 'group') {
      for (const child of field.children ?? []) visit(child, fullPath);
    }
  };
  for (const section of sections) {
    for (const field of section.fields) visit(field, '');
  }
  return out;
}

const FIELDS = new Map<string, FieldDef>([
  ...collectFields(PROFILE_SECTIONS),
  ...collectFields(STRATEGY_SECTIONS),
  ...collectFields(IDEA_SECTIONS),
]);

describe('guided specs are type-consistent with the JSON Schemas', () => {
  for (const [path, schemaType] of Object.entries(NON_STRING_SCALAR)) {
    it(`${path} (schema ${schemaType}) is not edited by a scalar control`, () => {
      const field = FIELDS.get(path);
      if (!field) return; // removed — fine
      expect(SCALAR_COMPATIBLE[schemaType]).toContain(field.kind);
    });
  }

  for (const path of STRING_ARRAY_KEYS) {
    it(`${path} (string array) uses a string-list, not an object card-list`, () => {
      const field = FIELDS.get(path);
      if (!field) return;
      expect(field.kind).toBe('string-list');
    });
  }

  for (const [path, required] of Object.entries(ARRAY_OBJECT_REQUIRED)) {
    it(`${path} (array<object>) is a card-list whose cardShape covers ${required.join(', ')}`, () => {
      const field = FIELDS.get(path);
      if (!field) return;
      expect(field.kind).toBe('card-list');
      const shapeKeys = (field.cardShape ?? []).map((f) => f.key);
      for (const req of required) expect(shapeKeys).toContain(req);
    });
  }
});
