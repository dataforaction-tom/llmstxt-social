import { useEffect, useId, useState } from 'react';

interface NumberFieldProps {
  label: string;
  /** Current numeric value, or '' when unset. */
  value: number | '';
  /** Emits a number, or undefined when the box is cleared. */
  onChange: (next: number | undefined) => void;
  hint?: string;
  placeholder?: string;
}

/**
 * Numeric guided field. Emits an actual `number` so the bridge serializes it
 * as a YAML number — a plain text field would emit a string and fail schema
 * validation for integer/number leaves (e.g. governance.board_size).
 */
export default function NumberField({ label, value, onChange, hint, placeholder }: NumberFieldProps) {
  const id = useId();
  // Local buffer, like TextField: keeps in-progress text off the round-trip.
  const [local, setLocal] = useState(value === '' ? '' : String(value));
  useEffect(() => {
    setLocal(value === '' ? '' : String(value));
  }, [value]);
  return (
    <label htmlFor={id} className="flex flex-col text-sm">
      <span className="kicker mb-2">{label}</span>
      <input
        id={id}
        type="number"
        value={local}
        onChange={(e) => {
          const raw = e.target.value;
          setLocal(raw);
          if (raw === '') {
            onChange(undefined);
            return;
          }
          const parsed = Number(raw);
          if (!Number.isNaN(parsed)) onChange(parsed);
        }}
        placeholder={placeholder}
        className="border border-rule bg-paper px-3 py-2 text-base text-ink focus:border-ink focus:outline-none"
      />
      {hint && <span className="mt-1 text-xs italic text-muted">{hint}</span>}
    </label>
  );
}
