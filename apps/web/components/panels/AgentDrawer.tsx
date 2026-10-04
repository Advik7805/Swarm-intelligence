"use client";

import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import ChatBox from "./ChatBox";
import { FACTION_COLORS } from "@/components/three/SwarmCanvas";

interface AgentMetaLite {
  id: string; name: string; archetype: string; faction: number; platform: string; influence: number;
}

export default function AgentDrawer({ runId, agent, onClose, extra }: {
  runId: string;
  agent: AgentMetaLite;
  onClose: () => void;
  extra?: { stance?: number; platform?: string };
}) {
  const [tab, setTab] = useState<"profile" | "chat">("profile");
  const [data, setData] = useState<{ memory: string[]; stanceTrace: { round: number; sentiment: number }[] } | null>(null);

  useEffect(() => {
    setData(null);
    apiFetch<{ memory: string[]; stanceTrace: { round: number; sentiment: number }[] }>(
      `/runs/${runId}/agents/${agent.id}/memory`
    ).then(setData).catch(() => setData({ memory: [], stanceTrace: [] }));
  }, [runId, agent.id]);

  const spark = useMemo(() => {
    const t = data?.stanceTrace ?? [];
    if (!t.length) return null;
    const W = 260, H = 56;
    const maxR = Math.max(...t.map((p) => p.round), 1);
    const pts = t.map((p) => `${(p.round / maxR) * W},${(1 - (p.sentiment + 1) / 2) * H}`).join(" ");
    return { W, H, pts };
  }, [data]);

  return (
    <aside className="glass-panel flex h-full w-80 shrink-0 flex-col p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold">{agent.name}</h3>
          <div className="mono mt-0.5 text-[10px] uppercase tracking-wider text-muted-fg">
            {agent.archetype || "agent"} · {agent.platform}
          </div>
        </div>
        <button onClick={onClose} aria-label="close agent panel"
          className="rounded-md p-1.5 text-muted-fg transition-colors hover:bg-surface-2 hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="mt-2 flex items-center gap-2 text-[11px]">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2 py-0.5">
          <span className="h-2 w-2 rounded-full" style={{ background: FACTION_COLORS[agent.faction % FACTION_COLORS.length] }} />
          faction {agent.faction}
        </span>
        <span className="mono text-muted-fg">influence {(agent.influence * 100).toFixed(0)}%</span>
      </div>

      <div className="mono mt-4 flex gap-1 text-[11px] uppercase tracking-wider">
        {(["profile", "chat"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`rounded-md px-3 py-1.5 transition-colors ${tab === t ? "bg-hive-amber/15 text-hive-amber" : "text-muted-fg hover:text-foreground"}`}>
            {t === "chat" ? "chat with agent" : t}
          </button>
        ))}
      </div>

      {tab === "profile" ? (
        <div className="mt-4 min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
          <div>
            <div className="mono text-[10px] uppercase tracking-widest text-muted-fg">stance over time</div>
            {spark ? (
              <svg viewBox={`0 0 ${spark.W} ${spark.H}`} className="mt-2 w-full">
                <line x1="0" y1={spark.H / 2} x2={spark.W} y2={spark.H / 2} stroke="hsl(224 18% 20%)" strokeWidth="1" />
                <polyline points={spark.pts} fill="none" stroke="#ffab00" strokeWidth="1.5" />
              </svg>
            ) : (
              <p className="mt-2 text-xs text-muted-fg">No stance samples yet for this agent.</p>
            )}
          </div>
          <div>
            <div className="mono text-[10px] uppercase tracking-widest text-muted-fg">memory ({data?.memory.length ?? 0})</div>
            <ul className="mt-2 space-y-1.5">
              {(data?.memory.slice(-12) ?? []).map((m, i) => (
                <li key={i} className="rounded-md bg-surface-2/70 px-2.5 py-1.5 text-[11px] leading-snug text-muted-fg">{m}</li>
              ))}
              {data && data.memory.length === 0 && (
                <li className="text-xs text-muted-fg">This agent kept its thoughts to itself.</li>
              )}
              {!data && <li className="text-xs text-muted-fg">loading memory…</li>}
            </ul>
          </div>
        </div>
      ) : (
        <div className="mt-4 flex min-h-0 flex-1 flex-col">
          <ChatBox
            endpoint={`/runs/${runId}/chat/agent/${agent.id}`}
            placeholder={`Ask ${agent.name.split(" ")[0]} anything…`}
            emptyHint={`${agent.name} answers in character, from what it actually saw and said during the simulation.`}
          />
        </div>
      )}
    </aside>
  );
}
