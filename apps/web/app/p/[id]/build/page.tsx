"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, Play, RefreshCw } from "lucide-react";
import { apiFetch, apiPost } from "@/lib/api";
import type { Persona, Project } from "@/lib/types";

function stanceChip(s: number) {
  const label = s > 0.15 ? "supportive" : s < -0.15 ? "opposed" : "neutral";
  const cls = s > 0.15 ? "bg-hive-green/15 text-hive-green" : s < -0.15 ? "bg-hive-rose/15 text-hive-rose" : "bg-hive-cyan/10 text-hive-cyan";
  return <span className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide ${cls}`}>{label}</span>;
}

export default function BuildPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [stage, setStage] = useState<string>("preparing");
  const [error, setError] = useState<string | null>(null);
  const [rounds, setRounds] = useState(30);
  const [speed, setSpeed] = useState(1.5);
  const [starting, setStarting] = useState(false);
  const building = useRef(false);

  const build = useCallback(async () => {
    if (building.current) return;
    building.current = true;
    setError(null); setStage("extracting knowledge graph");
    try {
      const params = JSON.parse(sessionStorage.getItem(`hm-build-${id}`) || "{}");
      setStage("spawning personas");
      await apiPost(`/projects/${id}/build`, {
        agentCount: params.agentCount ?? 80,
        platformCount: params.platformCount ?? 2,
        seed: params.seed ?? 42,
      });
      setStage("world ready");
      setProject(await apiFetch<Project>(`/projects/${id}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "build failed");
    } finally {
      building.current = false;
    }
  }, [id]);

  useEffect(() => {
    (async () => {
      try {
        const p = await apiFetch<Project>(`/projects/${id}`);
        if (p.status === "built" || p.status === "simulating" || p.status === "complete") {
          setProject(p); setStage("world ready");
        } else {
          await build();
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to load project");
      }
    })();
  }, [id, build]);

  async function startSimulation() {
    setStarting(true); setError(null);
    try {
      const res = await apiPost<{ runId: string }>(`/projects/${id}/simulate`, { rounds, speed, seed: 42 });
      router.push(`/p/${id}/run?run=${res.runId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "could not start simulation");
      setStarting(false);
    }
  }

  const personas: Persona[] = project?.personas ?? [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mono text-[11px] uppercase tracking-widest text-muted-fg">world build</div>
          <h1 className="mt-1 text-2xl font-semibold">{project?.name ?? "…"}</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-fg">“{project?.question ?? ""}”</p>
        </div>
        <div className="mono rounded-full border border-border bg-surface px-3 py-1 text-[11px] uppercase tracking-widest text-hive-cyan">
          {stage}
        </div>
      </div>

      {error && (
        <div className="glass-panel mt-6 flex items-center gap-3 border-hive-rose/40 p-4 text-sm text-hive-rose">
          {error}
          <button onClick={build} className="ml-auto inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-foreground hover:bg-surface-2">
            <RefreshCw className="h-3.5 w-3.5" /> retry
          </button>
        </div>
      )}

      {!project ? (
        <div className="glass-panel mt-8 p-10">
          <div className="flex items-center gap-3 text-muted-fg">
            <Loader2 className="h-5 w-5 animate-spin text-hive-amber" />
            {stage === "preparing" ? "Loading project…" : "HIVE MIND is building your world — extracting entities, wiring relationships, spawning personas…"}
          </div>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded-lg bg-surface-2/70" style={{ animationDelay: `${i * 150}ms` }} />
            ))}
          </div>
        </div>
      ) : (
        <>
          <div className="mt-8 grid gap-4 sm:grid-cols-4">
            {[
              ["agents", project.agentCount],
              ["graph nodes", project.graphSummary?.nodes ?? 0],
              ["graph edges", project.graphSummary?.edges ?? 0],
              ["communities", project.graphSummary?.communities ?? 0],
            ].map(([k, v], i) => (
              <motion.div key={String(k)} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }} className="glass-panel p-5">
                <div className="mono text-[10px] uppercase tracking-widest text-muted-fg">{k}</div>
                <div className="mono mt-2 text-3xl font-semibold text-hive-amber">{v}</div>
              </motion.div>
            ))}
          </div>

          <div className="glass-panel mt-8 p-6">
            <h2 className="font-semibold">Persona roster</h2>
            <p className="mt-1 text-sm text-muted-fg">Each agent carries its own stance, goals and memory into the swarm.</p>
            <div className="mt-4 grid max-h-80 gap-2 overflow-y-auto pr-1 sm:grid-cols-2 lg:grid-cols-3">
              {personas.map((p) => (
                <div key={p.id} className="rounded-lg border border-border bg-surface p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">{p.name}</span>
                    {stanceChip(p.stance)}
                  </div>
                  <div className="mono mt-1 truncate text-[11px] text-muted-fg">{p.archetype} · {p.platform}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="glass-panel mt-8 flex flex-wrap items-end gap-6 p-6">
            <div className="min-w-48 flex-1">
              <label className="mono text-[11px] uppercase tracking-widest text-muted-fg">
                rounds — <span className="text-hive-amber">{rounds}</span>
              </label>
              <input type="range" min={5} max={200} step={5} value={rounds} onChange={(e) => setRounds(Number(e.target.value))}
                className="mt-2 w-full accent-[hsl(var(--hive-amber))]" />
            </div>
            <div className="min-w-48 flex-1">
              <label className="mono text-[11px] uppercase tracking-widest text-muted-fg">
                speed — <span className="text-hive-cyan">{speed.toFixed(1)} rounds/s</span>
              </label>
              <input type="range" min={0.5} max={20} step={0.5} value={speed} onChange={(e) => setSpeed(Number(e.target.value))}
                className="mt-2 w-full accent-[hsl(var(--hive-cyan))]" />
            </div>
            <button onClick={startSimulation} disabled={starting}
              className="inline-flex items-center gap-2 rounded-lg bg-hive-amber px-6 py-3 text-sm font-semibold text-black transition-transform hover:scale-[1.03] disabled:opacity-60">
              {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              start simulation
            </button>
          </div>
        </>
      )}
    </div>
  );
}
