import type { GuidedSection } from './profile';

export const IDEA_SECTIONS: GuidedSection[] = [
  {
    id: 'summary',
    name: 'Summary',
    description: 'A name, status, and short summary.',
    yamlKeys: ['id', 'status'],
    bodyHeadings: ['Summary'],
    fields: [
      { key: 'id', label: 'Slug', kind: 'text', hint: 'URL-stable id, lowercase-and-dashes.' },
      {
        key: 'status',
        label: 'Status',
        kind: 'pills',
        selectionCap: 1,
        vocab: 'idea_status',
      },
      { key: 'Summary', label: 'Summary', kind: 'textarea', hint: 'One paragraph; the idea in plain English.' },
    ],
  },
  {
    id: 'detail',
    name: 'Detail',
    description: 'The longer explanation.',
    yamlKeys: [],
    bodyHeadings: ['The detail'],
    fields: [
      { key: 'The detail', label: 'Detail', kind: 'textarea' },
    ],
  },
  {
    id: 'place',
    name: 'Place',
    description: 'Where this would happen.',
    yamlKeys: ['place'],
    bodyHeadings: [],
    fields: [
      {
        key: 'place',
        label: 'Place',
        kind: 'group',
        children: [
          { key: 'description', label: 'Description', kind: 'textarea' },
          { key: 'area_codes', label: 'Area codes', kind: 'string-list', hint: 'ONS codes, e.g. E07000148.' },
          // geolocation (lat/lon numbers) is derived from area codes
          // downstream, not hand-entered. Preserved in the markdown.
        ],
      },
    ],
  },
  {
    id: 'themes_beneficiaries',
    name: 'Themes & beneficiaries',
    description: 'What it is about and who it is for.',
    yamlKeys: ['themes', 'beneficiaries'],
    bodyHeadings: [],
    fields: [
      { key: 'themes', label: 'Themes', kind: 'pills', selectionCap: 6, vocab: 'themes' },
      { key: 'beneficiaries', label: 'Beneficiaries', kind: 'pills', vocab: 'beneficiaries' },
    ],
  },
  {
    id: 'indicative_cost',
    name: 'Indicative cost',
    description: 'Rough order of magnitude — refine later.',
    yamlKeys: ['indicative_cost'],
    bodyHeadings: [],
    fields: [
      {
        key: 'indicative_cost',
        label: 'Cost',
        kind: 'group',
        children: [
          { key: 'lower', label: 'Lower', kind: 'number' },
          { key: 'upper', label: 'Upper', kind: 'number' },
          { key: 'currency', label: 'Currency', kind: 'text', placeholder: 'GBP' },
          { key: 'period', label: 'Period', kind: 'text', placeholder: 'one-off / per-year' },
        ],
      },
    ],
  },
  {
    id: 'evidence_base',
    name: 'Evidence base',
    description: 'What this is built on.',
    emptyPrompt: 'A study, a report, your own data — add one to start.',
    yamlKeys: ['evidence_base'],
    bodyHeadings: [],
    fields: [
      {
        key: 'evidence_base',
        label: 'Evidence',
        kind: 'card-list',
        cardShape: [
          { key: 'evidence_id', label: 'Reference', kind: 'text', hint: 'A short id, DOI, or URL.' },
          { key: 'relevance', label: 'Relevance', kind: 'textarea' },
        ],
      },
    ],
  },
  {
    id: 'connections',
    name: 'Connections',
    description: 'Who else cares, who might help.',
    yamlKeys: ['connections', 'collaborators', 'linked_strategy_id'],
    bodyHeadings: [],
    fields: [
      {
        key: 'connections',
        label: 'Connections',
        kind: 'card-list',
        // relationship is an enum and mutual a boolean — cards only do free
        // text, so they're set via the Markdown surface. org_name is the
        // required field and all a guided connection needs.
        hint: 'Other organisations connected to this idea.',
        cardShape: [{ key: 'org_name', label: 'Organisation', kind: 'text' }],
      },
      {
        key: 'collaborators',
        label: 'Collaborators',
        kind: 'card-list',
        cardShape: [
          { key: 'org_name', label: 'Organisation', kind: 'text' },
          { key: 'role', label: 'Role', kind: 'text' },
        ],
      },
      { key: 'linked_strategy_id', label: 'Linked strategy', kind: 'text', hint: 'Slug of a strategy on the same org.' },
    ],
  },
];
