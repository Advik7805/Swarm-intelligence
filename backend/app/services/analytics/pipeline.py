"""
HiveMind Analytics Pipeline
===========================

Orchestrates the full post-simulation analysis:

    actions.jsonl ──▶ HIVE-Sent sentiment/emotion scoring
                 ──▶ NetworkX interaction graph (influence + communities)
                 ──▶ Persona clustering (archetype discovery)
                 ──▶ Prediction confidence scoring
                 ──▶ SQLite persistence

The pipeline is fault-isolated: any single engine failing degrades its own
section without affecting the rest or the core simulation flow.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Dict, List, Optional

from .confidence_engine import compute_confidence
from .db import AnalyticsDB
from .network_analysis import analyze_network
from .persona_clustering import cluster_personas
from .sentiment_engine import score_posts, summarize

logger = logging.getLogger('hivemind.analytics.pipeline')

_SIM_ROOT = os.environ.get(
    'HIVEMIND_SIM_DATA_DIR',
    os.path.join(os.path.dirname(__file__), '../../../uploads/simulations'))

_ACTION_TYPES = {
    "CREATE_POST", "LIKE_POST", "REPOST", "QUOTE_POST", "FOLLOW",
    "DO_NOTHING", "CREATE_COMMENT", "LIKE_COMMENT", "DISLIKE_POST",
    "DISLIKE_COMMENT", "SEARCH_POSTS", "SEARCH_USER", "TREND", "REFRESH",
    "MUTE", "PURCHASE_PRODUCT",
}


def _sim_dir(simulation_id: str) -> str:
    return os.path.join(_SIM_ROOT, simulation_id)


def load_actions(simulation_id: str) -> List[Dict]:
    """Load raw agent actions from all platform logs (skips event lines)."""
    actions: List[Dict] = []
    sim_dir = _sim_dir(simulation_id)
    for platform in ("twitter", "reddit"):
        path = os.path.join(sim_dir, platform, "actions.jsonl")
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if "event_type" in rec:
                        continue
                    rec["platform"] = platform
                    actions.append(rec)
        except OSError as e:
            logger.warning("Failed reading %s: %s", path, e)
    return actions


def load_profiles(simulation_id: str) -> List[Dict]:
    """Load agent profiles (reddit JSON preferred, twitter CSV optional)."""
    profiles: List[Dict] = []
    path = os.path.join(_sim_dir(simulation_id), "reddit_profiles.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                raw = raw.get("profiles", [])
            for p in raw:
                profiles.append({
                    "agent_id": p.get("user_id", p.get("agent_id", 0)),
                    "name": p.get("name") or p.get("username", ""),
                    "profession": p.get("profession"),
                    "mbti": p.get("mbti"),
                    "country": p.get("country"),
                })
        except (OSError, json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed reading profiles %s: %s", path, e)
    return profiles


def _extract_posts(actions: List[Dict]) -> List[Dict]:
    posts = []
    for a in actions:
        if a.get("action_type") != "CREATE_POST":
            continue
        args = a.get("action_args") or {}
        posts.append({
            "round": a.get("round", 0),
            "platform": a.get("platform", ""),
            "agent_id": a.get("agent_id", 0),
            "agent_name": a.get("agent_name", ""),
            "post_id": args.get("post_id", ""),
            "content": args.get("content", ""),
            "like_count": args.get("num_likes", args.get("likes", 0)) or 0,
            "action_type": "CREATE_POST",
        })
    return posts


def _merge_actions_histories(actions: List[Dict], n_rounds: int) -> Dict:
    return {"n_rounds": n_rounds}


class AnalyticsPipeline:
    """Run the full analysis for one simulation and persist results."""

    @classmethod
    def run(cls, simulation_id: str, topic: str = "",
            force: bool = False) -> Optional[Dict]:
        try:
            return cls._run_inner(simulation_id, topic, force)
        except Exception:
            logger.exception("Analytics pipeline failed for %s", simulation_id)
            return None

    @classmethod
    def _run_inner(cls, simulation_id: str, topic: str, force: bool):
        if not force and AnalyticsDB.has_run(simulation_id):
            return cls.overview(simulation_id)

        actions = load_actions(simulation_id)
        if not actions:
            logger.info("No actions found for %s — skipping analytics",
                        simulation_id)
            return None

        # 1) sentiment & emotion scoring on posts
        posts = _extract_posts(actions)
        posts = score_posts(posts)
        sent_summary = summarize(posts)

        # 2) social network analysis
        network = analyze_network(actions)

        # 3) persona clustering
        personas = cluster_personas(actions, posts)

        # 4) rounds completed (max round across actions)
        n_rounds = max((a.get("round", 0) for a in actions), default=0)
        n_agents = len({a.get("agent_id") for a in actions})

        # 5) prediction confidence
        confidence = compute_confidence(posts, actions, n_agents, n_rounds)

        # 6) persist
        AnalyticsDB.insert_posts(simulation_id, posts)

        profile_map = {p["agent_id"]: p for p in load_profiles(simulation_id)}
        influence = {i["agent_id"]: i for i in network.get("influencers", [])}
        node_comm = network.get("node_community", {})
        cluster_of = {}
        for c in personas.get("clusters", []):
            for aid in c.get("agent_ids", []):
                cluster_of[aid] = c["id"]

        agent_rows = []
        all_agent_ids = n_agents and sorted({a.get("agent_id") for a in actions})
        for aid in (all_agent_ids or []):
            prof = profile_map.get(aid, {})
            inf = influence.get(aid, {})
            agent_rows.append({
                "agent_id": aid,
                "name": prof.get("name", ""),
                "profession": prof.get("profession"),
                "mbti": prof.get("mbti"),
                "country": prof.get("country"),
                "influence": inf.get("influence", 0.0),
                "pagerank": inf.get("pagerank", 0.0),
                "community_id": node_comm.get(str(aid), -1),
                "cluster_id": cluster_of.get(aid, -1),
            })
        if agent_rows:
            # fill mean sentiment per agent from posts
            sents: Dict[int, List[float]] = {}
            for p in posts:
                sents.setdefault(p["agent_id"], []).append(
                    p.get("sentiment_compound", 0.0))
            for row in agent_rows:
                vals = sents.get(row["agent_id"])
                row["mean_sentiment"] = round(sum(vals) / len(vals), 3) if vals else 0.0
            AnalyticsDB.upsert_agents(simulation_id, agent_rows)

        platforms = ",".join(sorted({a.get("platform", "") for a in actions} - {""}))
        AnalyticsDB.save_network(simulation_id, network.get("stats", {}),
                                 network.get("influencers", []),
                                 network.get("communities", []))
        AnalyticsDB.save_clusters(simulation_id, personas.get("clusters", []))
        AnalyticsDB.save_confidence(simulation_id, confidence)
        AnalyticsDB.upsert_run(
            simulation_id, n_agents=n_agents, n_rounds=n_rounds,
            n_posts=len(posts), platforms=platforms, topic=topic,
            sentiment_summary=sent_summary,
            network_summary=network.get("stats", {}),
            confidence_summary={"score": confidence["score"],
                                "band": confidence["band"]})
        logger.info("Analytics complete for %s: %d posts, %d agents, "
                    "confidence %.1f (%s)", simulation_id, len(posts),
                    n_agents, confidence["score"], confidence["band"])
        return cls.overview(simulation_id)

    # --------------------------------------------------------------
    @classmethod
    def overview(cls, simulation_id: str) -> Optional[Dict]:
        """Assemble the full analytics payload for the dashboard."""
        run = AnalyticsDB.get_run(simulation_id)
        if not run:
            return None
        posts = AnalyticsDB.get_posts(simulation_id)
        agents = AnalyticsDB.get_agents(simulation_id)
        network = AnalyticsDB.get_network(simulation_id) or {}
        clusters = AnalyticsDB.get_clusters(simulation_id)
        confidence = AnalyticsDB.get_confidence(simulation_id) or {}

        # sentiment timeline by round
        timeline: Dict[int, Dict] = {}
        for p in posts:
            r = p["round"]
            t = timeline.setdefault(r, {"round": r, "n_posts": 0,
                                        "sentiments": [], "emotions": {}})
            t["n_posts"] += 1
            t["sentiments"].append(p["sentiment_compound"] or 0.0)
            t["emotions"][p["emotion"]] = t["emotions"].get(p["emotion"], 0) + 1
        timeline_out = []
        for r in sorted(timeline):
            t = timeline[r]
            top_emotions = sorted(t["emotions"].items(), key=lambda kv: -kv[1])[:3]
            timeline_out.append({
                "round": r,
                "n_posts": t["n_posts"],
                "mean_sentiment": round(sum(t["sentiments"]) / len(t["sentiments"]), 3),
                "top_emotions": [{"emotion": e, "count": c}
                                 for e, c in top_emotions],
            })

        return {
            "simulation_id": simulation_id,
            "run": run,
            "sentiment_summary": json.loads(run.get("sentiment_summary") or "{}"),
            "timeline": timeline_out,
            "network": {"stats": network.get("stats", {}),
                        "influencers": network.get("influencers", []),
                        "communities": network.get("communities", [])},
            "agents": agents[:100],
            "personas": [{"id": c.get("cluster_id", c.get("id", 0)),
                          "label": c.get("label", "Unknown"),
                          "size": c.get("size", 0),
                          "top_terms": c.get("top_terms", []),
                          "signature": c.get("signature", {})}
                         for c in clusters],
            "confidence": confidence,
        }


def run_analytics_async(simulation_id: str, topic: str = "") -> None:
    """Fire-and-forget analytics in a background thread (never blocks the
    simulation finalisation path)."""
    def _work():
        AnalyticsPipeline.run(simulation_id, topic=topic)
    threading.Thread(target=_work, name=f"hivemind-analytics-{simulation_id[:8]}",
                     daemon=True).start()
