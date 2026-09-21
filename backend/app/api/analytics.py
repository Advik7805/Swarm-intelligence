"""
HiveMind Analytics API
======================

REST endpoints exposing the opinion-dynamics, network, persona and
confidence analytics, plus a fully self-contained DEMO MODE (seeded
synthetic simulation) so the platform can be explored end-to-end with
zero API keys or quota — ideal for the public live deployment.
"""

from __future__ import annotations

import json
import os
import random
import re
from flask import jsonify, request

from . import analytics_bp
from ..services.analytics import AnalyticsPipeline, AnalyticsDB, run_analytics_async
from ..services.analytics.pipeline import _SIM_ROOT


def _ok(payload):
    return jsonify({"success": True, "data": payload})


def _err(message: str, code: int = 400):
    return jsonify({"success": False, "error": message}), code


# --------------------------------------------------------------------------
# Pipeline triggers
# --------------------------------------------------------------------------

@analytics_bp.route('/run/<simulation_id>', methods=['POST'])
def trigger_analytics(simulation_id: str):
    """Run the full analytics pipeline for a simulation (idempotent unless
    ?force=1). Runs synchronously so the caller gets the overview back."""
    topic = (request.json or {}).get('topic', '') if request.is_json else ''
    force = request.args.get('force', '0') in ('1', 'true')
    result = AnalyticsPipeline.run(simulation_id, topic=topic, force=force)
    if result is None:
        return _err("No simulation data found for analytics", 404)
    return _ok(result)


@analytics_bp.route('/run/<simulation_id>/async', methods=['POST'])
def trigger_analytics_async(simulation_id: str):
    topic = (request.json or {}).get('topic', '') if request.is_json else ''
    run_analytics_async(simulation_id, topic=topic)
    return _ok({"queued": True})


# --------------------------------------------------------------------------
# Read endpoints
# --------------------------------------------------------------------------

@analytics_bp.route('/overview/<simulation_id>', methods=['GET'])
def get_overview(simulation_id: str):
    data = AnalyticsPipeline.overview(simulation_id)
    if data is None:
        return _err("Analytics not available for this simulation", 404)
    return _ok(data)


@analytics_bp.route('/sentiment/<simulation_id>', methods=['GET'])
def get_sentiment(simulation_id: str):
    run = AnalyticsDB.get_run(simulation_id)
    if not run:
        return _err("Analytics not available", 404)
    posts = AnalyticsDB.get_posts(simulation_id)
    from ..services.analytics.sentiment_engine import summarize
    import json as _json
    timeline = {}
    for p in posts:
        t = timeline.setdefault(p["round"], [])
        t.append(p["sentiment_compound"] or 0.0)
    return _ok({
        "summary": _json.loads(run.get("sentiment_summary") or "{}"),
        "timeline": [{"round": r, "mean_sentiment": round(sum(v) / len(v), 3),
                      "n_posts": len(v)} for r, v in sorted(timeline.items())],
        "sample_posts": posts[:50],
    })


@analytics_bp.route('/network/<simulation_id>', methods=['GET'])
def get_network(simulation_id: str):
    network = AnalyticsDB.get_network(simulation_id)
    if network is None:
        return _err("Network analytics not available", 404)
    return _ok(network)


@analytics_bp.route('/personas/<simulation_id>', methods=['GET'])
def get_personas(simulation_id: str):
    clusters = AnalyticsDB.get_clusters(simulation_id)
    if not clusters:
        return _err("Persona analytics not available", 404)
    return _ok({"clusters": clusters})


@analytics_bp.route('/confidence/<simulation_id>', methods=['GET'])
def get_confidence(simulation_id: str):
    conf = AnalyticsDB.get_confidence(simulation_id)
    if conf is None:
        return _err("Confidence analytics not available", 404)
    return _ok(conf)


@analytics_bp.route('/runs', methods=['GET'])
def list_runs():
    return _ok({"runs": AnalyticsDB.list_runs()})


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------

