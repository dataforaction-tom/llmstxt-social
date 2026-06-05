import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import SaveIndicator from './SaveIndicator';

describe('SaveIndicator', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders Saving while in flight', () => {
    render(<SaveIndicator state="saving" />);
    expect(screen.getByText(/saving/i)).toBeInTheDocument();
  });

  it('renders Saved · just now and ages over time', () => {
    render(<SaveIndicator state="saved" savedAt={new Date()} />);
    expect(screen.getByText(/just now/i)).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(15_000);
    });
    expect(screen.getByText(/15s ago|14s ago|16s ago/i)).toBeInTheDocument();
  });

  it('renders the error state with a Retry button that calls onRetry', () => {
    const onRetry = vi.fn();
    render(<SaveIndicator state="error" onRetry={onRetry} />);
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalled();
  });

  it('renders Unsaved · ⌘S to save when given the unsaved state', () => {
    render(<SaveIndicator state="unsaved" />);
    expect(screen.getByText(/unsaved/i)).toBeInTheDocument();
    expect(screen.getByText(/⌘s/i)).toBeInTheDocument();
  });
});
