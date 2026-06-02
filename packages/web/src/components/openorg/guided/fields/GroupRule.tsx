import type { ReactNode } from 'react';

interface GroupRuleProps {
  caption: string;
  children: ReactNode;
}

export default function GroupRule({ caption, children }: GroupRuleProps) {
  return (
    <div className="mt-4 border-t border-dashed border-rule pt-3">
      <div className="kicker mb-3 text-muted">{caption}</div>
      <div className="flex flex-col gap-3">{children}</div>
    </div>
  );
}
