import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import CardList from './CardList';

const SHAPE = [
  { key: 'name', label: 'Name', kind: 'text' as const },
  { key: 'description', label: 'Description', kind: 'textarea' as const },
];

describe('CardList', () => {
  it('renders one card per item with a title preview', () => {
    render(
      <CardList
        label="Programmes"
        value={[
          { name: 'Foodbank', description: 'A network.' },
          { name: 'Helpline', description: 'Phone support.' },
        ]}
        shape={SHAPE}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText('Foodbank')).toBeInTheDocument();
    expect(screen.getByText('Helpline')).toBeInTheDocument();
  });

  it('adds a blank item on Add', () => {
    const onChange = vi.fn();
    render(<CardList label="Programmes" value={[]} shape={SHAPE} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /add/i }));
    expect(onChange).toHaveBeenCalledWith([{ name: '', description: '' }]);
  });

  it('emits the updated item when a field changes', () => {
    const onChange = vi.fn();
    render(
      <CardList
        label="Programmes"
        value={[{ name: 'Foodbank', description: '' }]}
        shape={SHAPE}
        onChange={onChange}
      />,
    );
    // Cards start collapsed; click to expand.
    fireEvent.click(screen.getByText('Foodbank'));
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Foodbank network' } });
    expect(onChange).toHaveBeenLastCalledWith([
      { name: 'Foodbank network', description: '' },
    ]);
  });

  it('removes an item via the Remove button', () => {
    const onChange = vi.fn();
    render(
      <CardList
        label="Programmes"
        value={[{ name: 'A' }, { name: 'B' }]}
        shape={[{ key: 'name', label: 'Name', kind: 'text' }]}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByText('A'));
    fireEvent.click(screen.getAllByRole('button', { name: /remove/i })[0]);
    expect(onChange).toHaveBeenCalledWith([{ name: 'B' }]);
  });
});
