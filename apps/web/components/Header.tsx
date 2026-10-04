"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Hexagon, FolderOpen, Rocket } from "lucide-react";
import { apiFetch } from "@/lib/api";

export default function Header() {
  const [llm, setLlm] = useState<string | null>(null);
  useEffect(() => {
    apiFetch<{ llm: string }>("/health")
      .then((h) => setLlm(h.llm))
      .catch(() => setLlm(null));
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="relative grid h-8 w-8 place-items-center rounded-lg bg-hive-amber/15 text-hive-amber">
            <Hexagon className="h-5 w-5" strokeWidth={2.2} />
            <span className="absolute h-1.5 w-1.5 rounded-full bg-hive-amber" />
          </span>
          HIVE&nbsp;MIND
        </Link>
        <nav className="hidden items-center gap-1 text-sm text-muted-fg sm:flex">
          <Link href="/projects" className="rounded-md px-3 py-1.5 transition-colors hover:bg-surface-2 hover:text-foreground">
            <span className="inline-flex items-center gap-1.5"><FolderOpen className="h-3.5 w-3.5" /> Projects</span>
          </Link>
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <span
            className="mono hidden items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-[11px] uppercase tracking-wider text-muted-fg sm:inline-flex"
            title="LLM operating mode reported by the backend"
          >
            <span className={`status-dot h-1.5 w-1.5 rounded-full ${llm === "live" ? "bg-hive-green" : llm === "demo" ? "bg-hive-amber" : "bg-hive-rose"}`} />
            {llm ? `${llm} mode` : "api offline"}
          </span>
          <Link
            href="/new"
            className="inline-flex items-center gap-2 rounded-lg bg-hive-amber px-4 py-2 text-sm font-semibold text-black transition-transform hover:scale-[1.03] active:scale-[0.98]"
          >
            <Rocket className="h-4 w-4" /> Launch a simulation
          </Link>
        </div>
      </div>
    </header>
  );
}
