import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AuthVerifyPage from './AuthVerify';

const mockVerifyToken = vi.fn();

// Mutable so a test can model auth state flipping to true *during*
// verification — which is what AuthContext.verifyToken does via refetch().
const authState = { isAuthenticated: false };

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    verifyToken: mockVerifyToken,
    get isAuthenticated() {
      return authState.isAuthenticated;
    },
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
    authState.isAuthenticated = false;
  });

  it('redirects to the claim editor even when auth is already established', async () => {
    // Regression: verifyToken flips isAuthenticated true (via refetch) before
    // the caller sees claimOrgId. If the redirect guard short-circuits on
    // isAuthenticated, it navigates to /dashboard before redirectTo is set.
    // It must wait for verification to finish and honour the claim org.
    authState.isAuthenticated = true;
    mockVerifyToken.mockResolvedValueOnce({
      success: true,
      message: 'ok',
      claimOrgId: 'GB-CHC-7654321',
    });
    renderWithToken('abc');
    await waitFor(() => expect(screen.getByTestId('editor')).toBeInTheDocument());
    expect(screen.queryByTestId('dashboard')).not.toBeInTheDocument();
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
