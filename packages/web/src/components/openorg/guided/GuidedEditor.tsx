import { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import SidebarNav from './SidebarNav';
import Section from './Section';
import { applySectionEdit, parseSection, type ParsedSection } from './bridge';
import { computeTickStates } from './tickState';
import type { GuidedSection } from './sections/profile';
import type { PillOption } from './fields/PillPicker';

interface GuidedEditorProps {
  source: string;
  sections: GuidedSection[];
  onChange: (nextSource: string) => void;
  vocabs: Record<string, PillOption[]>;
  startHereId?: string;
}

function splitFrontmatterPreview(src: string): { frontmatter: string; body: string } {
  if (!src.startsWith('---\n') && !src.startsWith('---\r\n')) return { frontmatter: '', body: src };
  const closing = src.indexOf('\n---', 4);
  if (closing === -1) return { frontmatter: src, body: '' };
  return { frontmatter: src.slice(0, closing + 4), body: src.slice(closing + 4).replace(/^\r?\n/, '') };
}

export default function GuidedEditor({
  source,
  sections,
  onChange,
  vocabs,
  startHereId,
}: GuidedEditorProps) {
  const [activeId, setActiveId] = useState(sections[0]?.id ?? '');
  const ticks = useMemo(() => computeTickStates(source, sections), [source, sections]);
  const active = sections.find((s) => s.id === activeId) ?? sections[0];
  const parsed: ParsedSection = useMemo(() => parseSection(source, active), [source, active]);
  const { body } = useMemo(() => splitFrontmatterPreview(source), [source]);

  const handleSectionChange = (next: ParsedSection) => {
    onChange(applySectionEdit(source, active, next));
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[14rem_minmax(0,1fr)_minmax(0,1fr)]">
      <aside className="lg:border-r lg:border-rule lg:pr-4">
        <SidebarNav
          sections={ticks}
          activeId={active.id}
          onSelect={setActiveId}
          startHereId={startHereId}
        />
      </aside>
      <div>
        <Section section={active} parsed={parsed} onChange={handleSectionChange} vocabs={vocabs} />
      </div>
      <div className="border-l border-rule pl-4 lg:overflow-auto">
        <div className="kicker mb-2">Preview</div>
        <article className="editorial-preview text-ink">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
        </article>
      </div>
    </div>
  );
}
