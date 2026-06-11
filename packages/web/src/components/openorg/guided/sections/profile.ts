/**
 * Hand-coded section specs for the profile record kind.
 *
 * Section ordering, names, descriptions, hints, and empty-state prose are
 * editorial — the JSON Schema doesn't carry any of these. Field rendering
 * choices (text vs pill vs card) are also editorial.
 */

import type { SectionSpec } from '../bridge';

export type FieldKind =
  | 'text'
  | 'textarea'
  | 'pills'
  | 'card-list'
  | 'group';

export interface FieldDef {
  /** Path inside the section's yaml owner. E.g. ``identity.name`` becomes
   *  ``yaml.identity.name`` in the ParsedSection. */
  key: string;
  label: string;
  kind: FieldKind;
  hint?: string;
  placeholder?: string;
  /** Pill fields: max selected. Soft cap — UX nudge, not enforced. */
  selectionCap?: number;
  /** Pill fields: name of a vocab loaded at runtime (e.g. ``themes``). */
  vocab?: string;
  /** Group fields: nested children. */
  children?: FieldDef[];
  /** Card list fields: shape of one card. */
  cardShape?: FieldDef[];
}

export interface GuidedSection extends SectionSpec {
  name: string;
  description: string;
  emptyPrompt?: string;
  fields: FieldDef[];
}

export const PROFILE_SECTIONS: GuidedSection[] = [
  {
    id: 'identity',
    name: 'Identity',
    description: 'Who you are — the basics anyone looking you up needs to see first.',
    yamlKeys: ['identity'],
    bodyHeadings: [],
    fields: [
      { key: 'identity.name', label: 'Name', kind: 'text', placeholder: 'The Riverside Trust' },
      {
        key: 'identity.also_known_as',
        label: 'Also known as',
        kind: 'card-list',
        hint: 'Any other names you operate under.',
        cardShape: [{ key: 'value', label: 'Alias', kind: 'text' }],
      },
      { key: 'identity.website', label: 'Website', kind: 'text', placeholder: 'https://...' },
      { key: 'identity.founded', label: 'Founded', kind: 'text', hint: 'Year you started.' },
      {
        key: 'identity.contact',
        label: 'Contact',
        kind: 'group',
        children: [
          { key: 'email', label: 'Email', kind: 'text' },
          { key: 'phone', label: 'Phone', kind: 'text' },
        ],
      },
      {
        key: 'identity.geography',
        label: 'Where you work',
        kind: 'group',
        children: [
          { key: 'description', label: 'Description', kind: 'textarea' },
          { key: 'primary_area', label: 'Primary area code', kind: 'text', hint: 'ONS code, e.g. E07000148.' },
        ],
      },
      { key: 'identity.scale', label: 'Scale', kind: 'text', hint: 'local · regional · national · international' },
    ],
  },
  {
    id: 'mission',
    name: 'Mission',
    description: 'What you exist to do, who you serve, and how you go about it.',
    yamlKeys: ['mission'],
    bodyHeadings: ['Mission', 'Theory of change'],
    fields: [
      { key: 'Mission', label: 'Summary', kind: 'textarea', hint: 'One paragraph; what you do, for whom, where.' },
      {
        key: 'mission.themes',
        label: 'Themes',
        kind: 'pills',
        hint: 'The areas of work that define you. Pick up to six.',
        selectionCap: 6,
        vocab: 'themes',
      },
      {
        key: 'mission.beneficiaries',
        label: 'Beneficiaries',
        kind: 'pills',
        hint: 'Who you serve.',
        vocab: 'beneficiaries',
      },
      { key: 'Theory of change', label: 'Theory of change', kind: 'textarea', hint: 'How your work leads to the outcomes you intend.' },
      {
        key: 'mission.programmes',
        label: 'Programmes',
        kind: 'card-list',
        cardShape: [
          { key: 'name', label: 'Name', kind: 'text' },
          { key: 'description', label: 'Description', kind: 'textarea' },
        ],
      },
      { key: 'mission.evidence_summary', label: 'Evidence summary', kind: 'textarea' },
    ],
  },
  {
    id: 'governance',
    name: 'Governance',
    description: 'How you are run.',
    yamlKeys: ['governance'],
    bodyHeadings: [],
    fields: [
      { key: 'governance.board_size', label: 'Board size', kind: 'text' },
      { key: 'governance.accounts_filed_to', label: 'Accounts filed to', kind: 'text', hint: 'e.g. Charity Commission for England and Wales.' },
      {
        key: 'governance.policies',
        label: 'Public policies',
        kind: 'card-list',
        cardShape: [
          { key: 'name', label: 'Policy name', kind: 'text' },
          { key: 'url', label: 'URL', kind: 'text' },
        ],
      },
    ],
  },
  {
    id: 'culture',
    name: 'Culture',
    description: 'What working with you feels like, in your own words.',
    yamlKeys: ['culture'],
    bodyHeadings: [],
    fields: [
      { key: 'culture.narrative', label: 'Narrative', kind: 'textarea', hint: 'A paragraph or two. Honest, not aspirational.' },
    ],
  },
  {
    id: 'values',
    name: 'Values',
    description: 'What you stand by.',
    emptyPrompt: 'What three or four principles do you keep coming back to? Add one to start.',
    yamlKeys: ['values'],
    bodyHeadings: [],
    fields: [
      {
        key: 'values',
        label: 'Values',
        kind: 'card-list',
        cardShape: [
          { key: 'name', label: 'Name', kind: 'text' },
          { key: 'description', label: 'Description', kind: 'textarea' },
        ],
      },
    ],
  },
];
