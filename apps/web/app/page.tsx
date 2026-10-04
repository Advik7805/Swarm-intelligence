"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import {
  Boxes, Eye, GitBranch, MessagesSquare, Radar, Rocket,
  Server, Timer, Users, Workflow,
} from "lucide-react";

const BoidsHero = dynamic(() => import("@/components/three/BoidsHero"), { ssr: false });

const fade = {
  initial: { opacity: 0, y: 18 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.55, ease: "easeOut" as const },
};

const STEPS = [
  { icon: GitBranch, title: "Ingest the seed", text: "Drop in PDFs, reports, articles or plain text — plus your prediction question." },
  { icon: Workflow, title: "Build the world", text: "Entities and relations are extracted into a live knowledge graph (GraphRAG)." },
  { icon: Users, title: "Spawn the swarm", text: "Hundreds of agents get distinct personas, stances, goals and memory." },
  { icon: Radar, title: "Run the simulation", text: "Agents interact round by round. Inject God\u2019s-eye events and watch ripples." },
  { icon: Boxes, title: "Read the report", text: "The ReportAgent turns the transcript into a structured prediction with evidence." },
];

const FEATURES = [
  { icon: Boxes, title: "3-D swarm world", text: "Every agent is a light in a living graph. Interactions draw visible links; factions color the sky." },
  { icon: Eye, title: "God\u2019s-eye control", text: "Inject rumors, rulings, launches — mid-run — and watch sentiment waves propagate." },
  { icon: Timer, title: "Timeline replay", text: "Scrub any round. The full event log replays locally with zero extra LLM calls." },
  { icon: MessagesSquare, title: "Chat the hive", text: "Talk 1:1 with any agent — it answers in character from its own memory of the run." },
  { icon: Server, title: "No lock-in", text: "Any OpenAI-compatible model, local Ollama, or a fully offline deterministic demo mode." },
  { icon: Rocket, title: "Deploy anywhere", text: "One docker-compose, or Vercel + Render. SQLite persistence, nothing heavy to run." },
];

export default function LandingPage() {
  return (
    <div className="relative overflow-hidden">
      {/* ── hero ─────────────────────────────────────────── */}
      <section className="relative flex min-h-[calc(100vh-3.5rem)] items-center">
        <BoidsHero />
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_35%,hsl(var(--background))_82%)]" />
        <div className="relative mx-auto w-full max-w-7xl px-4 py-24">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: "easeOut" }}
            className="max-w-3xl"
          >
            <div className="mono mb-5 inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-muted-fg backdrop-blur">
              <span className="status-dot h-1.5 w-1.5 rounded-full bg-hive-amber" />
              swarm intelligence prediction engine
            </div>
            <h1 className="text-5xl font-bold leading-[1.05] tracking-tight sm:text-7xl">
              Rehearse the future in a{" "}
              <span className="bg-gradient-to-r from-hive-amber via-hive-cyan to-hive-violet bg-clip-text text-transparent">
                living swarm
              </span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-fg">
              HIVE MIND builds a parallel digital world from your seed material — hundreds of
              agents with memory, goals and opinions — then lets it run. Watch emergent
              consensus, polarization and shocks play out in 3-D, and read the prediction
              report before reality writes it.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Link
                href="/new"
                className="inline-flex items-center gap-2 rounded-lg bg-hive-amber px-6 py-3 text-base font-semibold text-black transition-transform hover:scale-[1.03] active:scale-[0.98]"
              >
                <Rocket className="h-5 w-5" /> Launch a simulation
              </Link>
              <Link
                href="/projects"
                className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface/70 px-6 py-3 text-base font-medium text-foreground backdrop-blur transition-colors hover:bg-surface-2"
              >
                Browse projects
              </Link>
            </div>
            <p className="mono mt-6 text-xs uppercase tracking-wider text-muted-fg">
              runs fully offline in demo mode · no api key required
            </p>
          </motion.div>
        </div>
      </section>

      {/* ── pipeline ─────────────────────────────────────── */}
      <section className="relative mx-auto max-w-7xl px-4 py-24">
        <motion.h2 {...fade} className="text-3xl font-semibold tracking-tight">
          From seed to signal
        </motion.h2>
        <motion.p {...fade} className="mt-3 max-w-2xl text-muted-fg">
          Five stages, fully automated. You bring the question — the hive does the rest.
        </motion.p>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map((s, i) => (
            <motion.div key={s.title} {...fade} transition={{ ...fade.transition, delay: i * 0.07 }}
              className="glass-panel group p-5 transition-transform hover:-translate-y-1">
              <s.icon className="h-6 w-6 text-hive-amber transition-colors group-hover:text-hive-cyan" />
              <div className="mono mt-3 text-[10px] uppercase tracking-widest text-muted-fg">step {i + 1}</div>
              <h3 className="mt-1 font-semibold">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-fg">{s.text}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ── features ─────────────────────────────────────── */}
      <section className="relative mx-auto max-w-7xl px-4 pb-28">
        <motion.h2 {...fade} className="text-3xl font-semibold tracking-tight">
          A mission control for collective behavior
        </motion.h2>
        <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <motion.div key={f.title} {...fade} transition={{ ...fade.transition, delay: i * 0.06 }}
              className="glass-panel p-6">
              <f.icon className="h-6 w-6 text-hive-cyan" />
              <h3 className="mt-3 font-semibold">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-fg">{f.text}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ── CTA band ─────────────────────────────────────── */}
      <section className="border-t border-border/60 bg-surface/40">
        <motion.div {...fade} className="mx-auto flex max-w-7xl flex-col items-center gap-6 px-4 py-20 text-center">
          <h2 className="text-3xl font-semibold tracking-tight">
            Give the swarm a question.
          </h2>
          <Link
            href="/new"
            className="inline-flex items-center gap-2 rounded-lg bg-hive-amber px-7 py-3 text-base font-semibold text-black transition-transform hover:scale-[1.03] active:scale-[0.98]"
          >
            <Rocket className="h-5 w-5" /> Start now
          </Link>
        </motion.div>
      </section>
    </div>
  );
}
