"use client";

import { MessageSquare, Repeat2, ThumbsUp, XOctagon } from "lucide-react";
import Panel from "./Panel";
import { FACTION_COLORS } from "@/components/three/SwarmCanvas";
import type { AgentAction } from "@/lib/types";

const ICON = {
  post: MessageSquare, reply: Repeat2, endorse: ThumbsUp, dispute: XOctagon,
} as const;

const KIND_COLOR: Record<string, string> = {
  post: "text-hive-cyan", reply: "text-hive-violet",
  endorse: "text-hive-green", dispute: "text-hive-rose",
};

export default function ActivityFeed({ actions, onPick }: {
  actions: AgentAction[]; onPick: (agentId: string) => void;
}) {
  const latest = actions.slice() /* copy */ .reverse().slice(0, 60);
  return (
    <Panel title="live activity" className="flex min-h-0 flex-1 flex-col">
      <div className="-mr-1 min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
        {latest.length === 0 && <p className="text-xs text-muted-fg">The swarm is warming up…</p>}
        {latest.map((a) => {
          const Icon = ICON[a.action] ?? MessageSquare;
          return (
            <button key={a.id} onClick={() => onPick(a.agentId)}
              className="flex w-full items-start gap-2 rounded-md p-1.5 text-left transition-colors hover:bg-surface-2">
              <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${KIND_COLOR[a.action]}`} />
              <span className="min-w-0">
                <span className="flex items-center gap-1.5 text-xs">
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: FACTION_COLORS[a.faction % FACTION_COLORS.length] }} />
                  <span className="truncate font-medium">{a.name}</span>
                  <span className="mono shrink-0 text-[9px] uppercase tracking-wide text-muted-fg">R{a.round}</span>
                </span>
                <span className="mt-0.5 block line-clamp-2 text-xs leading-snug text-muted-fg">{a.text}</span>
              </span>
            </button>
          );
        })}
      </div>
    </Panel>
  );
}
