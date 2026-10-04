"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Hexagon, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { Project } from "@/lib/types";

const STATUS_STYLE: Record<Project["status"], string> = {
  created: "text-muted-fg", building: "text-hive-cyan", built: "text-hive-violet",
  simulating: "text-hive-amber", complete: "text-hive-green", failed: "text-hive-rose",
};

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Project[]>("/projects")
      .then(setProjects)
      .catch((e) => setError(e instanceof Error ? e.message : "failed to load"));
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">Projects</h1>
      <p className="mt-2 text-sm text-muted-fg">Every simulation you have launched, persisted locally.</p>

      {error && <p className="mt-6 text-sm text-hive-rose">{error}</p>}
      {!projects && !error && (
        <div className="mt-16 flex items-center justify-center gap-2 text-muted-fg">
          <Loader2 className="h-5 w-5 animate-spin" /> loading hive…
        </div>
      )}
      {projects?.length === 0 && (
        <div className="glass-panel mt-10 p-10 text-center text-muted-fg">
          <Hexagon className="mx-auto h-10 w-10 text-hive-amber/60" />
          <p className="mt-4">No simulations yet. The hive is waiting for its first question.</p>
          <Link href="/new" className="mt-4 inline-flex items-center gap-2 rounded-lg bg-hive-amber px-5 py-2.5 text-sm font-semibold text-black">
            Launch a simulation <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      )}
      <div className="mt-8 grid gap-4 md:grid-cols-2">
        {projects?.map((p, i) => (
          <motion.div key={p.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05, duration: 0.35 }}>
            <Link
              href={p.currentRunId ? `/p/${p.id}/run` : p.status === "built" ? `/p/${p.id}/build` : `/p/${p.id}/build`}
              className="glass-panel block p-5 transition-transform hover:-translate-y-0.5"
            >
              <div className="flex items-center justify-between gap-4">
                <h3 className="truncate font-semibold">{p.name}</h3>
                <span className={`mono shrink-0 text-[10px] uppercase tracking-widest ${STATUS_STYLE[p.status]}`}>
                  {p.status}
                </span>
              </div>
              <p className="mt-2 line-clamp-2 text-sm text-muted-fg">“{p.question}”</p>
              <div className="mono mt-4 flex gap-4 text-[11px] text-muted-fg">
                <span>{p.agentCount} agents</span>
                <span>{new Date(p.createdAt * 1000).toLocaleString()}</span>
              </div>
            </Link>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
