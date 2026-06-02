import type { PillOption } from './fields/PillPicker';

export const STATIC_VOCABS: Record<string, PillOption[]> = {
  strategy_status: [
    { key: 'draft', label: 'Draft' },
    { key: 'live', label: 'Live' },
    { key: 'completed', label: 'Completed' },
    { key: 'paused', label: 'Paused' },
  ],
  idea_status: [
    { key: 'seed', label: 'Seed' },
    { key: 'developing', label: 'Developing' },
    { key: 'piloting', label: 'Piloting' },
    { key: 'scaling', label: 'Scaling' },
    { key: 'paused', label: 'Paused' },
  ],
  access_level: [
    { key: 'public', label: 'Public' },
    { key: 'authenticated', label: 'Authenticated' },
    { key: 'private', label: 'Private' },
  ],
  horizon: [
    { key: 'short', label: 'Short (under 1 year)' },
    { key: 'medium', label: 'Medium (1-3 years)' },
    { key: 'long', label: 'Long (3+ years)' },
  ],
  beneficiaries: [
    { key: 'older_people', label: 'Older people' },
    { key: 'children', label: 'Children & families' },
    { key: 'young_people', label: 'Young people' },
    { key: 'disabled_people', label: 'Disabled people' },
    { key: 'homelessness', label: 'People experiencing homelessness' },
    { key: 'refugees', label: 'Refugees & people seeking asylum' },
    { key: 'low_income', label: 'People on low incomes' },
    { key: 'lgbtq', label: 'LGBTQ+ people' },
  ],
  connections: [
    { key: 'seeking_partners', label: 'Seeking partners' },
    { key: 'seeking_funders', label: 'Seeking funders' },
    { key: 'sharing_evidence', label: 'Sharing evidence' },
    { key: 'open_to_replication', label: 'Open to replication' },
  ],
};
