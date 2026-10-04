# 🧠 HIVE MIND — Swarm Intelligence Prediction Engine

**Simulate thousands of agents, inject shocks, watch consensus and polarization emerge in 3-D — then read the prediction report. Rehearse the future before reality writes it.**

HIVE MIND is a multi-agent swarm simulation platform. You upload a *seed* (reports,
articles, policy drafts — PDF/TXT/MD or pasted text) and a prediction question; it builds a
knowledge-graph world (GraphRAG), spawns agent personas with memory and stances, runs the
swarm in discrete rounds, and produces a structured prediction report with cited evidence.

Inspired by the concepts of MiroFish — **all code written from scratch, English-only**, and
enhanced with a real-time **3-D swarm world**, live WebSocket streaming, timeline replay,
God's-eye event injection, a swappable LLM layer, and a **fully-offline demo mode** (no API
key, no cloud services required).

## Features

| | |
|---|---|
| 🌐 **3-D swarm world** | Agents as glowing orbs in a force-directed 3-D graph; interactions draw visible links; factions recolor the swarm live |
| ⚡ **Real-time stream** | Every round streams over WebSockets; pause / resume / stop / change speed from mission control |
| 👁 **God's-eye console** | Inject events mid-run and watch the ripple — sentiment shock propagates through openness-weighted agents |
| ⏱ **Timeline replay** | Full event log persisted to SQLite — scrub any round with **zero** extra LLM calls |
| 🧾 **ReportAgent** | Executive summary, overall prediction, confidence, key findings with quoted evidence, scenario branches, top agents |
| 💬 **Deep interaction** | Chat 1:1 with any agent (answers in character from its run memory) or with the ReportAgent |
| 🔌 **Your model** | Any OpenAI-compatible API or local Ollama; falls back to a deterministic offline demo pack |

## Architecture

```
apps/web   Next.js 15 + TypeScript + Tailwind v4 + react-three-fiber + zustand
apps/api   FastAPI + WebSockets + networkx GraphRAG + SQLite (stdlib) + OpenAI SDK
```

Pipeline: **ingest → GraphRAG build → persona spawn → simulation rounds → report → chat**.
Memory, graph, and event logs all live in-process/SQLite — no external SaaS needed.

## Quick start

```bash
# prerequisites: Node 18+, Python 3.11+
npm run setup        # install web deps + create API venv + install python deps
npm run dev          # web → http://localhost:3000 · api → http://localhost:8000
```

No `.env` needed for a first run — without an LLM key the engine runs its seeded
**demo mode** and the full flow (build → simulate → inject → report → chat) works offline.
To go live, copy `.env.example` → `.env` and set `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL_NAME`
(or `OLLAMA_BASE_URL`).

### Docker

```bash
docker compose up --build   # web :3000, api :8000
```

### Cloud deploy

- **Backend:** Render (blueprint in `render.yaml`) or any Python host:
  `uvicorn hivemind.main:app --host 0.0.0.0 --port $PORT`
- **Frontend:** Vercel pointing at `apps/web`; set `NEXT_PUBLIC_API_BASE` (and
  `NEXT_PUBLIC_WS_URL`) to the backend URL. Locally the browser never talks to the
  API directly — Next rewrites proxy `/api` and `/ws` same-origin.

## Verify

```bash
npm run smoke       # health → create → build → simulate → report → chat
```

## Decisions (documented per build prompt)

- **Per-round `round_batch` WS frames** instead of one message per action — bounded
  throughput (≤1 msg/agent/round) and naturally replayable for the timeline.
- **Live mode token budget:** only each round's most influential post is LLM-written
  (graphs/personas/reports/chats also use the LLM); bulk volume uses the seeded generator.
- **Compose runs `next dev`** for the web container (env-driven rewrites, zero build step);
  the production path is Vercel + Render as above.
- **Fonts via `<link>`** rather than `next/font` so builds pass on fully offline networks.

## API map (prefix `/api`)

`POST /projects` (JSON or multipart) · `GET /projects` · `GET /projects/{id}` ·
`POST /projects/{id}/build` · `POST /projects/{id}/simulate` · `GET /runs/{rid}` ·
`POST /runs/{rid}/control` (pause/resume/stop/setSpeed/injectEvent) ·
`POST|GET /runs/{rid}/report` · `POST /runs/{rid}/chat/agent/{aid}` ·
`POST /runs/{rid}/chat/report` · `GET /runs/{rid}/agents/{aid}/memory` ·
`GET /health` · WS `/ws/runs/{rid}?after=<seq>` (replay then live)

Interactive API docs: `http://localhost:8000/docs`

---

*HIVE MIND is original work. It redesigns the swarm-prediction concept from first
principles and shares no code or assets with MiroFish.*
