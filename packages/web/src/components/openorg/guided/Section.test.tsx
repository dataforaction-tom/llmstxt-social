import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Section from './Section';
import { PROFILE_SECTIONS } from './sections/profile';

const identity = PROFILE_SECTIONS.find((s) => s.id === 'identity')!;
const values = PROFILE_SECTIONS.find((s) => s.id === 'values')!;

describe('Section', () => {
  it('renders the section heading and field labels', () => {
    render(
      <Section
        section={identity}
        parsed={{ yaml: { identity: { name: '' } }, body: {} }}
        onChange={vi.fn()}
        vocabs={{}}
      />,
    );
    expect(screen.getByText(/identity/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^name$/i)).toBeInTheDocument();
  });

  it('emits a parsed update on text-field change', () => {
    const onChange = vi.fn();
    render(
      <Section
        section={identity}
        parsed={{ yaml: { identity: { name: '' } }, body: {} }}
        onChange={onChange}
        vocabs={{}}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Trussell' } });
    const lastCall = onChange.mock.calls.at(-1)![0];
    expect(lastCall.yaml.identity.name).toBe('Trussell');
  });

  it('shows the emptyPrompt when every field is empty', () => {
    render(
      <Section
        section={values}
        parsed={{ yaml: {}, body: {} }}
        onChange={vi.fn()}
        vocabs={{}}
      />,
    );
    expect(screen.getByText(/three or four principles/i)).toBeInTheDocument();
  });
});
