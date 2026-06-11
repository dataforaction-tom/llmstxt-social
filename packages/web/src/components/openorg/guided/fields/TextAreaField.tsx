import { useId } from 'react';
import type { FieldSource } from './TextField';

const SOURCE_LABELS: Record<FieldSource, string> = {
  cc: 'from Commission filing',
  website: 'from website',
  inferred: 'inferred',
};

interface TextAreaFieldProps {
  label: string;
  value: string;
  onChange: (next: string) => void;
  hint?: string;
  placeholder?: string;
  source?: FieldSource;
  userEdited?: boolean;
  rows?: number;
}

export default function TextAreaField({
  label,
  value,
  onChange,
  hint,
  placeholder,
  source,
  userEdited,
  rows = 4,
}: TextAreaFieldProps) {
  const id = useId();
  const showChip = source && !userEdited;
  return (
    <label htmlFor={id} className="flex flex-col text-sm">
      <span className="kicker mb-2 flex items-center gap-2">
        {label}
        {showChip && (
          <span className="border border-rule px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-muted">
            {SOURCE_LABELS[source]}
          </span>
        )}
      </span>
      <textarea
        id={id}
        rows={rows}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="border border-rule bg-paper px-3 py-2 text-base leading-relaxed text-ink focus:border-ink focus:outline-none"
      />
      {hint && <span className="mt-1 text-xs italic text-muted">{hint}</span>}
    </label>
  );
}
