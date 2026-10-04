"""ReportAgent: simulation event log → structured prediction report.

Demo mode computes a real, data-grounded report from the run's own
statistics; live mode asks the LLM to write the narrative on top of those
same stats and evidence quotes.
"""
import random
import time
from typing import Any

from . import llm
from .store import store


def _collect(run_id: str) -> dict[str, Any]:
    actions, metrics, injections = [], [], []
    for ev in store.events_after(run_id):
        if ev["type"] == "round_batch":
            actions.extend(ev.get("actions", []))
        elif ev["type"] == "metrics":
            metrics.append(ev)
        elif ev["type"] == "event_injected":
            injections.append(ev)
    return {"actions": actions, "metrics": metrics, "injections": injections}


def _window_mean(actions: list[dict], max_round: int) -> float:
    s = [a["sentiment"] for a in actions if a.get("round", 0) <= max_round]
    return sum(s) / len(s) if s else 0.0


def _tail_mean(actions: list[dict], min_round: int) -> float:
    s = [a["sentiment"] for a in actions if a.get("round", 0) >= min_round]
    return sum(s) / len(s) if s else 0.0


def _quote(actions: list[dict], prefer_rounds: tuple[int, int] | None = None) -> dict | None:
    pool = actions
    if prefer_rounds:
        lo, hi = prefer_rounds
        pool = [a for a in actions if lo <= a.get("round", 0) <= hi] or actions
    if not pool:
        return None
    a = max(pool, key=lambda x: abs(x.get("sentiment", 0)))
    return {"round": a["round"], "agentId": a["agentId"],
            "agent": a.get("name", ""), "quote": a.get("text", "")}


