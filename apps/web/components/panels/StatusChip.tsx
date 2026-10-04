"use client";

const MAP: Record<string, { label: string; cls: string; dot: string }> = {
  loading: { label: "CONNECTING", cls: "text-muted-fg", dot: "bg-muted-fg" },
  queued: { label: "QUEUED", cls: "text-muted-fg", dot: "bg-muted-fg" },
  running: { label: "SIMULATING", cls: "text-hive-amber", dot: "bg-hive-amber" },
  paused: { label: "PAUSED", cls: "text-hive-cyan", dot: "bg-hive-cyan" },
  stopped: { label: "STOPPED", cls: "text-hive-rose", dot: "bg-hive-rose" },
  reporting: { label: "REPORTING", cls: "text-hive-violet", dot: "bg-hive-violet" },
  complete: { label: "COMPLETE", cls: "text-hive-green", dot: "bg-hive-green" },
  failed: { label: "FAILED", cls: "text-hive-rose", dot: "bg-hive-rose" },
};

export default function StatusChip({ status, wsState }: { status: string; wsState: string }) {
  const s = MAP[status] ?? MAP.loading;
  return (
    <span className={`mono inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-[11px] uppercase tracking-wider ${s.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot} ${status === "running" ? "status-dot" : ""}`} />
      {s.label}
      {wsState !== "open" && status === "running" && (
        <span className="text-muted-fg">· ws {wsState}</span>
      )}
    </span>
  );
}
