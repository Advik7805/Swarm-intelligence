"""
HiveMind Network Analysis
=========================

Builds the agent interaction network from raw simulation action logs and
computes social-network-analysis (SNA) metrics:

  * Interaction graph  — nodes = agents, edges = follows/likes/reposts/comments
  * Influence ranking  — PageRank + in-degree centrality (weighted)
  * Bridge detection   — betweenness centrality (information brokers)
  * Community detection — Louvain modularity partitions (echo chambers)
  * Echo-chamber index  — 1 - cross-community interaction ratio

The graph is built from *observable interaction events*, not conversation
content, mirroring how social scientists infer networks from platform data.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Tuple

logger = logging.getLogger('hivemind.analytics.network')

try:
    import networkx as nx
    _NX = True
except ImportError:          # pragma: no cover - networkx is pure python
    nx = None
    _NX = False

# Interaction events that create edges, with weights (strength of tie)
EDGE_ACTIONS: Dict[str, float] = {
    "FOLLOW": 2.0,
    "LIKE_POST": 1.0,
    "LIKE_COMMENT": 1.0,
    "REPOST": 1.5,
    "QUOTE_POST": 1.5,
    "CREATE_COMMENT": 2.0,
    "MUTE": -1.5,          # negative tie
    "DISLIKE_POST": -0.5,
    "DISLIKE_COMMENT": -0.5,
}


def build_interaction_graph(actions: List[Dict]) -> "nx.DiGraph":
    """
    Build a weighted directed graph from OASIS action records.

    Each action dict needs: agent_id, action_type, action_args.
    CREATE_POST is not an interaction (no target) and is skipped.
    """
    G = nx.DiGraph() if _NX else None
    if G is None:
        return None

    for a in actions:
        atype = a.get("action_type", "")
        weight = EDGE_ACTIONS.get(atype)
        if weight is None:
            continue
        src = a.get("agent_id")
        args = a.get("action_args") or {}
        tgt = args.get("target_id") or args.get("user_id") or args.get("follow_user_id")
        # OASIS args vary by action; try common key patterns
        if tgt is None and atype in ("LIKE_POST", "DISLIKE_POST", "REPOST",
                                     "QUOTE_POST"):
            tgt = _resolve_post_author(args.get("post_id"), actions)
        if src is None or tgt is None or src == tgt:
            continue
        if G.has_edge(src, tgt):
            G[src][tgt]["weight"] += weight
        else:
            G.add_edge(src, tgt, weight=weight)
    return G


def _resolve_post_author(post_id, actions: List[Dict]):
    """Resolve which agent authored a post id (OASIS ids are sequential)."""
    if post_id is None:
        return None
    for a in actions:
        if a.get("action_type") == "CREATE_POST":
            args = a.get("action_args") or {}
            if str(args.get("post_id")) == str(post_id):
                return a.get("agent_id")
    # Fallback: OASIS global post ids map to agent round-robin; unusable
    # without the platform db — return None rather than guess.
    return None


def analyze_network(actions: List[Dict]) -> Dict:
    """
    Full SNA pass. Returns a JSON-serialisable dict:
      influencers : top agents by composite influence score
      communities : list of {id, members, size, cohesion}
      echo_chamber_index : 0 (healthy diversity) .. 1 (perfect segregation)
      stats       : density, edge count, reciprocity, mean strength
    """
    G = build_interaction_graph(actions)
    if G is None or G.number_of_nodes() == 0:
        return {"influencers": [], "communities": [],
                "echo_chamber_index": 0.0,
                "stats": {"nodes": 0, "edges": 0, "density": 0.0,
                          "reciprocity": 0.0, "modularity": 0.0}}

    # ---- influence ----
    try:
        pagerank = nx.pagerank(G, weight="weight", max_iter=200)
    except Exception:
        pagerank = {n: 1.0 / G.number_of_nodes() for n in G.nodes}
    in_deg = dict(G.in_degree(weight="weight"))
    out_deg = dict(G.out_degree(weight="weight"))
    try:
        betweenness = nx.betweenness_centrality(G, weight="weight")
    except Exception:
        betweenness = {n: 0.0 for n in G.nodes}

    def _norm(d: Dict) -> Dict:
        mx = max(d.values()) or 1.0
        return {k: (v / mx if v > 0 else 0.0) for k, v in d.items()}

    pr_n, id_n, bt_n = _norm(pagerank), _norm({k: max(v, 0) for k, v in in_deg.items()}), _norm(betweenness)
    influencers = sorted(
        G.nodes,
        key=lambda n: 0.5 * pr_n[n] + 0.3 * id_n[n] + 0.2 * bt_n[n],
        reverse=True,
    )[:15]
    influencer_list = [{
        "agent_id": n,
        "influence": round(0.5 * pr_n[n] + 0.3 * id_n[n] + 0.2 * bt_n[n], 4),
        "pagerank": round(pagerank[n], 5),
        "in_degree": round(float(in_deg[n]), 2),
        "out_degree": round(float(out_deg[n]), 2),
        "betweenness": round(betweenness[n], 5),
    } for n in influencers]

    # ---- communities (Louvain on the undirected projection) ----
    U = G.to_undirected()
    for u, v, d in U.edges(data=True):
        d["weight"] = max(d.get("weight", 1.0), 0.1)   # Louvain needs positive
    try:
        comms = nx.community.louvain_communities(U, weight="weight", seed=42)
        modularity = nx.community.modularity(U, comms, weight="weight")
    except Exception:
        try:
            comms = nx.community.greedy_modularity_communities(U, weight="weight")
            modularity = nx.community.modularity(U, comms, weight="weight")
        except Exception:
            comms = [set(U.nodes)]
            modularity = 0.0

    node_comm = {}
    communities_out = []
    for cid, members in enumerate(sorted(comms, key=len, reverse=True)):
        members = sorted(members)
        for m in members:
            node_comm[m] = cid
        # cohesion: internal edge weight share
        internal = sum(d.get("weight", 1) for u, v, d in U.edges(members, data=True)
                       if v in members)
        total = sum(d.get("weight", 1) for _, _, d in U.edges(members, data=True))
        communities_out.append({
            "id": cid,
            "size": len(members),
            "members": members[:60],   # cap payload
            "cohesion": round(internal / total, 3) if total else 0.0,
        })

    # ---- echo chamber index ----
    cross = same = 0
    for u, v in G.edges():
        if node_comm.get(u) == node_comm.get(v):
            same += 1
        else:
            cross += 1
    echo = same / (same + cross) if (same + cross) else 0.0

    stats = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "density": round(nx.density(G), 5),
        "reciprocity": round(nx.reciprocity(G), 3) if G.number_of_edges() else 0.0,
        "modularity": round(float(modularity), 4),
        "echo_chamber_index": round(echo, 3),
    }
    return {"influencers": influencer_list, "communities": communities_out,
            "node_community": {str(k): v for k, v in node_comm.items()},
            "stats": stats}
