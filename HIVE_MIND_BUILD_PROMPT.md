# 🧠 HIVE MIND — Master Build Prompt

> **Copy everything below the line and paste it to your coding agent.**
> It is a self-contained, from-scratch build specification for HIVE MIND — an enhanced,
> English-only, 3D swarm-intelligence prediction engine inspired by (not copied from) MiroFish.

---

```
═══════════════════════════════════════════════════════════════════════════════
PROJECT: HIVE MIND — Swarm Intelligence Prediction Engine
MISSION: Build AND deploy today. A full-stack multi-agent simulation platform
that predicts how crowds, markets, or narratives evolve — rendered as a living,
interactive 3D swarm — with an AI-generated prediction report at the end.
═══════════════════════════════════════════════════════════════════════════════

────────────────────────────────────────
0 ▸ PRODUCT DEFINITION (what it does)
────────────────────────────────────────
HIVE MIND is a swarm-intelligence "prediction rehearsal" engine. The user:

1. UPLOADS A SEED — one or more documents (PDF/TXT/MD) or pasted text: a news
   dossier, policy draft, market report, research notes, or a fiction world.
2. STATES A QUESTION — in natural language, e.g. "How will public sentiment
   evolve over 7 days?" or "Predict the most likely market reaction."
3. THE ENGINE BUILDS A WORLD — extracts entities & relationships into a
   knowledge graph (GraphRAG), then spawns N autonomous agents, each with a
   distinct persona, memory, goals, and stance derived from the seed.
4. THE SWARM RUNS — agents interact in discrete rounds (post, reply, endorse,
   dispute, form factions), with long-term + short-term memory updating over
   time. Emergent, collective behavior appears organically.
5. GOD'S-EYE INTERVENTIONS — the user can inject events mid-run
   ("a competitor launches a product", "a scandal breaks") and watch the
   shock ripple through the swarm in real time.
6. REPORT — a Report Agent analyzes the full simulation transcript + graph
   and produces a structured prediction report with confidence levels,
   cited evidence from specific agents/rounds, and scenario branches.
7. DEEP INTERACTION — after the run, the user can chat 1:1 with ANY
   individual agent (which answers in character from its memory) or with
   the Report Agent.

This is an ENHANCEMENT of the open-source project MiroFish (concept only).
ENHANCEMENTS over MiroFish that you MUST deliver:
  ✓ Full 3-D visualization of the swarm world (MiroFish is 2D-only)
  ✓ Real-time streaming simulation over WebSockets with a timeline scrubber
  ✓ Zero mandatory third-party SaaS (MiroFish requires Zep Cloud) — memory
    and graph run locally in-process
  ✓ Swappable LLM (OpenAI-compatible API OR local Ollama) + a fully offline
    DEMO MODE so the app is demo-able with no API key at all
  ✓ Modern dark "mission control" UI, English-only, one-command deploy.

────────────────────────────────────────
1 ▸ HARD CONSTRAINTS
────────────────────────────────────────
LANGUAGE / LOCALE
- ALL UI copy, code comments, file names, README, and docs: ENGLISH ONLY.
- Do NOT copy any code, images, or assets from the MiroFish repository.
  (It contains Chinese-language docs/screenshots — ignore them entirely.)
- Write everything from scratch. If a concept exists in MiroFish, re-derive
  it from the pipeline described above, never by porting code.

LLM ACCESS
- All LLM calls MUST go through one OpenAI-compatible client layer driven by
  env vars: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME.
- If OLLAMA_BASE_URL is set, use it instead (OpenAI-compatible endpoint).
- DEMO MODE: if NO LLM key is present, the backend must still run end-to-end
  using a deterministic scripted simulation (pre-baked personas, seeded RNG,
  template-based posts) so the entire app incl. 3D visuals is demo-able
  offline. Never crash on a missing key.

SCOPE DISCIPLINE
- Build MVP first and get it rendering + running, then layer enhancements.
  Follow the BUILD ORDER in section 9 exactly.
- No auth, no multi-tenancy, no payments. Single-user local/cloud tool.

────────────────────────────────────────
2 ▸ TECH STACK (fixed — do not substitute)
────────────────────────────────────────
Frontend  : Next.js 15 (App Router) + TypeScript + Tailwind CSS
3D        : three + @react-three/fiber + @react-three/drei
Motion    : framer-motion
State     : zustand (+ a small event buffer for the simulation stream)
Charts    : recharts (2D analytics panels only)
UI kit    : shadcn/ui (Radix) + lucide-react icons only — no other icon sets
Backend   : Python 3.11+, FastAPI + uvicorn + WebSockets
Validation: pydantic v2
LLM       : openai python SDK (base_url-configurable) / Ollama fallback
Graph     : networkx (in-process knowledge graph; persisted as JSON)
Docs      : PyMuPDF (PDF), python-docx optional, charset-normalizer
DB/store  : SQLite via sqlmodel (SQLite file = "project" persistence)
Package   : uv for Python deps, npm for Node
Deploy    : docker-compose (single command) AND one-click cloud path
            (frontend → Vercel, backend → Render/Railway) — provide both.

────────────────────────────────────────
3 ▸ DESIGN SYSTEM (do this FIRST, then reference tokens everywhere)
────────────────────────────────────────
Aesthetic: "luminescent hive in deep space". Dark, cinematic, high-contrast,
telemetry-like data density, but never cluttered. English type only.

CSS tokens (globals.css :root — DO NOT hardcode hex anywhere else):
  --background: 228 35% 4%;          /* deep space navy-black  */
  --surface:    228 28% 8%;          /* panel base             */
  --surface-2:  228 24% 12%;
  --border:     224 18% 20%;
  --foreground: 210 40% 96%;
  --muted-fg:   215 20% 65%;
  --hive-amber: 38 100% 55%;         /* PRIMARY — honey/amber  */
  --hive-cyan:  187 100% 55%;        /* interactions / links   */
  --hive-violet:265 90% 65%;         /* factions / memory      */
  --hive-rose:  340 85% 60%;         /* negative sentiment     */
  --hive-green: 152 70% 50%;         /* positive sentiment     */
  --ring:       38 100% 55%;
  --radius: 12px;
Map all tokens into Tailwind theme extension. Semantic sentiment colors map
to tokens ONLY (positive=green, neutral=cyan, negative=rose).

Typography: Inter (UI) + JetBrains Mono (telemetry/numbers/logs) via
next/font/google. Sizes: display 48/56, h1 32/40, h2 24/32, body 15/24,
mono-data 13/20.

Signature visuals (REQUIRED):
- Ambient 3D hero background: GPU-instanced boid swarm (~1500 particles,
  hexagonal glow sprites) flowing behind the landing content, amber/cyan,
  fog + additive blending, subtle mouse parallax. 60fps budget; throttle
  to 500 particles or static poster under prefers-reduced-motion or
  navigator.hardwareConcurrency < 4.
- Glass telemetry panels: bg = hsl(var(--surface)/0.72), backdrop-blur,
  1px border hsl(var(--border)), radius var(--radius), inner hairline glow.
- Status language: pulsing dot + mono uppercase labels (QUEUED / BUILDING
  GRAPH / SIMULATING / REPORTING / COMPLETE / FAILED).
- Motion: framer-motion; 150–250ms easeOut micro-interactions; staggered
  panel reveals; NO janky layout animations (animate transform/opacity).
  Respect prefers-reduced-motion globally.

────────────────────────────────────────
4 ▸ REPOSITORY LAYOUT (monorepo, npm workspaces)
────────────────────────────────────────
hive-mind/
  ├─ README.md                # English: what/why, screenshots, quickstart
  ├─ docker-compose.yml       # frontend:3000, backend:8000 — one command
  ├─ .env.example             # EVERY env var, commented
  ├─ package.json             # scripts: dev / setup / build
  ├─ apps/web/                # Next.js app (all UI)
  └─ apps/api/                # FastAPI app (all engine code)
       ├─ hivemind/
       │   ├─ main.py            # FastAPI entry, CORS, routers, WS mount
       │   ├─ config.py          # pydantic-settings, env loading
       │   ├─ llm.py             # OpenAI-compat client + Ollama + DEMO shim
       │   ├─ ingest.py          # file upload→text (pdf/txt/md), chunking
       │   ├─ graphrag.py        # entity/edge extraction, networkx graph,
       │   │                     #   community detection, retrieval() for RAG
       │   ├─ personas.py        # generate N agent personas from the graph
       │   ├─ memory.py          # per-agent short/long-term memory stores,
       │   │                     #   temporal decay, retrieval by relevance
       │   ├─ engine.py          # SimulationEngine: rounds, action loop,
       │   │                     #   event injection, faction/sentiment calc,
       │   │                     #   async generator emitting WSEvent objects
       │   ├─ reporter.py        # ReportAgent: transcript+graph→report JSON
       │   ├─ chat.py            # agent persona chat + report Q&A
       │   ├─ demo.py            # offline deterministic simulation pack
       │   ├─ models.py          # pydantic schemas shared by API+WS
       │   └─ store.py           # SQLite persistence: projects/runs/reports
       └─ pyproject.toml        # uv-managed

────────────────────────────────────────
5 ▸ BACKEND SPEC
────────────────────────────────────────
REST API (prefix /api):
  POST   /api/projects                      {name, seedText?} + multipart files
  GET    /api/projects                      list with status
  GET    /api/projects/{id}                 full detail incl. graph summary
  POST   /api/projects/{id}/build           extract entities→graph→personas
                                            {agentCount, platformCount(1|2)}
  POST   /api/projects/{id}/simulate        start run {rounds, speed, seed}
  POST   /api/runs/{runId}/control          {action: pause|resume|stop|
                                             setSpeed|injectEvent {text}}
  GET    /api/runs/{runId}/report           get report (or 202 while running)
  POST   /api/runs/{runId}/chat/agent/{agentId}     {message} → reply
  POST   /api/runs/{runId}/chat/report              {message} → reply
  GET    /api/health                         {ok, llm: "live"|"demo"}

WebSocket  /ws/runs/{runId}  — JSON events (pydantic-validated):
  {type:"round_started", round}
  {type:"agent_action", round, agent:{id,name,faction,spoke:"post|reply|
        endorse|dispute", sentiment:-1..1, text, targets:[agentId...],
        influence, position:[x,y,z]} }
  {type:"graph_update", nodesAdded:[], edgesAdded:[]}
  {type:"metrics", round, sentimentAvg, activityCount, factionShares:{},
        topInfluencers:[{id,name,score}]}
  {type:"event_injected", text, tick}
  {type:"report_progress", stage}
  {type:"run_complete", summary}
  {type:"error", message}
Backpressure: batch agent_action events per round (≤50 msgs/sec). Client
reconnects with Last-Event-Id equivalent (runSeq cursor).

ENGINE RULES
- Persona schema: {id, name, archetype, bio, goals[], stance:-1..1,
  openness, aggression, followers, memoryRefs[], color}
- Each round: sample active agents (scaled by influence), each takes one
  action chosen by LLM (or demo shim) GROUNDED in its memory + graph
  context (GraphRAG retrieval). Actions mutate memory store and edge
  weights; factions form via community detection on the interaction graph
  every k rounds. Deterministic given {seed}.
- A run is resumable from SQLite: full event log persisted (replay = same
  visuals, no LLM calls — also powers the timeline scrubber).
- Report JSON schema: {summary, overallPrediction, confidence:0..1,
  keyFindings[{claim, evidence:[{round,agentId,quote}], confidence}],
  scenarioBranches[{name, probability, trigger, outcome}],
  injectableSuggestions[], topAgents[]}
- Errors: typed JSON errors, never a bare 500; log to stdout.

────────────────────────────────────────
6 ▸ FRONTEND SPEC — pages & components
────────────────────────────────────────
Routes (App Router):
  /                      Landing: 3D boid hero, value prop, "Launch a
                         simulation" CTA, live DEMO MODE badge when offline
  /new                   Wizard: 1) seed upload/text  2) question + params
                         (agents 10–500, rounds 5–200, platforms 1–2,
                         speed)  3) review → build
  /p/[id]/build          Pipeline progress: graph grows live (3D force
                         graph), persona roster grid fills in
  /p/[id]/run            THE MISSION CONTROL (below)
  /p/[id]/report         Report reader + report chat
  /projects              Local project list (from /api)

MISSION CONTROL (/p/[id]/run) — the centerpiece, required components:
  1. <SwarmCanvas/> — react-three-fiber scene, fills ~70% of viewport:
     - <instancedMesh> agents as glowing hex prisms/icosphere orbs,
       colored by faction, emissive intensity = influence, pulse on action
     - 3D force-directed layout derived from the interaction graph
       (precompute with d3-force-3d on the client; animate transitions)
     - <Line/> links appear briefly between action source→targets
       (fade 1.2s, cyan) — this is what makes interactions VISIBLE
     - injected events = expanding emissive ring + camera shake (subtle)
     - OrbitControls (damped), hover → agent tooltip card, click →
       select agent → right panel pins to that agent
       (FPS guard: cap at 2000 instanced nodes; use drei <AdaptiveEvents>
       and <Preload>; static fallback canvas for reduced-motion)
  2. Right telemetry rail (glass panels):
     - Round / phase status chip   • Live sentiment gauge (histogram)
     - Faction share bar (stacked, violet/amber/cyan)
     - Top influencers list (click to focus camera)
     - Live activity feed (virtualized, agent avatar+text, color-coded
       action type) — clicking any entry jumps timeline+camera to it
  3. Bottom timeline: scrubber across all rounds (replay = read event
     log, NO LLM calls), play/pause, speed 0.5×–8×, round heat strip
     (activity density), event markers.
  4. God's-eye console: textarea + "Inject event" → POST control; the
     ripple animation plays on the scene and the event appears on the
     timeline immediately.
  5. Header: project name, question, LIVE/OFFLINE badge, LLM mode badge
     (live/demo), run controls (pause/stop), "Generate report" (enabled
     after ≥1 completed round), link to /report when ready.
  6. Agent detail drawer: persona card, memory timeline, its stance over
     time (sparkline), "Chat with agent" tab (in-character replies).
States: loading skeletons for every panel; empty states with guidance;
error toasts; WebSocket reconnect banner.

Component rules:
- Header/Footer are standalone components (apps/web/components/{Header,
  Footer}.tsx) reused via root layout — never inline them per page.
- Folder map: components/ (ui primitives, glass panel), components/three/
  (SwarmCanvas, BoidsHero, ForceGraph, AgentMesh, EventRipple), lib/
  (api client, ws client with auto-reconnect, event buffer), store/
  (zustand slices: run, selection, timeline).
- Every numeric UI uses mono font; every async button has loading+disabled
  states; every list is virtualized >100 rows.

────────────────────────────────────────
7 ▸ ASSET & COPY RULES
────────────────────────────────────────
- Fonts: Inter + JetBrains Mono only. No other font imports.
- Icons: lucide-react ONLY. No emoji in UI copy except a single 🧠/🐝 in
  the README/logo lockup. Logo = inline SVG hexagon-hive mark you author.
- NO stock photos, NO external image URLs, NO copied MiroFish images.
  Any "screenshot" in README must be taken from OUR built app.
- Favicon: generated SVG hive hexagon. OG image = the 3D swarm canvas
  screenshot (add /api/og or a static asset, either is fine).
- All copy in English, concise, confident, technical but approachable.

────────────────────────────────────────
8 ▸ DEPLOYMENT (today)
────────────────────────────────────────
Local dev:   `npm run dev` → web :3000, api :8000 (proxy /api + /ws via
             Next rewrites; browser must NEVER call localhost:8000 —
             relative URLs only).
Docker:      `docker compose up --build` → same ports, single network.
Cloud:       Provide render.yaml (FastAPI service) + vercel.json/README
             steps (Next statics/env: NEXT_PUBLIC_API_BASE absent → same
             origin rewrites; when split, use wss/https env-driven).
Env template (.env.example) documents: LLM_API_KEY, LLM_BASE_URL,
LLM_MODEL_NAME, OLLAMA_BASE_URL, PORT, DATABASE_URL, DEMO_MODE.
Smoke test script ./scripts/smoke.sh: health → create demo project →
build → 10-round demo sim → report → asserts 200s. Must pass before you
declare done.

────────────────────────────────────────
9 ▸ BUILD ORDER (strict — verify each phase before continuing)
────────────────────────────────────────
P0  Scaffold monorepo, tokens/globals.css, Tailwind, shadcn init, Header/
    Footer, landing shell. `npm run dev` renders with zero errors.
P1  Backend skeleton: FastAPI + all REST routes returning stub pydantic
    responses + /api/health. Demo-mode LLM shim. OpenAPI at /docs.
P2  Ingest→GraphRAG→Personas (demo + live paths). /build page live graph.
P3  Engine + WS streaming (demo pack first, then LLM). Mission control
    renders the stream in 2D feed + metrics.
P4  3D SwarmCanvas + timeline scrubber + event injection ripple.
P5  ReportAgent + report page + agent chat + report chat.
P6  Polish: empty/skeleton/error states, reduced-motion, FPS guards,
    README with real screenshots, .env.example, docker-compose, smoke.sh.
P7  Deploy: docker compose verified locally; cloud deploy instructions
    tested as far as possible in this environment. Ship.

────────────────────────────────────────
10 ▸ ACCEPTANCE CHECKLIST (self-review; fix before finishing)
────────────────────────────────────────
[ ] One command (`docker compose up --build` OR npm run dev) runs the
    whole app; /api/health returns {ok:true, llm:"demo"} with no keys.
[ ] Full demo flow works offline: seed→build→simulate≥10 rounds→report
    →agent chat, with NO external calls and NO console errors.
[ ] 3D swarm: ≥500 agents render interactively (pan/zoom/hover/click),
    actions visibly draw links, injected events visibly ripple, timeline
    scrub replays state, and FPS stays ≥40 (or auto-degraded gracefully).
[ ] English only everywhere (grep the repo for CJK → must be clean).
[ ] Every token in :root; no hardcoded hex outside tokens; no lucide-
    alternative icons; Inter+JetBrains Mono only.
[ ] WS reconnects; all buttons have loading/disabled states; skeletons
    everywhere async; typed JSON errors surfaced as toasts.
[ ] respects prefers-reduced-motion (boids static, no camera shake).
[ ] README (English) with real screenshots of OUR app + quickstart +
    deploy docs; .env.example complete; scripts/smoke.sh exits 0.

DEFINITION OF DONE = P0–P7 complete AND every box above ticked.
Do not ask questions — make the sensible choice, document it in README
"Decisions" section, and keep building.
```

---

## 📎 How to use this prompt

1. Paste the whole block above (between the fences) into your agent as the opening instruction.
2. If your agent stalls on the 3D phase (P4), tell it: *"Ship P3 with the 2D feed first, then P4"* — the prompt is explicitly structured to make that safe.
3. To go live: run `docker compose up --build` locally, or push the repo and follow the generated `render.yaml` + Vercel steps from P7.
