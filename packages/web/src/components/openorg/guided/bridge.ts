/**
 * Per-section markdown splicer.
 *
 * The Guided editor holds parsed section state and writes back to the
 * markdown source one section at a time. The invariants this module
 * upholds — covered by ``bridge.test.ts``:
 *
 *   1. Any byte of the source markdown OUTSIDE a touched section is
 *      byte-identical before and after the splice.
 *   2. Frontmatter delimiters (``---`` open and close) are preserved.
 *   3. Body sections are split on level-2 headings (``## Heading``);
 *      untouched body sections are byte-identical.
 *
 * The bridge does not perform schema validation — that stays on the
 * backend, where the existing converter validates on save. The bridge's
 * job is purely structural splicing.
 */

import yaml from 'js-yaml';

const FRONTMATTER_OPEN = /^---\r?\n/;
// A top-level YAML key starts at column 0 with a letter or underscore.
const TOP_LEVEL_KEY_RE = /^([a-zA-Z_][a-zA-Z0-9_-]*):/;

interface FrontmatterSplit {
  prefix: string; // ``---\n``
  body: string; // YAML body between the delimiters
  suffix: string; // ``---\n`` + any trailing markdown body
}

function splitFrontmatter(source: string): FrontmatterSplit {
  const openMatch = source.match(FRONTMATTER_OPEN);
  if (!openMatch) {
    throw new Error('no frontmatter found in source');
  }
  const afterOpen = openMatch[0].length;
  // Find the closing ``---`` on its own line.
  const closeIdx = source.indexOf('\n---', afterOpen);
  if (closeIdx === -1) {
    throw new Error('frontmatter has no closing delimiter');
  }
  return {
    prefix: source.slice(0, afterOpen),
    body: source.slice(afterOpen, closeIdx + 1), // include trailing newline
    suffix: source.slice(closeIdx + 1), // starts with ``---``
  };
}

interface KeyBlock {
  key: string;
  startLine: number; // index into ``lines``
  endLine: number; // exclusive
}

function findKeyBlocks(yamlBody: string): KeyBlock[] {
  const lines = yamlBody.split('\n');
  const blocks: KeyBlock[] = [];
  let current: KeyBlock | null = null;

  lines.forEach((line, i) => {
    const match = line.match(TOP_LEVEL_KEY_RE);
    if (match) {
      if (current) {
        current.endLine = i;
        blocks.push(current);
      }
      current = { key: match[1], startLine: i, endLine: lines.length };
    }
  });
  if (current) {
    blocks.push(current);
  }
  return blocks;
}

function renderKeyAsYaml(key: string, value: unknown): string {
  // Render { [key]: value } so js-yaml gives us the ``key: ...`` block we want.
  const dumped = yaml.dump({ [key]: value }, {
    indent: 2,
    lineWidth: -1,
    noRefs: true,
    sortKeys: false,
  });
  // Ensure trailing newline.
  return dumped.endsWith('\n') ? dumped : dumped + '\n';
}

export function spliceFrontmatterKey(
  source: string,
  key: string,
  value: unknown,
): string {
  const fm = splitFrontmatter(source);
  const lines = fm.body.split('\n');
  const blocks = findKeyBlocks(fm.body);
  const target = blocks.find((b) => b.key === key);

  const rendered = renderKeyAsYaml(key, value);

  let newBody: string;
  if (target) {
    const before = lines.slice(0, target.startLine).join('\n');
    const after = lines.slice(target.endLine).join('\n');
    // Reassemble: before + '\n' (if non-empty) + rendered + after.
    const beforeChunk = before === '' ? '' : before + '\n';
    const afterChunk = after === '' ? '' : after;
    newBody = beforeChunk + rendered + afterChunk;
  } else {
    // Append before the trailing newline that precedes the closing delim.
    const trimmed = fm.body.replace(/\n+$/, '\n');
    newBody = trimmed + rendered;
  }

  return fm.prefix + newBody + fm.suffix;
}
