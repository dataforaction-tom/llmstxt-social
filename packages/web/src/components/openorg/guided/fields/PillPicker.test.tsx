import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PillPicker from './PillPicker';

const VOCAB = [
  { key: 'older_people', label: 'Older people' },
  { key: 'children', label: 'Children & families' },
  { key: 'homelessness', label: 'Homelessness' },
];

describe('PillPicker', () => {
  it('renders one pill per option', () => {
    render(<PillPicker label="Themes" options={VOCAB} value={[]} onChange={vi.fn()} />);
    expect(screen.getByRole('button', { name: /older people/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /homelessness/i })).toBeInTheDocument();
  });

  it('toggles a selection on click (multi-select)', () => {
    const onChange = vi.fn();
    render(<PillPicker label="Themes" options={VOCAB} value={[]} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /older people/i }));
    expect(onChange).toHaveBeenCalledWith(['older_people']);
  });

  it('deselects when clicking an already-selected pill', () => {
    const onChange = vi.fn();
    render(
      <PillPicker
        label="Themes"
        options={VOCAB}
        value={['older_people']}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /older people/i }));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('single-select replaces the prior value', () => {
    const onChange = vi.fn();
    render(
      <PillPicker
        label="Status"
        options={VOCAB}
        value={['older_people']}
        onChange={onChange}
        selectionCap={1}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /homelessness/i }));
    expect(onChange).toHaveBeenCalledWith(['homelessness']);
  });

  it('shows the cap nudge when a multi-select cap is exceeded and does not emit', () => {
    const onChange = vi.fn();
    const SIX = VOCAB.concat(
      ['a', 'b', 'c', 'd', 'e'].map((k) => ({ key: k, label: k })),
    );
    render(
      <PillPicker
        label="Themes"
        options={SIX}
        value={['older_people', 'children', 'homelessness', 'a', 'b', 'c']}
        onChange={onChange}
        selectionCap={6}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /^d$/i }));
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText(/six is plenty/i)).toBeInTheDocument();
  });
});
