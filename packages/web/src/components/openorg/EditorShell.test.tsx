import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import EditorShell from './EditorShell';
import { PROFILE_SECTIONS } from './guided/sections/profile';

const SOURCE = `---
identity:
  name: Trust
---

## Mission

x
`;

describe('EditorShell', () => {
  beforeEach(() => window.localStorage.clear());

  it('renders the guided surface by default', () => {
    render(
      <EditorShell
        kind="profile"
        initialSource={SOURCE}
        sections={PROFILE_SECTIONS}
        onSave={vi.fn()}
        vocabs={{}}
      />,
    );
    // Guided surface has sidebar buttons.
    expect(screen.getByRole('button', { name: /^identity$/i })).toBeInTheDocument();
  });

  it('autosaves the guided surface after a debounce window', async () => {
    vi.useFakeTimers();
    const onSave = vi.fn(async () => undefined);
    render(
      <EditorShell
        kind="profile"
        initialSource={SOURCE}
        sections={PROFILE_SECTIONS}
        onSave={onSave}
        vocabs={{}}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Trussell' } });
    expect(onSave).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(700);
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave.mock.calls[0][0]).toContain('name: Trussell');
    vi.useRealTimers();
  });

  it('shows the save indicator', () => {
    render(
      <EditorShell
        kind="profile"
        initialSource={SOURCE}
        sections={PROFILE_SECTIONS}
        onSave={vi.fn()}
        vocabs={{}}
      />,
    );
    expect(screen.getByText(/saved/i)).toBeInTheDocument();
  });

  it('switches to markdown surface and persists', () => {
    const { unmount } = render(
      <EditorShell
        kind="profile"
        initialSource={SOURCE}
        sections={PROFILE_SECTIONS}
        onSave={vi.fn()}
        vocabs={{}}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /^markdown$/i }));
    expect(screen.getByText(/^source$/i)).toBeInTheDocument();
    unmount();

    render(
      <EditorShell
        kind="profile"
        initialSource={SOURCE}
        sections={PROFILE_SECTIONS}
        onSave={vi.fn()}
        vocabs={{}}
      />,
    );
    expect(screen.getByText(/^source$/i)).toBeInTheDocument();
  });
});
