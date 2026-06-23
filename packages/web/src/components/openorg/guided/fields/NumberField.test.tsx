import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import NumberField from './NumberField';

describe('NumberField', () => {
  it('renders the current numeric value', () => {
    render(<NumberField label="Board size" value={7} onChange={vi.fn()} />);
    expect(screen.getByLabelText(/board size/i)).toHaveValue(7);
  });

  it('emits a number, not a string', () => {
    const onChange = vi.fn();
    render(<NumberField label="Lower" value={''} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText(/lower/i), { target: { value: '5000' } });
    expect(onChange).toHaveBeenCalledWith(5000);
  });

  it('emits undefined when cleared', () => {
    const onChange = vi.fn();
    render(<NumberField label="Lower" value={5000} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText(/lower/i), { target: { value: '' } });
    expect(onChange).toHaveBeenCalledWith(undefined);
  });
});
