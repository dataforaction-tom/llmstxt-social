/**
 * Payments-flag behaviour on the llmstxt.social Generate page: with payments
 * off the tier selector disappears and the submit button is plain "Generate";
 * with payments on the current free/paid radiogroup renders.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

import GeneratePage from './Generate';
import { paymentsEnabled } from '../config/payments';

vi.mock('../config/payments', () => ({ paymentsEnabled: vi.fn(() => false) }));
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ user: null }) }));
// PaymentFlow calls loadStripe at module scope — keep it out of the test env.
vi.mock('../components/PaymentFlow', () => ({ default: () => null }));
vi.mock('../components/SEOHead', () => ({ default: () => null }));
vi.mock('../components/SchemaScript', () => ({
  default: () => null,
  generateHowToSchema: () => ({}),
}));
vi.mock('../api/client', () => ({
  default: {
    getTemplateOptions: vi.fn().mockResolvedValue({
      template: 'charity',
      sectors: [],
      goals: [],
      default_sector: 'general',
      default_goal: 'more_donors',
    }),
    generateFree: vi.fn(),
    getJob: vi.fn(),
  },
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <GeneratePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('GeneratePage payments flag', () => {
  beforeEach(() => {
    vi.mocked(paymentsEnabled).mockReturnValue(false);
  });

  it('hides the tier selector and shows a plain Generate button when payments are off', () => {
    renderPage();
    expect(
      screen.queryByRole('radiogroup', { name: /pricing tier/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /^generate$/i }),
    ).toBeInTheDocument();
  });

  it('shows the tier selector when payments are on', () => {
    vi.mocked(paymentsEnabled).mockReturnValue(true);
    renderPage();
    expect(
      screen.getByRole('radiogroup', { name: /pricing tier/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /generate free/i }),
    ).toBeInTheDocument();
  });
});
