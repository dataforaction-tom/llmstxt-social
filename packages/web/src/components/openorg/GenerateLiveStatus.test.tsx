import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import GenerateLiveStatus from './GenerateLiveStatus';

describe('GenerateLiveStatus', () => {
  it('shows the current stage message', () => {
    render(
      <GenerateLiveStatus
        status={{
          org_id: 'GB-CHC-1',
          status: 'generating',
          stage: 'drafting',
          message: 'Drafting your profile…',
          payload: null,
          elapsed_ms: 12_000,
        }}
        onTimeout={vi.fn()}
      />,
    );
    expect(screen.getByText('Drafting your profile…')).toBeInTheDocument();
  });

  it('shows the done summary when status is ready', () => {
    render(
      <GenerateLiveStatus
        status={{
          org_id: 'GB-CHC-1',
          status: 'ready',
          stage: 'done',
          message: 'Draft ready.',
          payload: { themes_count: 4, programmes_count: 14, has_summary: true },
          elapsed_ms: 47_000,
        }}
        onTimeout={vi.fn()}
      />,
    );
    expect(screen.getByText(/draft ready/i)).toBeInTheDocument();
    expect(screen.getByText(/took 47 seconds/i)).toBeInTheDocument();
    expect(screen.getByText(/14 programmes/i)).toBeInTheDocument();
  });

  it('calls onTimeout when elapsed > 90s and status still generating', () => {
    const onTimeout = vi.fn();
    render(
      <GenerateLiveStatus
        status={{
          org_id: 'GB-CHC-1',
          status: 'generating',
          stage: 'drafting',
          message: 'Drafting…',
          payload: null,
          elapsed_ms: 91_000,
        }}
        onTimeout={onTimeout}
      />,
    );
    expect(onTimeout).toHaveBeenCalled();
    expect(screen.getByText(/still working in the background/i)).toBeInTheDocument();
  });
});
