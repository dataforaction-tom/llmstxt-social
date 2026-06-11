import { parseSection } from './bridge';
import type { GuidedSection } from './sections/profile';
import type { SidebarSectionState } from './SidebarNav';

function isFilled(value: unknown): boolean {
  if (value == null) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') {
    return Object.values(value as Record<string, unknown>).some(isFilled);
  }
  return true;
}

function fieldValue(parsed: ReturnType<typeof parseSection>, key: string): unknown {
  if (key.includes('.')) {
    const [head, ...rest] = key.split('.');
    let cursor: unknown = parsed.yaml[head];
    for (const part of rest) {
      if (cursor == null || typeof cursor !== 'object') return undefined;
      cursor = (cursor as Record<string, unknown>)[part];
    }
    return cursor;
  }
  if (parsed.body[key] !== undefined) return parsed.body[key];
  return parsed.yaml[key];
}

export function computeTickStates(
  source: string,
  sections: GuidedSection[],
): SidebarSectionState[] {
  return sections.map((section) => {
    const parsed = parseSection(source, section);
    const fieldsFilled = section.fields.map((f) => isFilled(fieldValue(parsed, f.key)));
    const filled = fieldsFilled.filter(Boolean).length;
    const missing = section.fields
      .filter((_, i) => !fieldsFilled[i])
      .map((f) => f.label.toLowerCase());
    let tick: '✓' | '●' | '○';
    if (filled === 0) tick = '○';
    else if (filled === section.fields.length) tick = '✓';
    else tick = '●';
    return { id: section.id, name: section.name, tick, missing };
  });
}
