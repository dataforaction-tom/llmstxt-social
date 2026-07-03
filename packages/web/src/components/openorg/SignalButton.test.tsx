import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SignalButton from './SignalButton';

// Mock the API module so the component never hits the network.
vi.mock('../../api/openorg', () => ({
  signalIdea: vi.fn(),
}));

import { signalIdea } from '../../api/openorg';

describe('SignalButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the "Express interest" button', () => {
    render(<SignalButton orgId="GB-CHC-1" slug="kitchen-network" />);
    expect(screen.getByRole('button', { name: /express interest/i })).toBeInTheDocument();
  });

  it('clicking the button opens the form', () => {
    render(<SignalButton orgId="GB-CHC-1" slug="kitchen-network" />);
    fireEvent.click(screen.getByRole('button', { name: /express interest/i }));
    // Form fields should appear
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/message/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send signal/i })).toBeInTheDocument();
  });

  it('submit calls the API and shows a success message', async () => {
    (signalIdea as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 'abc',
      org_id: 'GB-CHC-1',
      signal_type: 'interest',
      funder_name: 'Funder',
      funder_email: null,
      message: null,
      created_at: '2026-06-26T00:00:00',
    });

    render(<SignalButton orgId="GB-CHC-1" slug="kitchen-network" />);
    fireEvent.click(screen.getByRole('button', { name: /express interest/i }));
    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'Funder' } });
    fireEvent.click(screen.getByRole('button', { name: /send signal/i }));

    await waitFor(() => {
      expect(signalIdea).toHaveBeenCalledWith('GB-CHC-1', 'kitchen-network', {
        funder_name: 'Funder',
        funder_email: '',
        message: '',
      });
    });
    await waitFor(() => {
      expect(screen.getByText(/thank you/i)).toBeInTheDocument();
    });
  });

  it('shows an inline error message when the API fails', async () => {
    (signalIdea as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('boom'));

    render(<SignalButton orgId="GB-CHC-1" slug="kitchen-network" />);
    fireEvent.click(screen.getByRole('button', { name: /express interest/i }));
    fireEvent.click(screen.getByRole('button', { name: /send signal/i }));

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    });
  });
});