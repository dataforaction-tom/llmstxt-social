/**
 * Payments-flag behaviour on the Pricing page: with payments off the £9
 * one-time tier disappears and Free advertises the full pipeline; with
 * payments on the current three-tier layout renders.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import PricingPage from './Pricing';
import { paymentsEnabled } from '../config/payments';

vi.mock('../config/payments', () => ({ paymentsEnabled: vi.fn(() => false) }));
vi.mock('../components/SEOHead', () => ({ default: () => null }));
vi.mock('../components/SchemaScript', () => ({
  default: () => null,
  generateFAQSchema: () => ({}),
  generateProductSchema: () => ({}),
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <PricingPage />
    </MemoryRouter>,
  );
}

describe('PricingPage payments flag', () => {
  beforeEach(() => {
    vi.mocked(paymentsEnabled).mockReturnValue(false);
  });

  // Note: the feature <li> elements are listitems too, so query the tier
  // cards by their aria-labels ("<name> tier - <price>...") rather than
  // counting listitems.

  it('shows Free (full pipeline) and Subscription only when payments are off', () => {
    renderPage();
    expect(
      screen.getByRole('listitem', { name: /^free tier/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('listitem', { name: /^paid tier/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('listitem', { name: /^subscription tier/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/one-time/i)).not.toBeInTheDocument();
    // Free tier now advertises the formerly-paid features.
    expect(screen.getByText('Full quality assessment')).toBeInTheDocument();
    expect(screen.getByText('Charity Commission enrichment')).toBeInTheDocument();
  });

  it('shows all three tiers when payments are on', () => {
    vi.mocked(paymentsEnabled).mockReturnValue(true);
    renderPage();
    expect(
      screen.getByRole('listitem', { name: /^free tier/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('listitem', { name: /^paid tier/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('listitem', { name: /^subscription tier/i }),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/one-time/i).length).toBeGreaterThan(0);
  });
});
