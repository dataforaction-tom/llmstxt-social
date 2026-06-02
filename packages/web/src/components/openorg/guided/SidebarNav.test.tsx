import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SidebarNav from './SidebarNav';

const SECTIONS = [
  { id: 'a', name: 'Alpha', tick: '✓' as const, missing: [] },
  { id: 'b', name: 'Beta', tick: '●' as const, missing: ['summary'] },
  { id: 'c', name: 'Gamma', tick: '○' as const, missing: ['everything'] },
];

describe('SidebarNav', () => {
  it('renders one row per section with its tick', () => {
    render(<SidebarNav sections={SECTIONS} activeId="a" onSelect={vi.fn()} />);
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.getByText('Gamma')).toBeInTheDocument();
    expect(screen.getAllByText('✓').length).toBeGreaterThan(0);
  });

  it('shows the completion rollup', () => {
    render(<SidebarNav sections={SECTIONS} activeId="a" onSelect={vi.fn()} />);
    // 1 of 3 complete = 33%.
    expect(screen.getByText(/33% done/i)).toBeInTheDocument();
  });

  it('calls onSelect with the clicked id', () => {
    const onSelect = vi.fn();
    render(<SidebarNav sections={SECTIONS} activeId="a" onSelect={onSelect} />);
    // The section row button's accessible name is the tick + section name.
    // The missing panel's button is "· Beta — summary"; disambiguate.
    fireEvent.click(screen.getByRole('button', { name: /^beta$/i }));
    expect(onSelect).toHaveBeenCalledWith('b');
  });

  it('lists missing items, click-jump fires onSelect', () => {
    const onSelect = vi.fn();
    render(<SidebarNav sections={SECTIONS} activeId="a" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole('button', { name: /beta — summary/i }));
    expect(onSelect).toHaveBeenCalledWith('b');
  });
});
