/**
 * Flat keyed dictionary of user-facing strings.
 *
 * Components import strings via ``t('key')``. New copy lands here first,
 * then components import the key — never a literal. This file is the
 * single place to edit user-facing language across the Open Org flows.
 */

export const MICROCOPY = {
  'publish.confirm.prompt': 'Publish this {noun} to the federated network? Anyone will be able to see it at {url}.',
  'publish.confirm.publish': 'Publish',
  'publish.confirm.notyet': 'Not yet',
  'publish.celebrate.share': 'Share this profile ↗',
  'publish.celebrate.copied': 'Copied',
  'save.justnow': 'just now',
  'save.unsaved': 'Unsaved · ⌘S to save',
  'save.saving': 'Saving…',
  'save.error': "Couldn't save —",
  'save.retry': 'Retry',
  'generate.trust': "We won't publish anything without your say-so.",
  'generate.timeout': "Still working in the background — we'll email you when it's ready, feel free to close this tab.",
  'welcome.body': "Here's your draft — pulled from public data. Have a look, edit anything that's off, and click Publish when you're ready. We've highlighted the first section we'd refine.",
  'welcome.dismiss': 'Dismiss',
  'sidebar.missing.heading': 'Missing',
  'sidebar.starthere': 'Start here',
} as const;

export type MicrocopyKey = keyof typeof MICROCOPY;

export function t(key: MicrocopyKey, vars?: Record<string, string>): string {
  const tpl = MICROCOPY[key];
  if (!tpl) {
    throw new Error(`unknown microcopy key: ${key}`);
  }
  if (!vars) return tpl;
  return tpl.replace(/\{([a-zA-Z_]+)\}/g, (_, name) => vars[name] ?? `{${name}}`);
}
