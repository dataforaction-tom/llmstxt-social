import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import GuidedEditor from './GuidedEditor';
import { PROFILE_SECTIONS } from './sections/profile';

const SOURCE = `---
schema_version: open-org/v0.1
identity:
  name: Trust
---

## Mission

We do good.
`;

describe('GuidedEditor', () => {
  it('renders sidebar entries for each section', () => {
    render(
      <GuidedEditor
        source={SOURCE}
        sections={PROFILE_SECTIONS}
        onChange={vi.fn()}
        vocabs={{}}
      />,
    );
    expect(screen.getByRole('button', { name: /^identity$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^mission$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^values$/i })).toBeInTheDocument();
  });

  it('shows the active section in the middle column', () => {
    render(
      <GuidedEditor
        source={SOURCE}
        sections={PROFILE_SECTIONS}
        onChange={vi.fn()}
        vocabs={{}}
      />,
    );
    expect(screen.getByLabelText(/^name$/i)).toHaveValue('Trust');
  });

  it('writes back through the bridge on field edit', () => {
    const onChange = vi.fn();
    render(
      <GuidedEditor
        source={SOURCE}
        sections={PROFILE_SECTIONS}
        onChange={onChange}
        vocabs={{}}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Trussell' } });
    const updatedSource = onChange.mock.calls.at(-1)![0] as string;
    expect(updatedSource).toContain('name: Trussell');
    // Body untouched.
    expect(updatedSource).toContain('## Mission\n\nWe do good.');
  });
});
