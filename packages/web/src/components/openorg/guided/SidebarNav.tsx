export type Tick = '✓' | '●' | '○';

export interface SidebarSectionState {
  id: string;
  name: string;
  tick: Tick;
  missing: string[];
}

interface SidebarNavProps {
  sections: SidebarSectionState[];
  activeId: string;
  onSelect: (id: string) => void;
  /** Optional "Start here" badge on a specific section id, set by the welcome strip. */
  startHereId?: string;
}

function rollup(sections: SidebarSectionState[]): number {
  if (sections.length === 0) return 100;
  const done = sections.filter((s) => s.tick === '✓').length;
  return Math.round((done / sections.length) * 100);
}

export default function SidebarNav({
  sections,
  activeId,
  onSelect,
  startHereId,
}: SidebarNavProps) {
  const pct = rollup(sections);
  const missing = sections.filter((s) => s.missing.length > 0);

  return (
    <nav aria-label="Editor sections" className="flex flex-col gap-4">
      <ul className="flex flex-col">
        {sections.map((s) => {
          const isActive = s.id === activeId;
          return (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onSelect(s.id)}
                className={`flex w-full items-center justify-between border-l-2 px-3 py-2 text-left text-sm transition ${
                  isActive
                    ? 'border-ink bg-paper-2 text-ink'
                    : 'border-transparent text-muted hover:bg-paper-2/60 hover:text-ink'
                }`}
              >
                <span className="flex items-center gap-2">
                  <span aria-hidden className="font-mono text-xs">
                    {s.tick}
                  </span>
                  <span>{s.name}</span>
                </span>
                {startHereId === s.id && (
                  <span className="border border-rule px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-muted">
                    Start here
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>

      <div className="border-t border-rule pt-3 text-xs text-muted">
        <div className="kicker">{pct}% done</div>
        {missing.length > 0 && (
          <div className="mt-3">
            <div className="kicker mb-2">Missing</div>
            <ul className="flex flex-col gap-1">
              {missing.map((s) =>
                s.missing.map((m) => (
                  <li key={`${s.id}-${m}`}>
                    <button
                      type="button"
                      onClick={() => onSelect(s.id)}
                      className="text-left text-[11px] text-muted hover:text-ink"
                    >
                      · {s.name} — {m}
                    </button>
                  </li>
                )),
              )}
            </ul>
          </div>
        )}
      </div>
    </nav>
  );
}
