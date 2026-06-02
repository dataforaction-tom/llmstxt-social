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
  // Empty-frontmatter case: ``---\n---`` (close delim immediately follows open).
  if (source.slice(afterOpen, afterOpen + 3) === '---') {
    return {
      prefix: source.slice(0, afterOpen),
      body: '',
      suffix: source.slice(afterOpen),
    };
  }
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

const HEADING_RE = /^## (.+)$/;

interface BodyBlock {
  heading: string;
  startLine: number;
  endLine: number;
}

function findBodyBlocks(bodyText: string): { lines: string[]; blocks: BodyBlock[] } {
  const lines = bodyText.split('\n');
  const blocks: BodyBlock[] = [];
  let current: BodyBlock | null = null;

  lines.forEach((line, i) => {
    const match = line.match(HEADING_RE);
    if (match) {
      if (current) {
        current.endLine = i;
        blocks.push(current);
      }
      current = { heading: match[1].trim(), startLine: i, endLine: lines.length };
    }
  });
  if (current) {
    blocks.push(current);
  }
  return { lines, blocks };
}

function bodyOf(source: string): { preBody: string; body: string } {
  const fm = splitFrontmatter(source);
  // fm.suffix starts with ``---`` (close delim). Everything after the close
  // delim's line is the body.
  const closeNl = fm.suffix.indexOf('\n');
  if (closeNl === -1) {
    return { preBody: fm.prefix + fm.body + fm.suffix, body: '' };
  }
  const preBody = fm.prefix + fm.body + fm.suffix.slice(0, closeNl + 1);
  return { preBody, body: fm.suffix.slice(closeNl + 1) };
}

export function spliceBodySection(source: string, heading: string, value: string): string {
  const { preBody, body } = bodyOf(source);
  const { lines, blocks } = findBodyBlocks(body);
  const target = blocks.find((b) => b.heading === heading);

  const trimmedValue = value.trim();
  const rendered = trimmedValue ? `## ${heading}\n\n${trimmedValue}\n` : '';

  let newBody: string;
  if (target) {
    const before = lines.slice(0, target.startLine).join('\n');
    const after = lines.slice(target.endLine).join('\n');
    const beforeChunk = before === '' ? '' : before + (before.endsWith('\n') ? '' : '\n');
    if (!rendered) {
      // Removing: drop a leading blank line if present.
      const cleanedAfter = after.replace(/^\n+/, '');
      const cleanedBefore = beforeChunk.replace(/\n+$/, '\n');
      newBody = cleanedBefore + cleanedAfter;
    } else {
      // Need a blank line before the new heading if there's content above.
      const sep = beforeChunk && !beforeChunk.endsWith('\n\n') ? '\n' : '';
      const afterSep = after && !after.startsWith('\n') ? '\n' : '';
      newBody = beforeChunk + sep + rendered + afterSep + after;
    }
  } else {
    if (!rendered) {
      newBody = body;
    } else {
      const sep = body.endsWith('\n\n') ? '' : body.endsWith('\n') ? '\n' : '\n\n';
      newBody = body + sep + rendered;
    }
  }

  return preBody + newBody;
}

export interface SectionSpec {
  /** Stable id used for nav + localStorage; matches the section file name. */
  id: string;
  /** Top-level YAML keys this section owns. */
  yamlKeys: string[];
  /** Level-2 body headings this section owns. */
  bodyHeadings: string[];
}

export interface ParsedSection {
  yaml: Record<string, unknown>;
  body: Record<string, string>;
}

function parseFrontmatterYaml(source: string): Record<string, unknown> {
  const fm = splitFrontmatter(source);
  const loaded = yaml.load(fm.body) as Record<string, unknown> | null | undefined;
  return loaded && typeof loaded === 'object' ? loaded : {};
}

export function parseSection(source: string, spec: SectionSpec): ParsedSection {
  const fmDict = parseFrontmatterYaml(source);
  const out: ParsedSection = { yaml: {}, body: {} };
  for (const key of spec.yamlKeys) {
    if (key in fmDict) {
      out.yaml[key] = fmDict[key];
    }
  }
  if (spec.bodyHeadings.length > 0) {
    const { body } = bodyOf(source);
    const { lines, blocks } = findBodyBlocks(body);
    for (const heading of spec.bodyHeadings) {
      const block = blocks.find((b) => b.heading === heading);
      if (block) {
        out.body[heading] = lines.slice(block.startLine + 1, block.endLine).join('\n').trim();
      }
    }
  }
  return out;
}

export function applySectionEdit(
  source: string,
  spec: SectionSpec,
  parsed: ParsedSection,
): string {
  let current = source;
  // Diff against the original parse to decide which keys/headings to splice.
  const original = parseSection(source, spec);

  for (const key of spec.yamlKeys) {
    const before = JSON.stringify(original.yaml[key] ?? null);
    const after = JSON.stringify(parsed.yaml[key] ?? null);
    if (before !== after) {
      if (parsed.yaml[key] === undefined || parsed.yaml[key] === null) {
        // Leave as-is for now; deletion isn't a Phase 1 guided affordance.
        continue;
      }
      current = spliceFrontmatterKey(current, key, parsed.yaml[key]);
    }
  }

  for (const heading of spec.bodyHeadings) {
    const before = (original.body[heading] ?? '').trim();
    const after = (parsed.body[heading] ?? '').trim();
    if (before !== after) {
      current = spliceBodySection(current, heading, after);
    }
  }

  return current;
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
