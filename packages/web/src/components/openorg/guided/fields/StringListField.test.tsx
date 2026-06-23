import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import StringListField from './StringListField';

describe('StringListField', () => {
  it('renders each string as its own input', () => {
    render(<StringListField label="Also known as" value={['Mind', 'NAMH']} onChange={vi.fn()} />);
    expect(screen.getByLabelText(/also known as 1/i)).toHaveValue('Mind');
    expect(screen.getByLabelText(/also known as 2/i)).toHaveValue('NAMH');
  });

  it('emits a flat string array on edit, not objects', () => {
    const onChange = vi.fn();
    render(<StringListField label="Aliases" value={['Mind']} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText(/aliases 1/i), { target: { value: 'Mind UK' } });
    expect(onChange).toHaveBeenCalledWith(['Mind UK']);
  });

  it('adds a new empty entry', () => {
    const onChange = vi.fn();
    render(<StringListField label="Aliases" value={['Mind']} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /add/i }));
    expect(onChange).toHaveBeenCalledWith(['Mind', '']);
  });
});
