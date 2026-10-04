"use client";

import Panel from "./Panel";
import { FACTION_COLORS } from "@/components/three/SwarmCanvas";

export default function FactionBar({ shares }: { shares: Record<string, number> }) {
  const entries = Object.entries(shares).sort((a, b) => b[1] - a[1]).slice(0, 6);
  const total = entries.reduce((n, [, v]) => n + v, 0) || 1;
  return (
    <Panel title="factions">
      {entries.length === 0 ? (
        <p className="text-xs text-muted-fg">Waiting for the first rounds…</p>
      ) : (
        <>
          <div className="flex h-3 w-full overflow-hidden rounded-full bg-surface-2">
            {entries.map(([f, v]) => (
              <div key={f} style={{ width: `${(v / total) * 100}%`, background: FACTION_COLORS[Number(f) % FACTION_COLORS.length] }} />
            ))}
          </div>
          <div className="mono mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted-fg">
            {entries.map(([f, v]) => (
              <span key={f} className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm" style={{ background: FACTION_COLORS[Number(f) % FACTION_COLORS.length] }} />
                F{f} · {(v * 100).toFixed(0)}%
              </span>
            ))}
          </div>
        </>
      )}
    </Panel>
  );
}
