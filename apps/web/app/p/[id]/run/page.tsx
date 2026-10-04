"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { FileText, Loader2, Pause, Play, Square } from "lucide-react";
import { apiFetch, apiPost } from "@/lib/api";
import { RunSocket } from "@/lib/ws";
import { useRunStore } from "@/store/run";
import type { Project, RunStatus } from "@/lib/types";
import StatusChip from "@/components/panels/StatusChip";
import SentimentChart from "@/components/panels/SentimentChart";
import FactionBar from "@/components/panels/FactionBar";
import Influencers from "@/components/panels/Influencers";
import ActivityFeed from "@/components/panels/ActivityFeed";
import Timeline from "@/components/panels/Timeline";
import InjectConsole from "@/components/panels/InjectConsole";
import AgentDrawer from "@/components/panels/AgentDrawer";

const SwarmCanvas = dynamic(() => import("@/components/three/SwarmCanvas"), { ssr: false });

function MissionControl() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const search = useSearchParams();
  const runStore = useRunStore();
  const socketRef = useRef<RunSocket | null>(null);
  const [runId, setRunId] = useState<string | null>(search.get("run"));
  const [project, setProject] = useState<Project | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [ctrlBusy, setCtrlBusy] = useState(false);

  // resolve run id + hydrate
  useEffect(() => {
    (async () => {
      try {
        const p = await apiFetch<Project>(`/projects/${id}`);
        setProject(p);
        const rid = runId ?? p.currentRunId ?? null;
        if (!rid) { router.replace(`/p/${id}/build`); return; }
        setRunId(rid);
      } catch (e) {
        setFatal(e instanceof Error ? e.message : "failed to load project");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // connect stream (replay first, then live)
  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    (async () => {
      try {
        const status = await apiFetch<RunStatus>(`/runs/${runId}`);
        if (cancelled) return;
        runStore.reset(runId, status.projectId);
        runStore.hydrateStatus(status);
        const sock = new RunSocket(runId, 0, {
          onEvent: (ev) => useRunStore.getState().applyEvent(ev),
          onState: (s) => useRunStore.getState().setWsState(s),
          shouldContinue: () => {
            const st = useRunStore.getState().status;
            return st === "running" || st === "queued" || st === "paused" || st === "loading";
          },
        });
        socketRef.current = sock;
        sock.connect();
      } catch (e) {
        if (!cancelled) setFatal(e instanceof Error ? e.message : "failed to load run");
      }
    })();
    return () => { cancelled = true; socketRef.current?.close(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  // replay tick
  useEffect(() => {
    if (!runStore.playing || runStore.scrubRound === null) return;
    const iv = setInterval(() => {
      const st = useRunStore.getState();
      const next = (st.scrubRound ?? 1) + 1;
      if (next >= st.latestRound) {
        st.setScrub(null); // catch up to live
      } else {
        st.setScrub(next);
      }
    }, Math.max(80, 1000 / runStore.playbackSpeed));
    return () => clearInterval(iv);
  }, [runStore.playing, runStore.scrubRound, runStore.playbackSpeed]);

  const displayRound = runStore.scrubRound ?? runStore.latestRound;
  const live = runStore.status === "running" || runStore.status === "paused" || runStore.status === "queued";

  const latestMetrics = runStore.metricSeries[runStore.metricSeries.length - 1];
  const feedActions = useMemo(() => {
    // feed shows the newest rounds relative to displayRound
    const rounds = Object.keys(runStore.actionsByRound).map(Number).filter((r) => r <= displayRound).sort((a, b) => b - a);
    const out = [];
    for (const r of rounds.slice(0, 4)) out.push(...(runStore.actionsByRound[r] ?? []));
    return out;
  }, [runStore.actionsByRound, displayRound]);

  const control = async (action: "pause" | "resume" | "stop") => {
    if (!runId) return;
    setCtrlBusy(true);
    try {
      await apiPost(`/runs/${runId}/control`, { action });
      if (action === "pause") runStore.hydrateStatus({ ...(await apiFetch<RunStatus>(`/runs/${runId}`)) });
    } catch { /* surfaced via ws error state */ }
    setCtrlBusy(false);
  };

  const generateReport = async () => {
    if (!runId) return;
    setReportBusy(true);
    try {
      await apiPost(`/runs/${runId}/report`);
      router.push(`/p/${id}/report?run=${runId}`);
    } catch { setReportBusy(false); }
  };

  const focusAgent = useCallback((agentId: string) => useRunStore.getState().select(agentId), []);

  if (fatal) {
    return (
      <div className="mx-auto max-w-xl px-4 py-24 text-center">
        <p className="text-hive-rose">{fatal}</p>
      </div>
    );
  }

  if (!runId) {
    return (
      <div className="flex h-[70vh] items-center justify-center gap-3 text-muted-fg">
        <Loader2 className="h-5 w-5 animate-spin text-hive-amber" /> entering mission control…
      </div>
    );
  }

  const selectedAgent = runStore.selected ? runStore.agents[runStore.selected] : null;

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col">
      {/* top bar */}
      <div className="flex flex-wrap items-center gap-3 border-b border-border/70 px-4 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold">{project?.name ?? "…"}</h1>
          <p className="mono max-w-xl truncate text-[11px] text-muted-fg">“{project?.question ?? ""}”</p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <StatusChip status={runStore.status} wsState={runStore.wsState} />
          <span className="mono rounded-full border border-border bg-surface px-3 py-1 text-[11px] uppercase tracking-wider text-muted-fg">
            {runStore.mode ?? "…"} swarm · {runStore.actionTotal} actions
          </span>
          {runStore.status === "running" ? (
            <button onClick={() => control("pause")} disabled={ctrlBusy}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs transition-colors hover:bg-surface-2">
              <Pause className="h-3.5 w-3.5" /> pause
            </button>
          ) : runStore.status === "paused" ? (
            <button onClick={() => control("resume")} disabled={ctrlBusy}
              className="inline-flex items-center gap-1.5 rounded-lg border border-hive-amber/50 bg-hive-amber/10 px-3 py-1.5 text-xs text-hive-amber">
              <Play className="h-3.5 w-3.5" /> resume
            </button>
          ) : null}
          {(runStore.status === "running" || runStore.status === "paused") && (
            <button onClick={() => control("stop")} disabled={ctrlBusy}
              className="inline-flex items-center gap-1.5 rounded-lg border border-hive-rose/40 bg-hive-rose/10 px-3 py-1.5 text-xs text-hive-rose">
              <Square className="h-3.5 w-3.5" /> stop
            </button>
          )}
          <button onClick={generateReport}
            disabled={reportBusy || runStore.latestRound < 1}
            className="inline-flex items-center gap-1.5 rounded-lg bg-hive-amber px-4 py-1.5 text-xs font-semibold text-black transition-transform hover:scale-[1.03] disabled:opacity-40">
            {reportBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileText className="h-3.5 w-3.5" />}
            {runStore.hasReport ? "view report" : runStore.reportStage ? `report: ${runStore.reportStage}` : "generate report"}
          </button>
        </div>
      </div>

      {/* main area */}
      <div className="flex min-h-0 flex-1 gap-3 p-3">
        <div className="relative min-w-0 flex-1 overflow-hidden rounded-xl border border-border">
          <SwarmCanvas
            agents={runStore.agents}
            actionsByRound={runStore.actionsByRound}
            displayRound={displayRound}
            events={runStore.events}
            selected={runStore.selected}
            onSelect={(sid) => useRunStore.getState().select(sid)}
            highlightText={runStore.status === "running" ? `${runStore.rounds ? `${runStore.rounds} planned` : ""}` : runStore.status.toUpperCase()}
          />
        </div>

        {selectedAgent && (
          <AgentDrawer
            runId={runId}
            agent={selectedAgent}
            onClose={() => useRunStore.getState().select(null)}
          />
        )}

        <div className="flex w-80 shrink-0 flex-col gap-3 overflow-y-auto max-lg:hidden">
          <SentimentChart series={runStore.metricSeries} />
          <FactionBar shares={latestMetrics?.factionShares ?? {}} />
          <Influencers list={latestMetrics?.topInfluencers ?? []} onFocus={focusAgent} />
          <ActivityFeed actions={feedActions} onPick={focusAgent} />
        </div>
      </div>

      {/* bottom strip */}
      <div className="space-y-3 px-3 pb-3">
        <InjectConsole runId={runId} live={live} />
        <Timeline
          latest={runStore.latestRound}
          scrub={runStore.scrubRound}
          playing={runStore.playing}
          speed={runStore.playbackSpeed}
          events={runStore.events}
          onScrub={(r) => useRunStore.getState().setScrub(r)}
          onPlay={(p) => useRunStore.getState().setPlaying(p)}
          onSpeed={(s) => useRunStore.getState().setPlaybackSpeed(s)}
        />
      </div>
    </div>
  );
}

export default function RunPage() {
  return (
    <Suspense fallback={
      <div className="flex h-[70vh] items-center justify-center gap-3 text-muted-fg">
        <Loader2 className="h-5 w-5 animate-spin text-hive-amber" /> loading…
      </div>
    }>
      <MissionControl />
    </Suspense>
  );
}
