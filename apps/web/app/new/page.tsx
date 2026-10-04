"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, ArrowRight, FileUp, Loader2, Rocket, X } from "lucide-react";
import { apiPost, fileToPayload } from "@/lib/api";

const SAMPLE = `Tech giant Meridian Dynamics announced 'Aurora', a consumer AI chip claiming 10x efficiency. Within hours, regulators in three countries opened reviews, labor unions warned of supply-chain job displacement, and two rival firms hinted at competing launches next quarter. Analysts are split: some call it a watershed moment for edge computing, others see classic overpromising. Social channels are flooded with demos, skepticism, and memes.`;

interface FilePayload { name: string; contentBase64: string }

export default function NewSimulationPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [question, setQuestion] = useState("How will public sentiment evolve over the next two weeks?");
  const [seedText, setSeedText] = useState("");
  const [files, setFiles] = useState<FilePayload[]>([]);
  const [agentCount, setAgentCount] = useState(80);
  const [platformCount, setPlatformCount] = useState(2);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canNext = step === 0 ? seedText.trim().length > 20 || files.length > 0
    : step === 1 ? name.trim().length > 1 && question.trim().length > 5 : true;

  async function addFiles(list: FileList | null) {
    if (!list) return;
    const next: FilePayload[] = [];
    for (const f of Array.from(list).slice(0, 6)) {
      if (f.size > 6 * 1024 * 1024) { setError(`${f.name} is over 6MB — skipped`); continue; }
      try { next.push(await fileToPayload(f)); } catch { /* ignore */ }
    }
    setFiles((prev) => [...prev, ...next].slice(0, 8));
  }

  async function submit() {
    setBusy(true); setError(null);
    try {
      const res = await apiPost<{ id: string }>("/projects", {
        name: name.trim(), question: question.trim(), seedText: seedText.trim(), files,
      });
      sessionStorage.setItem(`hm-build-${res.id}`,
        JSON.stringify({ agentCount, platformCount, seed: 42 }));
      router.push(`/p/${res.id}/build`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to create project");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <div className="mono mb-8 flex items-center gap-3 text-[11px] uppercase tracking-widest text-muted-fg">
        {["seed", "question", "world"].map((s, i) => (
          <span key={s} className="flex items-center gap-3">
            <span className={i === step ? "text-hive-amber" : i < step ? "text-hive-green" : ""}>
              {String(i + 1).padStart(2, "0")} · {s}
            </span>
            {i < 2 && <span className="h-px w-8 bg-border" />}
          </span>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -24 }} transition={{ duration: 0.25, ease: "easeOut" }}
          className="glass-panel p-8"
        >
          {step === 0 && (
            <>
              <h1 className="text-2xl font-semibold">Feed the seed</h1>
              <p className="mt-2 text-sm text-muted-fg">
                Paste the material the simulation should be grounded in — a dossier, article,
                policy draft, research notes — or upload files (PDF/TXT/MD).
              </p>
              <textarea
                value={seedText} onChange={(e) => setSeedText(e.target.value)}
                rows={9} placeholder="Paste seed material here…"
                className="mt-5 w-full resize-y rounded-lg border border-border bg-surface p-4 text-sm leading-relaxed outline-none focus:border-hive-amber/60 focus:ring-2 focus:ring-hive-amber/20"
              />
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-border bg-surface px-4 py-2 text-sm text-muted-fg transition-colors hover:border-hive-cyan/60 hover:text-foreground">
                  <FileUp className="h-4 w-4" /> Add files
                  <input type="file" multiple accept=".pdf,.txt,.md,.csv,.json,.log" className="hidden"
                    onChange={(e) => addFiles(e.target.files)} />
                </label>
                <button type="button" onClick={() => setSeedText(SAMPLE)}
                  className="text-sm text-hive-cyan underline-offset-4 hover:underline">
                  use a sample seed
                </button>
                {files.map((f) => (
                  <span key={f.name} className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2 px-3 py-1 text-xs">
                    {f.name}
                    <button type="button" aria-label={`remove ${f.name}`}
                      onClick={() => setFiles((p) => p.filter((x) => x.name !== f.name))}>
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <h1 className="text-2xl font-semibold">Ask the question</h1>
              <p className="mt-2 text-sm text-muted-fg">Name the run and state what you want predicted.</p>
              <label className="mono mt-6 block text-[11px] uppercase tracking-widest text-muted-fg">project name</label>
              <input value={name} onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Aurora chip — public sentiment"
                className="mt-2 w-full rounded-lg border border-border bg-surface px-4 py-3 text-sm outline-none focus:border-hive-amber/60 focus:ring-2 focus:ring-hive-amber/20" />
              <label className="mono mt-5 block text-[11px] uppercase tracking-widest text-muted-fg">prediction question</label>
              <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={3}
                className="mt-2 w-full resize-none rounded-lg border border-border bg-surface px-4 py-3 text-sm outline-none focus:border-hive-amber/60 focus:ring-2 focus:ring-hive-amber/20" />
            </>
          )}

          {step === 2 && (
            <>
              <h1 className="text-2xl font-semibold">Shape the world</h1>
              <p className="mt-2 text-sm text-muted-fg">Swarm size and arena layout. You can re-run with different parameters later.</p>
              <label className="mono mt-6 block text-[11px] uppercase tracking-widest text-muted-fg">
                agents — <span className="text-hive-amber">{agentCount}</span>
              </label>
              <input type="range" min={10} max={500} step={10} value={agentCount}
                onChange={(e) => setAgentCount(Number(e.target.value))}
                className="mt-2 w-full accent-[hsl(var(--hive-amber))]" />
              <label className="mono mt-6 block text-[11px] uppercase tracking-widest text-muted-fg">platforms</label>
              <div className="mt-2 flex gap-2">
                {[1, 2].map((n) => (
                  <button key={n} type="button" onClick={() => setPlatformCount(n)}
                    className={`rounded-lg border px-4 py-2 text-sm transition-colors ${platformCount === n ? "border-hive-amber/70 bg-hive-amber/10 text-hive-amber" : "border-border bg-surface text-muted-fg hover:text-foreground"}`}>
                    {n === 1 ? "Single arena" : "Dual arenas (A / B)"}
                  </button>
                ))}
              </div>
              <div className="mt-6 rounded-lg border border-border bg-surface p-4 text-sm text-muted-fg">
                Next: HIVE MIND extracts the knowledge graph and spawns personas. Then you set
                rounds & speed and the swarm goes live.
              </div>
            </>
          )}

          {error && <p className="mt-4 text-sm text-hive-rose">{error}</p>}

          <div className="mt-8 flex items-center justify-between">
            <button type="button" disabled={step === 0 || busy} onClick={() => setStep((s) => s - 1)}
              className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-muted-fg transition-colors hover:text-foreground disabled:opacity-40">
              <ArrowLeft className="h-4 w-4" /> back
            </button>
            {step < 2 ? (
              <button type="button" disabled={!canNext} onClick={() => setStep((s) => s + 1)}
                className="inline-flex items-center gap-2 rounded-lg bg-hive-amber px-5 py-2.5 text-sm font-semibold text-black transition-transform hover:scale-[1.03] disabled:opacity-40 disabled:hover:scale-100">
                next <ArrowRight className="h-4 w-4" />
              </button>
            ) : (
              <button type="button" disabled={busy} onClick={submit}
                className="inline-flex items-center gap-2 rounded-lg bg-hive-amber px-5 py-2.5 text-sm font-semibold text-black transition-transform hover:scale-[1.03] disabled:opacity-60">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
                build the world
              </button>
            )}
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
