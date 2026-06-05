import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AuthVerifyPage from './AuthVerify';

const mockVerifyToken = vi.fn();

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    verifyToken: mockVerifyToken,
    isAuthenticated: false,
  }),
}));

function renderWithToken(token: string) {
  return render(
    <MemoryRouter initialEntries={[`/auth/verify?token=${token}`]}>
      <Routes>
        <Route path="/auth/verify" element={<AuthVerifyPage />} />
        <Route
          path="/openorg/edit/:orgId/profile"
          element={<div data-testid="editor">editor</div>}
        />
        <Route path="/dashboard" element={<div data-testid="dashboard">dashboard</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AuthVerify post-claim redirect', () => {
  beforeEach(() => {
    mockVerifyToken.mockReset();
    window.localStorage.clear();
  });

  it('redirects to the editor and sets the welcome flag when claimOrgId is present', async () => {
    mockVerifyToken.mockResolvedValueOnce({
      success: true,
      message: 'ok',
      claimOrgId: 'GB-CHC-1234567',
    });
    renderWithToken('abc');
    await waitFor(() => expect(screen.getByTestId('editor')).toBeInTheDocument());
    expect(window.localStorage.getItem('openorg.welcomeStrip.GB-CHC-1234567')).toBe('pending');
  });

  it('redirects to the dashboard when there is no claimOrgId', async () => {
    mockVerifyToken.mockResolvedValueOnce({ success: true, message: 'ok' });
    renderWithToken('abc');
    await waitFor(() => expect(screen.getByTestId('dashboard')).toBeInTheDocument());
  });
});
