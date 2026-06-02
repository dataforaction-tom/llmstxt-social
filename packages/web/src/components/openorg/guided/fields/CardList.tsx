import { useState } from 'react';
import TextField from './TextField';
import TextAreaField from './TextAreaField';
import type { FieldDef } from '../sections/profile';

interface CardListProps {
  label: string;
  value: Record<string, unknown>[];
  shape: FieldDef[];
  onChange: (next: Record<string, unknown>[]) => void;
  hint?: string;
}

function titleOf(item: Record<string, unknown>, shape: FieldDef[]): string {
  for (const f of shape) {
    const v = item?.[f.key];
    if (typeof v === 'string' && v.trim()) {
      return v.slice(0, 80);
    }
  }
  return '(untitled)';
}

function blankItem(shape: FieldDef[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of shape) out[f.key] = '';
  return out;
}

export default function CardList({ label, value, shape, onChange, hint }: CardListProps) {
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  const handleFieldChange = (idx: number, key: string, next: string) => {
    const updated = value.map((item, i) => (i === idx ? { ...item, [key]: next } : item));
    onChange(updated);
  };

  const handleAdd = () => {
    onChange([...value, blankItem(shape)]);
    setOpenIdx(value.length);
  };

  const handleRemove = (idx: number) => {
    onChange(value.filter((_, i) => i !== idx));
    setOpenIdx(null);
  };

  return (
    <div className="flex flex-col text-sm">
      <span className="kicker mb-2">{label}</span>
      <ul className="flex flex-col gap-2">
        {value.map((item, idx) => {
          const open = idx === openIdx;
          return (
            <li key={idx} className="border border-rule bg-paper">
              <button
                type="button"
                onClick={() => setOpenIdx(open ? null : idx)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-ink hover:bg-paper-2"
                aria-expanded={open}
              >
                <span>{titleOf(item, shape)}</span>
                <span className="text-xs text-muted">{open ? 'Close' : 'Edit'}</span>
              </button>
              {open && (
                <div className="flex flex-col gap-3 border-t border-rule px-3 py-3">
                  {shape.map((f) => {
                    const fieldValue = typeof item?.[f.key] === 'string' ? (item[f.key] as string) : '';
                    if (f.kind === 'textarea') {
                      return (
                        <TextAreaField
                          key={f.key}
                          label={f.label}
                          value={fieldValue}
                          onChange={(next) => handleFieldChange(idx, f.key, next)}
                        />
                      );
                    }
                    return (
                      <TextField
                        key={f.key}
                        label={f.label}
                        value={fieldValue}
                        onChange={(next) => handleFieldChange(idx, f.key, next)}
                      />
                    );
                  })}
                  <button
                    type="button"
                    onClick={() => handleRemove(idx)}
                    className="self-start border border-rule px-3 py-1 text-xs uppercase tracking-wider text-muted hover:text-red-900"
                  >
                    Remove
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <button
        type="button"
        onClick={handleAdd}
        className="mt-3 self-start border border-rule bg-paper-2 px-3 py-1 text-xs uppercase tracking-wider text-ink hover:bg-paper"
      >
        + Add
      </button>
      {hint && <span className="mt-2 text-xs italic text-muted">{hint}</span>}
    </div>
  );
}
