import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import TextField from './TextField';

describe('TextField', () => {
  it('renders the label, placeholder, and current value', () => {
    render(
      <TextField label="Name" value="Riverside Trust" placeholder="The Trussell Trust" onChange={vi.fn()} />,
    );
    expect(screen.getByLabelText(/name/i)).toHaveValue('Riverside Trust');
    expect(screen.getByPlaceholderText(/trussell/i)).toBeInTheDocument();
  });

  it('renders the hint when provided', () => {
    render(<TextField label="Founded" value="" hint="Year you started." onChange={vi.fn()} />);
    expect(screen.getByText('Year you started.')).toBeInTheDocument();
  });

  it('shows the source chip and hides it on first edit', () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <TextField label="Name" value="Trussell Trust" source="cc" onChange={onChange} />,
    );
    expect(screen.getByText(/from commission filing/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'New name' } });
    expect(onChange).toHaveBeenCalledWith('New name');

    rerender(<TextField label="Name" value="New name" source="cc" onChange={onChange} userEdited />);
    expect(screen.queryByText(/from commission filing/i)).toBeNull();
  });
});
