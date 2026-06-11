import TextField from './fields/TextField';
import TextAreaField from './fields/TextAreaField';
import PillPicker, { type PillOption } from './fields/PillPicker';
import CardList from './fields/CardList';
import GroupRule from './fields/GroupRule';
import type { ParsedSection } from './bridge';
import type { FieldDef, GuidedSection } from './sections/profile';

interface SectionProps {
  section: GuidedSection;
  parsed: ParsedSection;
  onChange: (next: ParsedSection) => void;
  vocabs: Record<string, PillOption[]>;
}

function getByPath(parsed: ParsedSection, key: string): unknown {
  if (key.includes('.')) {
    const [head, ...rest] = key.split('.');
    let cursor: unknown = parsed.yaml[head];
    for (const part of rest) {
      if (cursor == null || typeof cursor !== 'object') return undefined;
      cursor = (cursor as Record<string, unknown>)[part];
    }
    return cursor;
  }
  // Body section: key is a heading.
  if (parsed.body[key] !== undefined) return parsed.body[key];
  // Top-level yaml key.
  return parsed.yaml[key];
}

function setByPath(parsed: ParsedSection, key: string, value: unknown): ParsedSection {
  const next: ParsedSection = {
    yaml: { ...parsed.yaml },
    body: { ...parsed.body },
  };
  if (key.includes('.')) {
    const [head, ...rest] = key.split('.');
    const headObj: Record<string, unknown> = {
      ...((next.yaml[head] as Record<string, unknown>) ?? {}),
    };
    let cursor: Record<string, unknown> = headObj;
    for (let i = 0; i < rest.length - 1; i += 1) {
      cursor[rest[i]] = { ...((cursor[rest[i]] as Record<string, unknown>) ?? {}) };
      cursor = cursor[rest[i]] as Record<string, unknown>;
    }
    cursor[rest[rest.length - 1]] = value;
    next.yaml[head] = headObj;
    return next;
  }
  // Heuristic for yaml vs body: yaml top-level keys are snake_case lowercase
  // without spaces; body headings have spaces or start uppercase.
  if (key === key.toLowerCase() && !/\s/.test(key)) {
    next.yaml[key] = value;
  } else {
    next.body[key] = typeof value === 'string' ? value : '';
  }
  return next;
}

function renderField(
  field: FieldDef,
  parsed: ParsedSection,
  onChange: (next: ParsedSection) => void,
  vocabs: Record<string, PillOption[]>,
): JSX.Element {
  const value = getByPath(parsed, field.key);

  if (field.kind === 'text') {
    return (
      <TextField
        key={field.key}
        label={field.label}
        value={typeof value === 'string' ? value : ''}
        hint={field.hint}
        placeholder={field.placeholder}
        onChange={(v) => onChange(setByPath(parsed, field.key, v))}
      />
    );
  }
  if (field.kind === 'textarea') {
    return (
      <TextAreaField
        key={field.key}
        label={field.label}
        value={typeof value === 'string' ? value : ''}
        hint={field.hint}
        placeholder={field.placeholder}
        onChange={(v) => onChange(setByPath(parsed, field.key, v))}
      />
    );
  }
  if (field.kind === 'pills') {
    const options = (field.vocab ? vocabs[field.vocab] : undefined) ?? [];
    const arr: string[] = Array.isArray(value)
      ? (value as string[])
      : typeof value === 'string' && value
      ? [value]
      : [];
    return (
      <PillPicker
        key={field.key}
        label={field.label}
        options={options}
        value={arr}
        hint={field.hint}
        selectionCap={field.selectionCap}
        onChange={(v) =>
          onChange(setByPath(parsed, field.key, field.selectionCap === 1 ? v[0] ?? '' : v))
        }
      />
    );
  }
  if (field.kind === 'card-list') {
    return (
      <CardList
        key={field.key}
        label={field.label}
        value={Array.isArray(value) ? (value as Record<string, unknown>[]) : []}
        shape={field.cardShape ?? []}
        hint={field.hint}
        onChange={(v) => onChange(setByPath(parsed, field.key, v))}
      />
    );
  }
  if (field.kind === 'group') {
    return (
      <GroupRule key={field.key} caption={field.label}>
        {(field.children ?? []).map((child) => {
          const childKey = `${field.key}.${child.key}`;
          const childValue = getByPath(parsed, childKey);
          if (child.kind === 'textarea') {
            return (
              <TextAreaField
                key={childKey}
                label={child.label}
                value={typeof childValue === 'string' ? childValue : ''}
                onChange={(v) => onChange(setByPath(parsed, childKey, v))}
              />
            );
          }
          if (child.kind === 'card-list') {
            return (
              <CardList
                key={childKey}
                label={child.label}
                value={Array.isArray(childValue) ? (childValue as Record<string, unknown>[]) : []}
                shape={child.cardShape ?? []}
                onChange={(v) => onChange(setByPath(parsed, childKey, v))}
              />
            );
          }
          if (child.kind === 'group') {
            return (
              <GroupRule key={childKey} caption={child.label}>
                {(child.children ?? []).map((grand) => {
                  const grandKey = `${childKey}.${grand.key}`;
                  const grandValue = getByPath(parsed, grandKey);
                  return (
                    <TextField
                      key={grandKey}
                      label={grand.label}
                      value={typeof grandValue === 'string' ? grandValue : ''}
                      onChange={(v) => onChange(setByPath(parsed, grandKey, v))}
                    />
                  );
                })}
              </GroupRule>
            );
          }
          return (
            <TextField
              key={childKey}
              label={child.label}
              value={typeof childValue === 'string' ? childValue : ''}
              onChange={(v) => onChange(setByPath(parsed, childKey, v))}
            />
          );
        })}
      </GroupRule>
    );
  }
  return <span key={field.key}>Unsupported field kind: {field.kind}</span>;
}

function sectionIsEmpty(section: GuidedSection, parsed: ParsedSection): boolean {
  return section.fields.every((f) => {
    const v = getByPath(parsed, f.key);
    if (v == null) return true;
    if (typeof v === 'string') return v.trim() === '';
    if (Array.isArray(v)) return v.length === 0;
    if (typeof v === 'object') {
      return Object.values(v as Record<string, unknown>).every((x) => x == null || x === '');
    }
    return false;
  });
}

export default function Section({ section, parsed, onChange, vocabs }: SectionProps) {
  const empty = sectionIsEmpty(section, parsed);
  return (
    <section className="flex flex-col gap-4" data-section-id={section.id}>
      <header>
        <div className="kicker">{section.name}</div>
        <p className="mt-1 max-w-prose text-sm text-muted">{section.description}</p>
      </header>
      {empty && section.emptyPrompt && (
        <p className="max-w-prose border-l-2 border-rule pl-3 text-sm italic text-muted">
          {section.emptyPrompt}
        </p>
      )}
      <div className="flex flex-col gap-4">
        {section.fields.map((f) => renderField(f, parsed, onChange, vocabs))}
      </div>
    </section>
  );
}
