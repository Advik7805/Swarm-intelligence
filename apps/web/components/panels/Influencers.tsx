"use client";

import Panel from "./Panel";
import { FACTION_COLORS } from "@/components/three/SwarmCanvas";

export default function Influencers({ list, onFocus }: {
  list: { id: string; name: string; faction: number; archetype?: string; score: number }[];
  onFocus: (id: string) => void;
}) {
  return (
    <Panel title="top influencers">
      {list.length === 0 ? (
        <p className="text-xs text-muted-fg">No ranking yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {list.map((a, i) => (
            <li key={a.id}>
              <button onClick={() => onFocus(a.id)}
                className="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-surface-2">
                <span className="mono w-4 text-[10px] text-muted-fg">{i + 1}</span>
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: FACTION_COLORS[a.faction % FACTION_COLORS.length] }} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{a.name}</span>
                  <span className="mono block truncate text-[10px] uppercase tracking-wide text-muted-fg">{a.archetype || "agent"}</span>
                </span>
                <span className="mono text-[11px] text-hive-amber">{a.score.toFixed(0)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
