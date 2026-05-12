/**
 * Smoke test for the public Generate Profile page.
 *
 * Validates the form's gate logic (charity number + email shape) and that a
 * successful submit transitions to the confirmation state.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import OpenOrgGeneratePage from './Generate';

const generateProfile = vi.fn<[string, string], Promise<unknown>>();

vi.mock('../../api/openorg', async () => {
  const actual = await vi.importActual<typeof import('../../api/openorg')>(
    '../../api/openorg',
  );
  return {
    ...actual,
    generateProfile: (n: string, e: string) => generateProfile(n, e),
  };
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/openorg/generate']}>
      <Routes>
        <Route path="/openorg/generate" element={<OpenOrgGeneratePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('OpenOrgGeneratePage', () => {
  beforeEach(() => {
    generateProfile.mockReset();
  });

  it('rejects an invalid charity number client-side', async () => {
    renderPage();
    fireEvent.change(screen.getByLabelText(/charity number/i), {
      target: { value: '123' },
    });
    fireEvent.change(screen.getByLabelText(/your email/i), {
      target: { value: 'tom@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate profile/i }));

    await waitFor(() => {
      // The error message uses "must be 6 to 8 digits"; the static hint uses
      // "6 to 8 digits." (with a period). Match the unique error phrase.
      expect(screen.getByText(/must be 6 to 8 digits/i)).toBeInTheDocument();
    });
    expect(generateProfile).not.toHaveBeenCalled();
  });

  it('rejects an invalid email client-side', async () => {
    renderPage();
    fireEvent.change(screen.getByLabelText(/charity number/i), {
      target: { value: '1234567' },
    });
    fireEvent.change(screen.getByLabelText(/your email/i), {
      target: { value: 'not-an-email' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate profile/i }));

    await waitFor(() => {
      expect(screen.getByText(/valid email/i)).toBeInTheDocument();
    });
    expect(generateProfile).not.toHaveBeenCalled();
  });

  it('shows a check-your-inbox screen after a successful submit', async () => {
    generateProfile.mockResolvedValue({
      org_id: 'GB-CHC-1234567',
      profile_id: 'abc',
      generation_status: 'pending',
      task_id: 't1',
    });
    renderPage();
    fireEvent.change(screen.getByLabelText(/charity number/i), {
      target: { value: '1234567' },
    });
    fireEvent.change(screen.getByLabelText(/your email/i), {
      target: { value: 'tom@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate profile/i }));

    await waitFor(() => {
      expect(screen.getByText(/check your inbox/i)).toBeInTheDocument();
    });
    expect(generateProfile).toHaveBeenCalledWith('1234567', 'tom@example.com');
    expect(screen.getByText(/tom@example.com/)).toBeInTheDocument();
    expect(screen.getByText(/GB-CHC-1234567/)).toBeInTheDocument();
  });
});
