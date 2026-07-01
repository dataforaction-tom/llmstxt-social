import { useId } from 'react';

interface StringListFieldProps {
  label: string;
  value: string[];
  onChange: (next: string[]) => void;
  hint?: string;
  placeholder?: string;
}

/**
 * Edits an array of plain strings (e.g. identity.also_known_as, place.area_codes).
 * A card-list would emit an array of objects and fail schema validation
 * ("{value: …} is not of type 'string'"); this emits a flat string[].
 */
export default function StringListField({
  label,
  value,
  onChange,
  hint,
  placeholder,
}: StringListFieldProps) {
  const id = useId();
  const update = (idx: number, next: string) =>
    onChange(value.map((item, i) => (i === idx ? next : item)));
  const add = () => onChange([...value, '']);
  const remove = (idx: number) => onChange(value.filter((_, i) => i !== idx));

  return (
    <div className="flex flex-col text-sm">
      <span id={id} className="kicker mb-2">
        {label}
      </span>
      <ul className="flex flex-col gap-2" aria-labelledby={id}>
        {value.map((item, idx) => (
          <li key={idx} className="flex gap-2">
            <input
              type="text"
              aria-label={`${label} ${idx + 1}`}
              value={item}
              onChange={(e) => update(idx, e.target.value)}
              placeholder={placeholder}
              className="flex-1 border border-rule bg-cream px-3 py-2 text-base text-navy focus:border-navy focus:outline-none"
            />
            <button
              type="button"
              onClick={() => remove(idx)}
              className="border border-rule px-3 text-xs uppercase tracking-wider text-grey-blue hover:text-red-900"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={add}
        className="mt-3 self-start border border-rule bg-cream-dark px-3 py-1 text-xs uppercase tracking-wider text-navy hover:bg-cream"
      >
        + Add
      </button>
      {hint && <span className="mt-2 text-xs italic text-grey-blue">{hint}</span>}
    </div>
  );
}