@analytics_bp.route('/health', methods=['GET'])
def health():
    db_ok = True
    try:
        AnalyticsDB.list_runs(limit=1)
    except Exception:
        db_ok = False
    return _ok({"status": "ok", "db": db_ok, "service": "hivemind-analytics"})


# --------------------------------------------------------------------------
# DEMO MODE — deterministic seeded fixture, zero external dependencies
# --------------------------------------------------------------------------

_DEMO_TOPICS = [
    ("A major city announces a plan to replace all parking lots with pocket "
     "parks by next year", ["traffic", "green space", "commute", "city hall",
     "parklets", "urbanism"]),
    ("A viral AI assistant passes a professional licensing exam, sparking "
     "debate about automation", ["AI", "jobs", "regulation", "future of work",
     "automation", "exam"]),
    ("Researchers publish a breakthrough battery with 2x range and 5-minute "
     "charging", ["EV", "range anxiety", "charging", "battery tech",
     "grid", "manufacturing"]),
]

_DEMO_TEMPLATES = {
    "supportive": [
        "This is exactly the kind of bold move we needed. Finally some real {kw}!",
        "Honestly impressed. If this works, {kw} changes for everyone 🙌",
        "Skeptical at first but the {kw} data is convincing. Well done.",
        "Great news for {kw}! Long overdue, can't wait to see it roll out.",
        "Proud of the team behind this. {kw} is the future, no doubt.",
    ],
    "outraged": [
        "Absolutely not. This {kw} plan is a disaster in the making 😡",
        "Who asked for this? Nobody. Fix {kw} first, then we talk.",
        "Another empty promise about {kw}. We've heard it all before.",
        "This will ruin {kw} for working people. Disgusting decision.",
        "Can't believe they're pushing {kw} without any public consultation!",
    ],
    "analytical": [
        "The {kw} numbers check out, but implementation risk is high.",
        "Interesting. Model says {kw} benefits show up only after 18 months.",
        "Worth noting the {kw} study had a small sample. Wait for replication.",
        "Cost-benefit on {kw} is marginal unless maintenance budgets hold.",
        "Second-order effects on {kw} are being ignored here, IMO.",
    ],
    "confused": [
        "Wait, does this affect {kw} or not? The article is unclear.",
        "So is {kw} good or bad now? Genuine question.",
        "I keep reading about {kw} and I still don't get it lol",
        "Can someone explain the {kw} part like I'm five?",
    ],
    "amplifier": [
        "RT: {kw} plan announced!! Huge. 👀",
        "Sharing this everywhere. {kw} is THE topic today.",
        "Everyone in my feed is talking about {kw} right now.",
        "Bookmarking this {kw} thread for later, it's going to blow up.",
    ],
}


