"use client";

import { useState } from "react";
import { Eye, Loader2, Send } from "lucide-react";
import { apiPost } from "@/lib/api";

const QUICK = [
  "A leaked memo contradicts the official statement",
  "Regulators approve the product unconditionally",
  "A rival announces a breakthrough partnership",
];

const LIVE_STATES = new Set(["running", "paused", "queued"]);
const FINISHED_STATES = new Set(["complete", "stopped", "failed"]);

export default function InjectConsole({ runId, status }: { runId: string; status: string }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [extendRounds, setExtendRounds] = useState(20);
  const [error, setError] = useState<string | null>(null);

  const live = LIVE_STATES.has(status);
  const finished = FINISHED_STATES.has(status);
  const enabled = live || finished;

  async function inject(payload: string) {
    if (!payload.trim() || !enabled) return;
    setBusy(true); setError(null);
    try {
      if (finished) {
        // wake the engine back up with more rounds, then drop the shock in
        await apiPost(`/runs/${runId}/control`, { action: "resume", rounds: extendRounds });
        await new Promise((r) => setTimeout(r, 400));
      }
      await apiPost(`/runs/${runId}/control`, { action: "injectEvent", text: payload.trim() });
      setText("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "injection failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="glass-panel p-4">
      <div className="mono mb-2 flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-muted-fg">
        <Eye className="h-3.5 w-3.5 text-hive-amber" /> god&rsquo;s-eye console
        {finished && (
          <span className="ml-auto inline-flex items-center gap-1.5 text-[10px] normal-case tracking-normal">
            extend run by
            <select
              value={extendRounds}
              onChange={(e) => setExtendRounds(Number(e.target.value))}
              className="rounded border border-border bg-surface px-1.5 py-0.5 text-[11px] text-foreground"
              aria-label="extend run rounds"
            >
              {[10, 20, 40].map((n) => <option key={n} value={n}>+{n} rounds</option>)}
            </select>
          </span>
        )}
      </div>
      <div className="flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && inject(text)}
          disabled={!enabled}
          placeholder={
            live
              ? "Inject an event into the world…"
              : finished
                ? "Inject an event — the run continues with more rounds…"
                : "Waiting for the engine…"
          }
          className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none placeholder:text-muted-fg/60 focus:border-hive-amber/60 focus:ring-2 focus:ring-hive-amber/20 disabled:opacity-50"
        />
        <button
          onClick={() => inject(text)}
          disabled={!enabled || busy || !text.trim()}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-hive-amber px-3 py-2 text-sm font-semibold text-black transition-transform hover:scale-[1.03] disabled:opacity-40 disabled:hover:scale-100"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          {finished ? "inject & continue" : "inject"}
        </button>
      </div>
      {enabled && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {QUICK.map((q) => (
            <button key={q} onClick={() => inject(q)}
              className="rounded-full border border-border bg-surface px-2.5 py-1 text-[11px] text-muted-fg transition-colors hover:border-hive-amber/50 hover:text-foreground">
              {q}
            </button>
          ))}
        </div>
      )}
      {error && <p className="mt-2 text-xs text-hive-rose">{error}</p>}
    </div>
  );
}
