"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft, Loader2, Quote, Rotate3d } from "lucide-react";
import { apiFetch, apiPost } from "@/lib/api";
import type { Project, Report, RunStatus } from "@/lib/types";
import ChatBox from "@/components/panels/ChatBox";
import { FACTION_COLORS } from "@/components/three/SwarmCanvas";

function ConfidenceRing({ value }: { value: number }) {
  const r = 34, c = 2 * Math.PI * r;
  return (
    <div className="relative h-24 w-24">
      <svg viewBox="0 0 84 84" className="h-24 w-24 -rotate-90">
        <circle cx="42" cy="42" r={r} fill="none" stroke="hsl(224 18% 20%)" strokeWidth="7" />
        <circle cx="42" cy="42" r={r} fill="none" stroke="#ffab00" strokeWidth="7"
          strokeLinecap="round" strokeDasharray={`${c * value} ${c}`} />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        <span className="mono text-lg font-semibold">{Math.round(value * 100)}%</span>
      </div>
    </div>
  );
}

function ReportView() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [runId, setRunId] = useState<string | null>(search.get("run"));
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stage, setStage] = useState("locating run");

  useEffect(() => {
    (async () => {
      try {
        const p = await apiFetch<Project>(`/projects/${id}`);
        setProject(p);
        const rid = runId ?? p.currentRunId;
        if (!rid) { router.replace(`/p/${id}/build`); return; }
        setRunId(rid);
        setStage("generating report");
        try {
          const existing = await apiFetch<Report>(`/runs/${rid}/report`);
          setReport(existing);
          return;
        } catch { /* not generated yet */ }
        try {
          const status = await apiFetch<RunStatus>(`/runs/${rid}`);
          if (status.round < 1) { setError("The run needs at least one completed round before a report can be generated."); return; }
          const fresh = await apiPost<Report>(`/runs/${rid}/report`);
          setReport(fresh);
        } catch (e2) {
          setError(e2 instanceof Error ? e2.message : "report failed");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to load");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (error) {
    return (
      <div className="mx-auto max-w-xl px-4 py-24 text-center">
        <p className="text-hive-rose">{error}</p>
        <Link href={`/p/${id}/run${runId ? `?run=${runId}` : ""}`} className="mt-4 inline-flex items-center gap-2 text-sm text-hive-cyan hover:underline">
          <ArrowLeft className="h-4 w-4" /> back to mission control
        </Link>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex h-[70vh] flex-col items-center justify-center gap-3 text-muted-fg">
        <Loader2 className="h-6 w-6 animate-spin text-hive-amber" />
        <span className="mono text-xs uppercase tracking-widest">{stage} — the ReportAgent is reading the swarm&rsquo;s transcript…</span>
      </div>
    );
  }

  const meta = report.meta;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <Link href={`/p/${id}/run${runId ? `?run=${runId}` : ""}`}
        className="mono inline-flex items-center gap-2 text-[11px] uppercase tracking-widest text-muted-fg transition-colors hover:text-foreground">
        <ArrowLeft className="h-3.5 w-3.5" /> mission control
      </Link>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-6">
        <div className="max-w-2xl">
          <div className="mono text-[11px] uppercase tracking-widest text-hive-amber">prediction report</div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">{project?.name}</h1>
          <p className="mt-2 text-muted-fg">“{project?.question}”</p>
          <div className="mono mt-4 flex flex-wrap gap-2 text-[10px] uppercase tracking-wider text-muted-fg">
            <span className="rounded-full border border-border bg-surface px-2.5 py-1">{meta.agents} agents</span>
            <span className="rounded-full border border-border bg-surface px-2.5 py-1">{meta.rounds} rounds</span>
            <span className="rounded-full border border-border bg-surface px-2.5 py-1">{meta.actions} actions</span>
            <span className="rounded-full border border-border bg-surface px-2.5 py-1">{meta.mode} swarm</span>
            <span className="rounded-full border border-border bg-surface px-2.5 py-1">final sentiment {meta.finalSentiment >= 0 ? "+" : ""}{meta.finalSentiment}</span>
            <span className="rounded-full border border-border bg-surface px-2.5 py-1">polarization {meta.polarization}</span>
          </div>
        </div>
        <div className="glass-panel flex items-center gap-4 p-4">
          <ConfidenceRing value={report.confidence} />
          <div>
            <div className="mono text-[10px] uppercase tracking-widest text-muted-fg">confidence</div>
            <div className="mt-1 max-w-40 text-xs leading-relaxed text-muted-fg">
              derived from agreement, drift and polarization across the swarm
            </div>
          </div>
        </div>
      </div>

      <div className="mt-10 grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          <motion.section initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="glass-panel p-6">
            <h2 className="mono text-[11px] uppercase tracking-widest text-muted-fg">executive summary</h2>
            <p className="mt-3 leading-relaxed">{report.summary}</p>
            <div className="mt-4 rounded-lg border border-hive-amber/30 bg-hive-amber/5 p-4">
              <div className="mono text-[10px] uppercase tracking-widest text-hive-amber">overall prediction</div>
              <p className="mt-2 leading-relaxed">{report.overallPrediction}</p>
            </div>
          </motion.section>

          <motion.section initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }} className="glass-panel p-6">
            <h2 className="mono text-[11px] uppercase tracking-widest text-muted-fg">key findings</h2>
            <div className="mt-4 space-y-4">
              {report.keyFindings.map((f, i) => (
                <div key={i} className="rounded-lg border border-border bg-surface p-4">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm leading-relaxed">{f.claim}</p>
                    <span className="mono shrink-0 rounded-full bg-hive-cyan/10 px-2 py-0.5 text-[10px] text-hive-cyan">
                      {(f.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  {f.evidence?.length > 0 && (
                    <div className="mt-3 space-y-2 border-l-2 border-border pl-3">
                      {f.evidence.map((e, j) => (
                        <div key={j} className="flex gap-2 text-xs text-muted-fg">
                          <Quote className="mt-0.5 h-3 w-3 shrink-0 text-hive-violet" />
                          <span>
                            “{e.quote}”
                            <span className="mono ml-1.5 text-[10px] text-muted-fg/70">
                              — {e.agent ?? e.agentId}, round {e.round}
                            </span>
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </motion.section>

          <motion.section initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.14 }} className="glass-panel p-6">
            <h2 className="mono text-[11px] uppercase tracking-widest text-muted-fg">scenario branches</h2>
            <div className="mt-4 space-y-3">
              {report.scenarioBranches.map((b, i) => (
                <div key={i} className="rounded-lg border border-border bg-surface p-4">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-medium">{b.name}</span>
                    <span className="mono text-hive-amber">{(b.probability * 100).toFixed(0)}%</span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-2">
                    <div className="h-full rounded-full bg-gradient-to-r from-hive-amber to-hive-cyan" style={{ width: `${b.probability * 100}%` }} />
                  </div>
                  <p className="mono mt-2 text-[11px] uppercase tracking-wide text-muted-fg">trigger: {b.trigger}</p>
                  <p className="mt-1 text-sm text-muted-fg">{b.outcome}</p>
                </div>
              ))}
            </div>
          </motion.section>
        </div>

        <div className="space-y-6">
          <section className="glass-panel p-5">
            <h2 className="mono text-[11px] uppercase tracking-widest text-muted-fg">top agents by reach</h2>
            <ul className="mt-3 space-y-2">
              {report.topAgents.map((a, i) => (
                <li key={a.id} className="flex items-center gap-2.5 text-sm">
                  <span className="mono w-4 text-[10px] text-muted-fg">{i + 1}</span>
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: FACTION_COLORS[a.faction % FACTION_COLORS.length] }} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">{a.name}</span>
                    <span className="mono block text-[10px] uppercase tracking-wide text-muted-fg">{a.archetype}</span>
                  </span>
                  <span className="mono text-[11px] text-hive-amber">{a.score.toFixed(0)}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="glass-panel p-5">
            <h2 className="mono flex items-center gap-2 text-[11px] uppercase tracking-widest text-muted-fg">
              <Rotate3d className="h-3.5 w-3.5 text-hive-violet" /> suggested interventions
            </h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {report.injectableSuggestions.map((s, i) => (
                <span key={i} className="rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted-fg">{s}</span>
              ))}
            </div>
          </section>

          <section className="glass-panel flex h-96 flex-col p-5">
            <h2 className="mono mb-3 text-[11px] uppercase tracking-widest text-muted-fg">ask the report agent</h2>
            {runId && (
              <ChatBox
                endpoint={`/runs/${runId}/chat/report`}
                placeholder="e.g. What's most likely to flip the swarm?"
                emptyHint="Ask anything about the findings — risks, evidence, scenarios. Answers are grounded in this report and the run's event log."
              />
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

export default function ReportPage() {
  return (
    <Suspense fallback={
      <div className="flex h-[70vh] items-center justify-center gap-3 text-muted-fg">
        <Loader2 className="h-5 w-5 animate-spin text-hive-amber" /> loading…
      </div>
    }>
      <ReportView />
    </Suspense>
  );
}
