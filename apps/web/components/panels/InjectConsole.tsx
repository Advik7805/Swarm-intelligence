"use client";

import { useState } from "react";
import { Eye, Loader2, Send } from "lucide-react";
import { apiPost } from "@/lib/api";

const QUICK = [
  "A leaked memo contradicts the official statement",
  "Regulators approve the product unconditionally",
  "A rival announces a breakthrough partnership",
];

export default function InjectConsole({ runId, live }: { runId: string; live: boolean }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function inject(payload: string) {
    if (!payload.trim()) return;
    setBusy(true); setError(null);
    try {
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
      </div>
      <div className="flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && live && inject(text)}
          disabled={!live}
          placeholder={live ? "Inject an event into the world…" : "Run finished — replay mode"}
          className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none placeholder:text-muted-fg/60 focus:border-hive-amber/60 focus:ring-2 focus:ring-hive-amber/20 disabled:opacity-50"
        />
        <button
          onClick={() => inject(text)}
          disabled={!live || busy || !text.trim()}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-hive-amber px-3 py-2 text-sm font-semibold text-black transition-transform hover:scale-[1.03] disabled:opacity-40 disabled:hover:scale-100"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          inject
        </button>
      </div>
      {live && (
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
