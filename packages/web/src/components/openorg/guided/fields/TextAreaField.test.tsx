import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TextAreaField from './TextAreaField';

describe('TextAreaField', () => {
  it('lets the user type spaces even when the parent trims the round-trip', async () => {
    // Mimics the guided-editor bridge: each onChange re-parses markdown and
    // echoes back a value with trailing whitespace stripped. A naive controlled
    // input loses the space the instant it becomes trailing, so spaces can
    // never be typed. The field must hold its own in-progress buffer.
    function Harness() {
      const [stored, setStored] = useState('');
      return (
        <TextAreaField
          label="Summary"
          value={stored}
          onChange={(next) => setStored(next.replace(/\s+$/, ''))}
        />
      );
    }
    const user = userEvent.setup();
    render(<Harness />);
    const box = screen.getByLabelText(/summary/i);
    await user.type(box, 'a b c');
    expect(box).toHaveValue('a b c');
  });

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