def _build_demo_actions(simulation_id: str = "demo-run") -> Dict:
    """Deterministically simulate a mini OASIS run with 5 persona families."""
    rng = random.Random(42)
    topic, keywords = _DEMO_TOPICS[0]
    families = [
        ("supportive", 0.75, 0.30), ("outraged", -0.65, 0.85),
        ("analytical", 0.10, 0.25), ("confused", 0.0, 0.20),
        ("amplifier", 0.55, 0.55),
    ]
    actions, posts_meta = [], []
    agent_profiles = []
    agent_id = 0
    for fam, polarity, arousal in families:
        for _ in range(8):
            agent_profiles.append({
                "user_id": agent_id,
                "username": f"user_{agent_id:03d}",
                "name": f"{fam.capitalize()} {agent_id}",
                "persona": f"A {fam} commenter interested in {keywords[agent_id % len(keywords)]}.",
                "profession": ["teacher", "engineer", "nurse", "student",
                               "analyst", "driver", "designer", "farmer"][agent_id % 8],
                "country": "demo",
            })
            agent_id += 1

    rounds = 10
    post_counter = 0
    for rnd in range(1, rounds + 1):
        # sentiment warms up and converges over rounds (emergent dynamic)
        drift = 0.05 * rnd if rnd > 4 else 0.0
        for aid, (fam, polarity, arousal) in enumerate(
                [f for f in families for _ in range(8)]):
            if rng.random() < 0.35:
                actions.append({"round": rnd, "platform": rng.choice(["twitter", "reddit"]),
                                "agent_id": aid, "agent_name": f"user_{aid:03d}",
                                "action_type": "DO_NOTHING", "action_args": {}})
                continue
            roll = rng.random()
            if roll < 0.45:
                kw = rng.choice(keywords)
                content = rng.choice(_DEMO_TEMPLATES[fam]).format(kw=kw)
                content = _apply_drift(content, polarity + drift, rng)
                post_counter += 1
                pid = f"p{post_counter}"
                actions.append({"round": rnd, "platform": "twitter",
                                "agent_id": aid, "agent_name": f"user_{aid:03d}",
                                "action_type": "CREATE_POST",
                                "action_args": {"post_id": pid, "content": content,
                                                "num_likes": 0}})
                posts_meta.append(pid)
            elif roll < 0.7 and posts_meta:
                actions.append({"round": rnd, "platform": "twitter",
                                "agent_id": aid, "agent_name": f"user_{aid:03d}",
                                "action_type": "LIKE_POST",
                                "action_args": {"post_id": rng.choice(posts_meta)}})
            elif roll < 0.8 and posts_meta:
                actions.append({"round": rnd, "platform": "twitter",
                                "agent_id": aid, "agent_name": f"user_{aid:03d}",
                                "action_type": "REPOST",
                                "action_args": {"post_id": rng.choice(posts_meta)}})
            elif roll < 0.9:
                target = rng.choice([a for a in range(40) if a != aid])
                actions.append({"round": rnd, "platform": "twitter",
                                "agent_id": aid, "agent_name": f"user_{aid:03d}",
                                "action_type": "FOLLOW",
                                "action_args": {"target_id": target}})
            else:
                actions.append({"round": rnd, "platform": "twitter",
                                "agent_id": aid, "agent_name": f"user_{aid:03d}",
                                "action_type": "DO_NOTHING", "action_args": {}})
    actions.append({"event_type": "simulation_end", "total_rounds": rounds,
                    "total_actions": len(actions)})
    return {"topic": topic, "actions": actions, "profiles": agent_profiles,
            "rounds": rounds}


def _apply_drift(content: str, polarity: float, rng) -> str:
    """Late-simulation bandwagon: negative voices soften, positive amplify."""
    if polarity < -0.3 and rng.random() < 0.4:
        content = "On reflection, " + content[0].lower() + content[1:]
    elif polarity > 0.5 and rng.random() < 0.3:
        content += " Spreading the word!"
    return content


@analytics_bp.route('/demo', methods=['POST'])
def create_demo():
    """Materialise the demo simulation on disk and run analytics on it."""
    sim_id = "demo-" + str(abs(hash('hivemind-demo')) % 100000)
    sim_dir = os.path.join(_SIM_ROOT, sim_id, "twitter")
    os.makedirs(sim_dir, exist_ok=True)
    demo = _build_demo_actions(sim_id)
    with open(os.path.join(sim_dir, "actions.jsonl"), "w", encoding="utf-8") as f:
        for a in demo["actions"]:
            f.write(json.dumps(a) + "\n")
    prof_dir = os.path.join(_SIM_ROOT, sim_id)
    with open(os.path.join(prof_dir, "reddit_profiles.json"), "w",
              encoding="utf-8") as f:
        json.dump(demo["profiles"], f, ensure_ascii=False)
    result = AnalyticsPipeline.run(sim_id, topic=demo["topic"], force=True)
    if result is None:
        return _err("Demo generation failed", 500)
    result["demo"] = True
    result["topic"] = demo["topic"]
    return _ok(result)


@analytics_bp.route('/demo', methods=['GET'])
def get_demo():
    """Return the existing demo analytics, creating it on first request."""
    runs = AnalyticsDB.list_runs(200)
    for r in runs:
        if str(r.get("simulation_id", "")).startswith("demo-"):
            data = AnalyticsPipeline.overview(r["simulation_id"])
            if data:
                data["demo"] = True
                return _ok(data)
    return create_demo()
