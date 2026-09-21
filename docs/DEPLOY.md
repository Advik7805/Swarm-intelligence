# 🚀 HiveMind — Free Online Deployment Guide

This guide takes HiveMind from this repo to a **public URL**, 100% on free tiers.
Total time: ~20 minutes (mostly waiting for builds).

## Architecture

```
┌─────────────────┐        /api/* (rewritten)       ┌──────────────────────┐
│  Vercel (free)  │ ───────────────────────────────▶ │   Render (free)      │
│  Vue 3 frontend │                                  │  Flask + analytics   │
│  static + CDN   │ ◀─────────────────────────────── │  SQLite + OASIS      │
└─────────────────┘            JSON                 └──────────┬───────────┘
                                                               │
                                                    ┌──────────▼───────────┐
                                                    │  Google Gemini (LLM) │
                                                    │  Zep Cloud (memory)  │
                                                    └──────────────────────┘
```

The Vercel rewrite forwards `/api/*` to the Render backend, so the browser
only ever talks to one origin — no CORS setup needed.

> **Free-tier reality check (read this):**
> * Render free services **sleep after ~15 min idle** — the first request after
>   a nap takes ~50s to wake. Your demo data survives redeploys only while the
>   instance lives (ephemeral disk).
> * Both platforms require account verification (card not required for free tier).

---

## Step 0 — Get your two free API keys (5 min)

| Key | Where | Used for |
|-----|-------|----------|
| **Gemini API key** | https://aistudio.google.com/apikey → *Create API key* | All LLM calls (graph building, personas, reports) |
| **Zep Cloud API key** | https://app.getzep.com → sign up → *Project API key* | Agent memory knowledge graph |

Keep both handy — you'll paste them into Render's dashboard (never into Git!).

## Step 1 — Deploy the backend on Render (10 min)

1. Push this repo to your GitHub (already done: `Advik7805/Swarm-intelligence`).
2. Go to https://dashboard.render.com → **New +** → **Blueprint**.
3. Select your `Swarm-intelligence` repo. Render reads `render.yaml`.
4. When prompted, fill in the secret values:
   * `LLM_API_KEY` → your Gemini key
   * `ZEP_API_KEY` → your Zep key
5. Click **Apply** → wait for the build (~5 min).
6. Note your backend URL, e.g. `https://hivemind-api.onrender.com`
   (Test: open `<backend-url>/health` → should return JSON `status: ok`).

> ⚠️ If you named the Render service something else, update the URL inside
> `vercel.json` (next step) to match.

## Step 2 — Deploy the frontend on Vercel (5 min)

1. Go to https://vercel.com/new and import `Swarm-intelligence`.
2. Vercel auto-detects Vite. Set:
   * **Root Directory:** `frontend`
   * (vercel.json handles build + API rewrites automatically)
3. Click **Deploy** → wait ~2 min.
4. Your site is LIVE at `https://<your-project>.vercel.app` 🎉

## Step 3 — Verify

1. Open your Vercel URL → you should see the HiveMind dark landing page.
2. Click **⚡ Try Live Demo** inside *Opinion Analytics* — works with **zero
   keys**, great for sharing before your API quota is set up.
3. Full pipeline test: upload a small PDF/TXT seed on the landing page,
   describe a prediction, and run a **short simulation first** (≤ 10 rounds —
   free LLM quotas go fast!).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| First page load takes ~50s | Render free tier waking up — normal |
| `502` on `/api/*` | Backend asleep or crashed — check Render logs tab |
| Simulation stuck at step 2 | Check backend logs for LLM/Zep key errors (LIMITED MODE banner) |
| Analytics page empty | Click **Try Live Demo** — real runs appear after a simulation finishes |
| Build fails on Vercel | Make sure Root Directory is `frontend` and Node version ≥ 18 |

## Alternative: single-container deploy (Hugging Face Spaces)

Prefer one URL and one platform? HF Spaces runs the included `Dockerfile`
(frontend + backend in one container, dev mode). See the repo root `Dockerfile`.
Note: HF Spaces sleep after 48h of inactivity.
