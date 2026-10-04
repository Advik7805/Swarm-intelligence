"use client";

import { useState } from "react";
import { Loader2, Send } from "lucide-react";
import { apiPost } from "@/lib/api";

interface Msg { role: "user" | "assistant"; content: string }

export default function ChatBox({ endpoint, placeholder, emptyHint }: {
  endpoint: string; placeholder: string; emptyHint: string;
}) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    const message = input.trim();
    if (!message || busy) return;
    setInput(""); setBusy(true); setError(null);
    setMessages((m) => [...m, { role: "user", content: message }]);
    try {
      const res = await apiPost<{ reply: string }>(endpoint, { message });
      setMessages((m) => [...m, { role: "assistant", content: res.reply }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "chat failed");
      setMessages((m) => m.slice(0, -1));
      setInput(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
        {messages.length === 0 && <p className="text-xs leading-relaxed text-muted-fg">{emptyHint}</p>}
        {messages.map((m, i) => (
          <div key={i} className={`max-w-[92%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
            m.role === "user" ? "ml-auto bg-hive-amber/15 text-foreground" : "bg-surface-2 text-muted-fg"
          }`}>
            {m.content}
          </div>
        ))}
        {busy && (
          <div className="flex items-center gap-2 text-xs text-muted-fg">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> thinking…
          </div>
        )}
        {error && <p className="text-xs text-hive-rose">{error}</p>}
      </div>
      <div className="mt-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={placeholder}
          className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none placeholder:text-muted-fg/60 focus:border-hive-cyan/60 focus:ring-2 focus:ring-hive-cyan/20"
        />
        <button onClick={send} disabled={busy || !input.trim()} aria-label="send message"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-hive-cyan text-black transition-transform hover:scale-105 disabled:opacity-40">
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
