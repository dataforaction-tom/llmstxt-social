import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import WelcomeStrip from './WelcomeStrip';

describe('WelcomeStrip', () => {
  beforeEach(() => window.localStorage.clear());

  it('renders when the orgId has a pending welcome flag', () => {
    window.localStorage.setItem('openorg.welcomeStrip.GB-CHC-1', 'pending');
    render(<WelcomeStrip orgId="GB-CHC-1" />);
    expect(screen.getByText(/here's your draft/i)).toBeInTheDocument();
  });

  it('does not render when no flag is set', () => {
    render(<WelcomeStrip orgId="GB-CHC-1" />);
    expect(screen.queryByText(/here's your draft/i)).toBeNull();
  });

  it('dismissal persists in localStorage', () => {
    window.localStorage.setItem('openorg.welcomeStrip.GB-CHC-1', 'pending');
    render(<WelcomeStrip orgId="GB-CHC-1" />);
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(window.localStorage.getItem('openorg.welcomeStrip.GB-CHC-1')).toBe('dismissed');
  });
});
