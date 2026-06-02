import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import TextAreaField from './TextAreaField';

describe('TextAreaField', () => {
  it('renders label, value, and hint', () => {
    render(
      <TextAreaField label="Summary" value="We do good." hint="One paragraph." onChange={vi.fn()} />,
    );
    expect(screen.getByLabelText(/summary/i)).toHaveValue('We do good.');
    expect(screen.getByText('One paragraph.')).toBeInTheDocument();
  });

  it('emits change on input', () => {
    const onChange = vi.fn();
    render(<TextAreaField label="Summary" value="" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText(/summary/i), { target: { value: 'New' } });
    expect(onChange).toHaveBeenCalledWith('New');
  });

  it('hides the source chip once userEdited', () => {
    render(
      <TextAreaField label="Summary" value="x" source="website" userEdited onChange={vi.fn()} />,
    );
    expect(screen.queryByText(/from website/i)).toBeNull();
  });
});
