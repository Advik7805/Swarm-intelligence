"use client";

import { create } from "zustand";
import type { AgentAction, InjectedEvent, MetricsEvent, RunStatus, WSEvent } from "@/lib/types";

const MAX_ACTIONS = 20_000;

interface AgentMeta {
  id: string;
  name: string;
  archetype: string;
  faction: number;
  platform: string;
  influence: number;
}

interface RunStore {
  runId: string | null;
  projectId: string | null;
  status: RunStatus["status"] | "loading";
  mode: "demo" | "live" | null;
  rounds: number;
  latestRound: number;
  scrubRound: number | null; // null = follow live
  playing: boolean;
  playbackSpeed: number;
  wsState: "connecting" | "open" | "closed" | "error";
  agents: Record<string, AgentMeta>;
  actionsByRound: Record<number, AgentAction[]>;
  actionTotal: number;
  metricSeries: MetricsEvent[];
  events: InjectedEvent[];
  reportStage: string | null;
  selected: string | null;
  hasReport: boolean;

  reset: (runId: string, projectId: string) => void;
  hydrateStatus: (s: RunStatus) => void;
  applyEvent: (ev: WSEvent) => void;
  setScrub: (r: number | null) => void;
  setPlaying: (p: boolean) => void;
  setPlaybackSpeed: (s: number) => void;
  setWsState: (s: RunStore["wsState"]) => void;
  select: (agentId: string | null) => void;
}

export const useRunStore = create<RunStore>((set, get) => ({
  runId: null,
  projectId: null,
  status: "loading",
  mode: null,
  rounds: 0,
  latestRound: 0,
  scrubRound: null,
  playing: true,
  playbackSpeed: 2,
  wsState: "connecting",
  agents: {},
  actionsByRound: {},
  actionTotal: 0,
  metricSeries: [],
  events: [],
  reportStage: null,
  selected: null,
  hasReport: false,

  reset: (runId, projectId) =>
    set({
      runId, projectId, status: "loading", latestRound: 0, scrubRound: null,
      agents: {}, actionsByRound: {}, actionTotal: 0, metricSeries: [],
      events: [], reportStage: null, selected: null, hasReport: false, playing: true,
    }),

  hydrateStatus: (s) =>
    set({
      status: s.status, rounds: s.rounds, mode: s.mode,
      latestRound: Math.max(get().latestRound, s.round),
      hasReport: s.hasReport,
      projectId: s.projectId,
    }),

  applyEvent: (ev) => {
    const st = get();
    switch (ev.type) {
      case "round_started": {
        const latestRound = Math.max(st.latestRound, ev.round ?? 0);
        set({
          latestRound,
          status: "running",
          ...(st.scrubRound === null ? {} : {}),
        });
        break;
      }
      case "round_batch": {
        const round = ev.round ?? 0;
        const actions = ev.actions ?? [];
        let total = st.actionTotal + actions.length;
        const agents = { ...st.agents };
        for (const a of actions) {
          agents[a.agentId] = {
            id: a.agentId, name: a.name, archetype: a.archetype ?? agents[a.agentId]?.archetype ?? "",
            faction: st.agents[a.agentId]?.faction ?? a.faction,
            platform: a.platform, influence: a.influence,
          };
        }
        const actionsByRound = { ...st.actionsByRound, [round]: actions };
        // memory guard
        if (total > MAX_ACTIONS) {
          const keys = Object.keys(actionsByRound).map(Number).sort((a, b) => a - b);
          const drop = keys.slice(0, Math.ceil(keys.length / 4));
          for (const k of drop) delete actionsByRound[k];
          total = Object.values(actionsByRound).reduce((n, arr) => n + arr.length, 0);
        }
        set({ agents, actionsByRound, actionTotal: total });
        break;
      }
      case "metrics": {
        const m = ev.metrics ?? (ev as unknown as MetricsEvent);
        set({
          metricSeries: [...st.metricSeries.slice(-300), {
            round: m.round ?? ev.round ?? 0,
            sentimentAvg: m.sentimentAvg ?? 0,
            activityCount: m.activityCount ?? 0,
            factionShares: m.factionShares ?? {},
            topInfluencers: m.topInfluencers ?? [],
          }],
        });
        break;
      }
      case "graph_update": {
        if (!ev.factions) break;
        const agents = { ...st.agents };
        for (const [id, f] of Object.entries(ev.factions)) {
          if (agents[id]) agents[id] = { ...agents[id], faction: f };
        }
        set({ agents });
        break;
      }
      case "event_injected":
        set({ events: [...st.events, { tick: ev.tick ?? st.latestRound, text: ev.text ?? "" }] });
        break;
      case "report_progress":
        set({ reportStage: ev.stage ?? null, hasReport: true });
        break;
      case "run_complete":
        set({ status: ev.summary?.stopped ? "stopped" : "complete", playing: false });
        break;
      case "error":
        set({ status: "failed" });
        break;
    }
  },

  setScrub: (r) => set({ scrubRound: r }),
  setPlaying: (p) => set({ playing: p }),
  setPlaybackSpeed: (s) => set({ playbackSpeed: s }),
  setWsState: (s) => set({ wsState: s }),
  select: (agentId) => set({ selected: agentId }),
}));