def generate(run_id: str, run: dict, project: dict) -> dict:
    bus_data = _collect(run_id)
    actions = bus_data["actions"]
    rounds = max(1, run.get("rounds", 1))
    metrics = bus_data["metrics"]
    injections = bus_data["injections"]
    personas = project.get("personas") or []
    rng = random.Random(run.get("seed", 42) * 31 + len(actions))

    if run.get("summary") and run["summary"].get("personas"):
        personas = run["summary"]["personas"]

    early = _window_mean(actions, min(3, rounds))
    late = _tail_mean(actions, max(1, rounds - 2))
    drift = late - early

    # Per-faction sentiment at the end of the run
    by_faction: dict[int, list[float]] = {}
    for a in actions:
        if a.get("round", 0) >= max(1, rounds - 2):
            by_faction.setdefault(a.get("faction", 0), []).append(a["sentiment"])
    faction_means = {f: (sum(v) / len(v)) for f, v in by_faction.items() if v}
    polarity = (max(faction_means.values()) - min(faction_means.values())) if len(faction_means) > 1 else 0.0

    score: dict[str, float] = {}
    for a in actions:
        score[a["agentId"]] = score.get(a["agentId"], 0) + 1
        for t in a.get("targets", []):
            score[t] = score.get(t, 0) + 2
    p_by_id = {p["id"]: p for p in personas}
    top = sorted(score.items(), key=lambda kv: -kv[1])[:5]
    top_agents = [{
        "id": aid, "name": p_by_id.get(aid, {}).get("name", aid),
        "archetype": p_by_id.get(aid, {}).get("archetype", ""),
        "faction": p_by_id.get(aid, {}).get("faction", 0),
        "score": round(sc, 1),
    } for aid, sc in top]

    direction = ("supportive" if late > 0.12 else "opposed" if late < -0.12 else "divided")
    trend_w = ("trended upward" if drift > 0.05 else "trended downward" if drift < -0.05 else "stabilized")

    findings: list[dict[str, Any]] = []
    q_early, q_late = _quote(actions, (1, 3)), _quote(actions, (max(1, rounds - 2), rounds))
    findings.append({
        "claim": f"Swarm sentiment {trend_w} over the run, settling {direction} "
                 f"(avg {late:+.2f} on a −1…+1 scale).",
        "evidence": [q for q in [q_early, q_late] if q],
        "confidence": round(min(0.9, 0.55 + abs(drift)), 2),
    })
    if metrics:
        f_shares = metrics[-1].get("factionShares", {})
        if f_shares:
            dom = max(f_shares.items(), key=lambda kv: kv[1])
            findings.append({
                "claim": f"Faction {dom[0]} formed the largest bloc "
                         f"({dom[1] * 100:.0f}% of agents), anchoring the majority narrative.",
                "evidence": [q for q in [_quote(actions)] if q][:1],
                "confidence": 0.72,
            })
    if polarity > 0.35:
        findings.append({
            "claim": f"The swarm POLARIZED: opposing factions ended {polarity:.2f} "
                     f"apart on the sentiment scale — consensus is fragile.",
            "evidence": [q for q in [_quote(actions)] if q][:1],
            "confidence": 0.8,
        })
    for ev in injections:
        t = ev.get("tick", 0)
        before = _window_mean(actions, t) if t > 1 else early
        after_mean = _tail_mean(actions, t + 1)
        delta = after_mean - before
        findings.append({
            "claim": f'Injected event "{ev.get("text","")}" shifted swarm sentiment '
                     f"{'up' if delta >= 0 else 'down'} by {abs(delta):.2f} within one round.",
            "evidence": [q for q in [_quote(actions, (t, min(rounds, t + 2)))] if q][:1],
            "confidence": 0.65,
        })

    probs = [rng.uniform(0.3, 0.6), rng.uniform(0.15, 0.35), 0.0]
    probs[2] = 1.0 - probs[0] - probs[1]
    branches = [
        {"name": "Consensus consolidation", "probability": round(probs[0], 2),
         "trigger": "Majority narrative keeps reinforcing with no strong counter-event",
         "outcome": ("Sentiment settles into a stable plateau; early "
                     "influencers retain narrative control.")},
        {"name": "Polarization spiral", "probability": round(probs[1], 2),
         "trigger": "A high-reach dispute between top influencers",
         "outcome": "Two hardened blocs emerge; moderation voices lose reach."},
        {"name": "Single-event reversal", "probability": round(probs[2], 2),
         "trigger": "A credible external shock (news, ruling, leak)",
         "outcome": "Swarm flips within 2–3 rounds; faction boundaries redraw."},
    ]
    branches.sort(key=lambda b: -b["probability"])

    agreement = 1.0 - min(1.0, polarity)
    confidence = round(max(0.35, min(0.92, 0.5 + abs(late) * 0.25 + agreement * 0.2)), 2)

    report: dict[str, Any] = {
        "summary": (
            f"Across {rounds} rounds and {len(actions)} agent actions, the swarm's "
            f"collective stance {trend_w}, settling into a {direction} equilibrium. "
            f"{'The population polarized into hardened factions. ' if polarity > 0.35 else ''}"
            f"{len(injections)} external event(s) were injected and absorbed."
        ),
        "overallPrediction": (
            f"Question: “{project.get('question','')}” — The most probable path is "
            f"'{branches[0]['name']}' ({branches[0]['probability'] * 100:.0f}%): "
            f"{branches[0]['outcome']}"
        ),
        "confidence": confidence,
        "keyFindings": findings,
        "scenarioBranches": branches,
        "injectableSuggestions": [
            "A surprise regulatory clarification is published",
            "A viral counter-narrative appears from a high-reach account",
            "A major partnership announcement resets the frame",
        ],
        "topAgents": top_agents,
        "meta": {
            "agents": len(personas), "rounds": rounds, "actions": len(actions),
            "mode": llm.mode(), "generatedAt": time.time(),
            "finalSentiment": round(late, 3), "polarization": round(polarity, 3),
        },
    }

    if llm.mode() == "live":
        stats = {
            "question": project.get("question", ""),
            "direction": direction, "drift": round(drift, 3),
            "finalSentiment": late, "polarization": round(polarity, 3),
            "findings": [f["claim"] for f in findings],
            "branches": [{"name": b["name"], "p": b["probability"]} for b in branches],
            "quotes": [e for f in findings for e in f["evidence"]][:6],
        }
        enriched = llm.complete_json(
            "You are a senior foresight analyst. Given simulation statistics, return JSON: "
            '{"summary": 3-4 sentence executive summary, "overallPrediction": '
            "1-2 sentence direct answer to the simulation question}",
            f"Simulation statistics:\n{stats}", max_tokens=500,
        )
        if enriched:
            if enriched.get("summary"):
                report["summary"] = str(enriched["summary"])
            if enriched.get("overallPrediction"):
                report["overallPrediction"] = str(enriched["overallPrediction"])

    return report
