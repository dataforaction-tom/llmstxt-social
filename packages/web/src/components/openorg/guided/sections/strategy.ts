import type { GuidedSection } from './profile';

export const STRATEGY_SECTIONS: GuidedSection[] = [
  {
    id: 'overview',
    name: 'Overview',
    description: 'A name, a one-line summary, and visibility.',
    yamlKeys: ['id', 'status', 'access_level', 'summary'],
    bodyHeadings: ['Summary'],
    fields: [
      { key: 'id', label: 'Slug', kind: 'text', hint: 'URL-stable id, lowercase-and-dashes.' },
      {
        key: 'status',
        label: 'Status',
        kind: 'pills',
        selectionCap: 1,
        vocab: 'strategy_status',
      },
      {
        key: 'access_level',
        label: 'Visibility',
        kind: 'pills',
        selectionCap: 1,
        vocab: 'access_level',
      },
      { key: 'Summary', label: 'Summary', kind: 'textarea', hint: 'One paragraph; the strategy in plain English.' },
    ],
  },
  {
    id: 'period',
    name: 'Period',
    description: 'When this strategy runs.',
    yamlKeys: ['period'],
    bodyHeadings: [],
    fields: [
      { key: 'period.start', label: 'Start', kind: 'text', placeholder: '2026-01' },
      { key: 'period.end', label: 'End', kind: 'text', placeholder: '2028-12' },
      {
        key: 'period.horizon',
        label: 'Horizon',
        kind: 'pills',
        selectionCap: 1,
        vocab: 'horizon',
      },
    ],
  },
  {
    id: 'themes',
    name: 'Themes',
    description: 'What this strategy is about.',
    yamlKeys: ['themes'],
    bodyHeadings: [],
    fields: [
      {
        key: 'themes',
        label: 'Themes',
        kind: 'pills',
        selectionCap: 6,
        vocab: 'themes',
      },
    ],
  },
  {
    id: 'priorities',
    name: 'Priorities',
    description: 'The concrete things you intend to do.',
    emptyPrompt: 'What two to five priorities define this strategy? Add one to start.',
    yamlKeys: ['priorities'],
    bodyHeadings: [],
    fields: [
      {
        key: 'priorities',
        label: 'Priorities',
        kind: 'card-list',
        cardShape: [
          { key: 'title', label: 'Title', kind: 'text' },
          { key: 'description', label: 'Description', kind: 'textarea' },
        ],
      },
    ],
  },
  {
    id: 'not_doing',
    name: 'Not doing',
    description: 'What you are deliberately not doing.',
    yamlKeys: [],
    bodyHeadings: ['Not doing'],
    fields: [
      { key: 'Not doing', label: 'Not doing', kind: 'textarea', hint: 'Items follow the - **Title** rationale shape.' },
    ],
  },
  {
    id: 'tensions',
    name: 'Tensions',
    description: 'Trade-offs you live with.',
    yamlKeys: [],
    bodyHeadings: ['Tensions'],
    fields: [
      { key: 'Tensions', label: 'Tensions', kind: 'textarea', hint: 'Items follow the - **Title** narrative shape.' },
    ],
  },
  {
    id: 'learning',
    name: 'Learning',
    description: 'What has changed your thinking.',
    yamlKeys: [],
    bodyHeadings: ['Learning'],
    fields: [
      { key: 'Learning', label: 'Learning', kind: 'textarea', hint: 'Bulleted lessons. *Source: …* tags optional.' },
    ],
  },
  {
    id: 'relationships',
    name: 'Relationships',
    description: 'Who you work with and where you sit.',
    yamlKeys: ['relationships'],
    bodyHeadings: [],
    fields: [
      {
        key: 'relationships.partnerships',
        label: 'Partnerships',
        kind: 'card-list',
        cardShape: [
          { key: 'name', label: 'Partner', kind: 'text' },
          { key: 'description', label: 'Description', kind: 'textarea' },
        ],
      },
      { key: 'relationships.ecosystem_position', label: 'Ecosystem position', kind: 'textarea' },
      { key: 'relationships.community_mandate', label: 'Community mandate', kind: 'textarea' },
    ],
  },
  {
    id: 'resource_model',
    name: 'Resource model',
    description: 'How you fund the work.',
    yamlKeys: ['resource_model'],
    bodyHeadings: [],
    fields: [
      { key: 'resource_model.current_funding_mix', label: 'Current funding mix', kind: 'textarea' },
      { key: 'resource_model.sustainability_direction', label: 'Sustainability direction', kind: 'textarea' },
      {
        key: 'resource_model.resourcing_gaps',
        label: 'Resourcing gaps',
        kind: 'card-list',
        cardShape: [
          { key: 'title', label: 'Gap', kind: 'text' },
          { key: 'description', label: 'Description', kind: 'textarea' },
        ],
      },
    ],
  },
];
