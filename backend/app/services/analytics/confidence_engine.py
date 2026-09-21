"""
HiveMind Prediction Confidence Engine
=====================================

Grades how much a simulation's prediction should be trusted, using
convergence diagnostics from computational social science:

  1. Stabilisation   — rolling variance of round-level mean sentiment in the
                       last third of rounds vs. the first third.
  2. Consensus       — share of the dominant emotion + vanishing polarity
                       spread across agents.
  3. Cascade energy  — engagement (likes/reposts per post) acceleration,
                       signalling whether the topic is still evolving.
  4. Data sufficiency — agent count, post count, rounds completed.

Output: score 0-100, band label (low/medium/high), and a per-factor
breakdown for transparent, explainable UI (each factor shown as a gauge).
"""

from __future__ import annotations

import math
from typing import Dict, List


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _variance(xs):
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def _rolling_means(posts: List[Dict], n_rounds: int) -> List[float]:
    by_round: Dict[int, List[float]] = {}
    for p in posts:
        r = p.get("round", 0)
        by_round.setdefault(r, []).append(p.get("sentiment_compound", 0.0))
    return [_mean(by_round[r]) for r in sorted(by_round)]


def compute_confidence(scored_posts: List[Dict], actions: List[Dict],
                       n_agents: int, n_rounds: int) -> Dict:
    """
    Returns {score, band, factors: {stabilisation, consensus, cascade,
    sufficiency}, detail: {...}} — all normalised 0..1 except score/band.
    """
    posts = [p for p in scored_posts
             if p.get("action_type", "CREATE_POST") == "CREATE_POST"]
    n_posts = len(posts)

    # ---------- 1. stabilisation ----------
    series = _rolling_means(posts, n_rounds)
    if len(series) >= 4:
        third = max(1, len(series) // 3)
        early_var = _variance(series[:third])
        late_var = _variance(series[-third:])
        drift = abs(_mean(series[-third:]) - _mean(series[:third]))
        stabilisation = 1.0 / (1.0 + 12 * late_var + 3 * drift)
    elif series:
        stabilisation = 0.4
    else:
        stabilisation = 0.2

    # ---------- 2. consensus ----------
    emotions: Dict[str, int] = {}
    for p in posts:
        emotions[p.get("emotion", "neutral")] = \
            emotions.get(p.get("emotion", "neutral"), 0) + 1
    dominant_share = (max(emotions.values()) / n_posts) if posts else 0.0
    compounds = [p.get("sentiment_compound", 0.0) for p in posts]
    polar_share = ((sum(1 for c in compounds if c > 0.4) +
                    sum(1 for c in compounds if c < -0.4)) / n_posts) \
        if posts else 0.0
    consensus = 0.65 * dominant_share + 0.35 * (1 - polar_share)

    # ---------- 3. cascade energy (engagement acceleration) ----------
    engage = {}   # round -> engagement events
    for a in actions:
        if a.get("action_type") in ("LIKE_POST", "REPOST", "QUOTE_POST",
                                    "CREATE_COMMENT"):
            engage[a.get("round", 0)] = engage.get(a.get("round", 0), 0) + 1
    rounds_sorted = sorted(engage)
    if len(rounds_sorted) >= 4:
        half = len(rounds_sorted) // 2
        early_rate = _mean([engage[r] for r in rounds_sorted[:half]])
        late_rate = _mean([engage[r] for r in rounds_sorted[half:]])
        accel = (late_rate - early_rate) / (early_rate + 1e-9)
        cascade = 1.0 / (1.0 + math.exp(-2.5 * accel))     # sigmoid 0..1
    else:
        cascade = 0.5

    # ---------- 4. data sufficiency ----------
    sufficiency = min(1.0,
                      0.4 * min(n_agents / 30, 1.0) +
                      0.4 * min(n_posts / 200, 1.0) +
                      0.2 * min(n_rounds / 10, 1.0))

    score = round(100 * (0.35 * stabilisation + 0.25 * consensus +
                         0.2 * sufficiency + 0.2 * cascade), 1)
    band = "high" if score >= 70 else "medium" if score >= 45 else "low"

    detail = {
        "n_agents": n_agents,
        "n_posts": n_posts,
        "n_rounds": n_rounds,
        "sentiment_series": [round(x, 4) for x in series],
        "dominant_emotion": max(emotions, key=emotions.get) if emotions else None,
        "dominant_share": round(dominant_share, 3),
        "polar_share": round(polar_share, 3),
        "engagement_accel": round(accel, 3) if len(rounds_sorted) >= 4 else None,
    }
    return {
        "score": score,
        "band": band,
        "factors": {
            "stabilisation": round(stabilisation, 3),
            "consensus": round(consensus, 3),
            "cascade": round(cascade, 3),
            "sufficiency": round(sufficiency, 3),
        },
        "detail": detail,
    }
