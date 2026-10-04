"use client";

import { Area, AreaChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import Panel from "./Panel";
import type { MetricsEvent } from "@/lib/types";

export default function SentimentChart({ series }: { series: MetricsEvent[] }) {
  return (
    <Panel title="swarm sentiment">
      <div className="h-28">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={series} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="sentGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2fe6ff" stopOpacity={0.6} />
                <stop offset="100%" stopColor="#2fe6ff" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <XAxis dataKey="round" hide />
            <YAxis domain={[-1, 1]} hide />
            <ReferenceLine y={0} stroke="hsl(224 18% 20%)" />
            <Tooltip
              contentStyle={{ background: "hsl(228 28% 8%)", border: "1px solid hsl(224 18% 20%)", borderRadius: 8, fontSize: 12 }}
              labelFormatter={(r) => `round ${r}`}
              formatter={(v) => [Number(v).toFixed(3), "sentiment"]}
            />
            <Area type="monotone" dataKey="sentimentAvg" stroke="#2fe6ff" strokeWidth={1.6} fill="url(#sentGrad)" isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="mono mt-1 flex justify-between text-[10px] text-muted-fg">
        <span>-1 opposed</span>
        <span>{series.length ? `now ${series[series.length - 1].sentimentAvg.toFixed(2)}` : "—"}</span>
        <span>+1 supportive</span>
      </div>
    </Panel>
  );
}
