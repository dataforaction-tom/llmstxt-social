import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import PublishStrip from './PublishStrip';

describe('PublishStrip (unpublished)', () => {
  it('shows the Publish trigger and a confirm strip on click', () => {
    render(
      <PublishStrip
        published={false}
        busy={false}
        onPublish={vi.fn()}
        onUnpublish={vi.fn()}
        liveUrl="https://openorg.good-ship.co.uk/GB-CHC-1"
      />,
    );
    expect(screen.getByRole('button', { name: /^publish$/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));
    expect(screen.getByText(/publish this profile/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /not yet/i })).toBeInTheDocument();
  });

  it('calls onPublish when the confirm button is clicked', () => {
    const onPublish = vi.fn();
    render(
      <PublishStrip
        published={false}
        busy={false}
        onPublish={onPublish}
        onUnpublish={vi.fn()}
        liveUrl="https://openorg.good-ship.co.uk/GB-CHC-1"
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));
    fireEvent.click(screen.getAllByRole('button', { name: /^publish$/i }).at(-1)!);
    expect(onPublish).toHaveBeenCalled();
  });
});

describe('PublishStrip (celebration)', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('shows the celebration row when justPublishedAt is recent', () => {
    render(
      <PublishStrip
        published
        busy={false}
        onPublish={vi.fn()}
        onUnpublish={vi.fn()}
        liveUrl="https://openorg.good-ship.co.uk/GB-CHC-1"
        justPublishedAt={new Date()}
      />,
    );
    expect(screen.getByText(/live at/i)).toBeInTheDocument();
    expect(screen.getByText(/share this profile/i)).toBeInTheDocument();
  });

  it('hides the celebration after 8s', () => {
    render(
      <PublishStrip
        published
        busy={false}
        onPublish={vi.fn()}
        onUnpublish={vi.fn()}
        liveUrl="https://openorg.good-ship.co.uk/GB-CHC-1"
        justPublishedAt={new Date()}
      />,
    );
    act(() => {
      vi.advanceTimersByTime(8_100);
    });
    expect(screen.queryByText(/share this profile/i)).toBeNull();
  });
});
