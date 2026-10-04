"use client";

import { Pause, Play, Radio } from "lucide-react";
import type { InjectedEvent } from "@/lib/types";

export default function Timeline({ latest, scrub, playing, speed, events, onScrub, onPlay, onSpeed }: {
  latest: number;
  scrub: number | null;
  playing: boolean;
  speed: number;
  events: InjectedEvent[];
  onScrub: (r: number | null) => void;
  onPlay: (p: boolean) => void;
  onSpeed: (s: number) => void;
}) {
  const value = scrub ?? latest;
  const max = Math.max(1, latest);
  return (
    <div className="glass-panel flex items-center gap-4 px-4 py-3">
      <button
        onClick={() => onPlay(!playing)}
        aria-label={playing ? "pause playback" : "resume playback"}
        className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-hive-amber text-black transition-transform hover:scale-105"
      >
        {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 translate-x-px" />}
      </button>

      <div className="relative min-w-0 flex-1">
        <div className="relative">
          <input
            type="range" min={1} max={max} step={1} value={Math.max(1, value)}
            onChange={(e) => { onScrub(Number(e.target.value)); onPlay(false); }}
            className="w-full accent-[hsl(var(--hive-amber))]"
            aria-label="timeline scrubber"
          />
          {events.map((ev, i) => (
            <span key={i}
              className="pointer-events-none absolute -top-1.5 h-2 w-2 rounded-full bg-hive-amber ring-2 ring-background"
              style={{ left: `calc(${((Math.max(1, ev.tick) - 1) / Math.max(1, max - 1)) * 100}% + 0px)` }}
              title={ev.text}
            />
          ))}
        </div>
        <div className="mono mt-1 flex justify-between text-[10px] text-muted-fg">
          <span>round {Math.max(1, value)} / {max}</span>
          <span>{scrub === null ? "following live" : "replay — no llm calls"}</span>
        </div>
      </div>

      <select
        value={speed}
        onChange={(e) => onSpeed(Number(e.target.value))}
        className="mono shrink-0 rounded-md border border-border bg-surface px-2 py-1.5 text-xs text-foreground"
        aria-label="playback speed"
      >
        {[0.5, 1, 2, 4, 8].map((s) => <option key={s} value={s}>{s}×</option>)}
      </select>

      {scrub !== null && (
        <button onClick={() => { onScrub(null); onPlay(true); }}
          className="mono inline-flex shrink-0 items-center gap-1.5 rounded-md border border-hive-amber/50 bg-hive-amber/10 px-3 py-1.5 text-[11px] uppercase tracking-wider text-hive-amber">
          <Radio className="h-3.5 w-3.5" /> live
        </button>
      )}
    </div>
  );
}
