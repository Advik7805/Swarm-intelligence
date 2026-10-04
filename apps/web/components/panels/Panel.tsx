import { ReactNode } from "react";

export default function Panel({ title, children, className = "" }: {
  title: string; children: ReactNode; className?: string;
}) {
  return (
    <section className={`glass-panel p-4 ${className}`}>
      <h3 className="mono mb-3 text-[10px] uppercase tracking-[0.18em] text-muted-fg">{title}</h3>
      {children}
    </section>
  );
}
