/**
 * Smoke test for the Open Org markdown editor.
 *
 * Establishes the Vitest + RTL pattern for this repo. Doesn't exhaustively
 * test CodeMirror's text-entry behaviour (CodeMirror's own tests cover that)
 * — focuses on the integration we own: validation-error rendering, the
 * frontmatter/body split that drives the preview, and the save button.
 */

import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import MarkdownEditor from './MarkdownEditor';

const PROFILE_MD = `---
schema_version: open-org/v0.1
identity:
  name: Riverside Community Trust
mission:
  themes:
    - older_people
---

## Mission

We support older people in Norfolk.
`;

describe('MarkdownEditor', () => {
  it('renders without crashing and shows the save button', () => {
    render(
      <MarkdownEditor
        initialMarkdown={PROFILE_MD}
        onSave={vi.fn()}
        saveLabel="Save profile"
      />
    );
    expect(screen.getByRole('button', { name: /save profile/i })).toBeInTheDocument();
  });

  it('renders the markdown body in the preview pane', () => {
    const { container } = render(
      <MarkdownEditor initialMarkdown={PROFILE_MD} onSave={vi.fn()} />
    );
    // The preview pane wraps content in a <article class="prose">. Restrict
    // the lookup to that to avoid matching the editor's CodeMirror layer too.
    const preview = container.querySelector('article.prose');
    expect(preview).not.toBeNull();
    expect(preview!.textContent).toMatch(/We support older people in Norfolk/);
  });

  it('starts in "all changes saved" state with the save button disabled', () => {
    render(
      <MarkdownEditor initialMarkdown={PROFILE_MD} onSave={vi.fn()} />
    );
    expect(screen.getByText(/all changes saved/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled();
  });

  it('surfaces validation errors when provided', () => {
    render(
      <MarkdownEditor
        initialMarkdown={PROFILE_MD}
        onSave={vi.fn()}
        validationErrors={[
          { path: 'mission.themes', message: 'must contain at least 1 item' },
        ]}
      />
    );
    expect(screen.getByText(/Validation errors:/)).toBeInTheDocument();
    expect(screen.getByText(/must contain at least 1 item/)).toBeInTheDocument();
  });

  it('hides the frontmatter behind a details disclosure', () => {
    render(
      <MarkdownEditor initialMarkdown={PROFILE_MD} onSave={vi.fn()} />
    );
    // The frontmatter <details> renders the summary; the inner contents are
    // present in the DOM (collapsed) but the user clicks to expand.
    expect(screen.getByText(/Frontmatter/)).toBeInTheDocument();
  });
});
