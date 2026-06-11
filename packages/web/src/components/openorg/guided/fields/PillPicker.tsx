import { useState } from 'react';

export interface PillOption {
  key: string;
  label: string;
}

interface PillPickerProps {
  label: string;
  options: PillOption[];
  value: string[];
  onChange: (next: string[]) => void;
  /** Multi-select unless ``selectionCap === 1`` (radio behaviour). */
  selectionCap?: number;
  hint?: string;
}

export default function PillPicker({
  label,
  options,
  value,
  onChange,
  selectionCap,
  hint,
}: PillPickerProps) {
  const [capNudge, setCapNudge] = useState(false);

  const isSelected = (key: string) => value.includes(key);
  const handleClick = (key: string) => {
    if (selectionCap === 1) {
      onChange([key]);
      return;
    }
    if (isSelected(key)) {
      onChange(value.filter((v) => v !== key));
      setCapNudge(false);
      return;
    }
    if (selectionCap !== undefined && value.length >= selectionCap) {
      setCapNudge(true);
      return;
    }
    onChange([...value, key]);
  };

  return (
    <div className="flex flex-col text-sm">
      <span className="kicker mb-2">{label}</span>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const sel = isSelected(opt.key);
          return (
            <button
              key={opt.key}
              type="button"
              onClick={() => handleClick(opt.key)}
              aria-pressed={sel}
              className={`border px-3 py-1 text-xs uppercase tracking-wider transition ${
                sel
                  ? 'border-ink bg-ink text-paper'
                  : 'border-rule bg-paper text-muted hover:border-ink/40 hover:text-ink'
              }`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
      {capNudge && (
        <span className="mt-2 text-xs italic text-muted">
          Six is plenty — uncheck one first.
        </span>
      )}
      {hint && !capNudge && <span className="mt-2 text-xs italic text-muted">{hint}</span>}
    </div>
  );
}
