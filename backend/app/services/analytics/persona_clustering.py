"""
HiveMind Persona Clustering
===========================

Discovers behavioural archetypes in the simulated population.

Method:
  1. Behavioural features — action mix (post/like/repost/follow/do-nothing
     ratios), activity level, mean sentiment of authored content, platform
     preference.
  2. Content features — TF-IDF over authored post text (top components).
  3. KMeans (k selected automatically by silhouette over k∈[3..6]) groups
     agents; each cluster gets a deterministic heuristic label from its
     behavioural signature (e.g. "Amplifiers", "Lurkers", "Outraged
     Broadcasters") plus top discriminating terms.

If scikit-learn is unavailable the module degrades to quantile-based rule
labelling so the platform never breaks on tiny hosts.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from typing import Dict, List

logger = logging.getLogger('hivemind.analytics.personas')

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    _SK = True
except ImportError:
    _SK = False

EPS = 1e-9


def build_agent_features(actions: List[Dict], scored_posts: List[Dict]) -> Dict[int, Dict]:
    """Aggregate per-agent behavioural + content features."""
    agents: Dict[int, Dict] = {}

    def _agent(aid: int) -> Dict:
        if aid not in agents:
            agents[aid] = {
                "agent_id": aid, "n_actions": 0, "n_posts": 0, "n_likes": 0,
                "n_reposts": 0, "n_follows": 0, "n_comments": 0,
                "n_passive": 0, "platform_twitter": 0, "platform_reddit": 0,
                "sentiments": [], "texts": [],
            }
        return agents[aid]

    post_sent = {}
    for p in scored_posts:
        post_sent[(p.get("agent_id"), str(p.get("post_id")))] = p.get("sentiment_compound", 0.0)

    for a in actions:
        ag = _agent(a.get("agent_id", 0))
        atype = a.get("action_type", "")
        ag["n_actions"] += 1
        if a.get("platform") == "twitter":
            ag["platform_twitter"] += 1
        else:
            ag["platform_reddit"] += 1
        args = a.get("action_args") or {}
        if atype == "CREATE_POST":
            ag["n_posts"] += 1
            content = args.get("content", "")
            ag["texts"].append(content)
            ag["sentiments"].append(post_sent.get(
                (a.get("agent_id"), str(args.get("post_id"))), 0.0))
        elif atype in ("LIKE_POST", "LIKE_COMMENT"):
            ag["n_likes"] += 1
        elif atype in ("REPOST", "QUOTE_POST"):
            ag["n_reposts"] += 1
        elif atype == "FOLLOW":
            ag["n_follows"] += 1
        elif atype == "CREATE_COMMENT":
            ag["n_comments"] += 1
        elif atype == "DO_NOTHING":
            ag["n_passive"] += 1

    for ag in agents.values():
        n = max(ag["n_actions"], 1)
        ag["post_ratio"] = ag["n_posts"] / n
        ag["amplify_ratio"] = (ag["n_likes"] + ag["n_reposts"]) / n
        ag["social_ratio"] = (ag["n_follows"] + ag["n_comments"]) / n
        ag["passive_ratio"] = ag["n_passive"] / n
        ag["twitter_ratio"] = ag["platform_twitter"] / n
        ag["mean_sentiment"] = (sum(ag["sentiments"]) / len(ag["sentiments"])
                                if ag["sentiments"] else 0.0)
    return agents


def _vectorise(agents: List[Dict]):
    """Behavioural matrix + optional TF-IDF content matrix."""
    behav = [[a["post_ratio"], a["amplify_ratio"], a["social_ratio"],
              a["passive_ratio"], a["twitter_ratio"], a["mean_sentiment"]]
             for a in agents]
    docs = [" ".join(a["texts"][:40]).strip() or "(silent)" for a in agents]
    if _SK and len(agents) >= 6 and any(len(d) > 12 for d in docs):
        try:
            tfidf = TfidfVectorizer(max_features=256, stop_words="english",
                                    sublinear_tf=True)
            X_text = tfidf.fit_transform(docs)
            # scale behavioural block to comparable magnitude
            import numpy as np
            Xb = np.array(behav, dtype=float)
            Xb = (Xb - Xb.mean(0)) / (Xb.std(0) + EPS)
            from sklearn.preprocessing import normalize
            from scipy.sparse import hstack, csr_matrix
            X = hstack([csr_matrix(Xb * 0.6), X_text * 0.8]).tocsr()
            return X, tfidf
        except Exception as e:
            logger.warning("TF-IDF vectorisation failed, using behaviour only: %s", e)
    if _SK:
        import numpy as np
        Xb = np.array(behav, dtype=float)
        Xb = (Xb - Xb.mean(0)) / (Xb.std(0) + EPS)
        return Xb, None
    return None, None


def _kmeans_labels(X, k_range=(3, 4, 5, 6)):
    best, best_k, best_score = None, None, -1.0
    kmin, kmax = k_range[0], k_range[-1]
    kmax = min(kmax, X.shape[0] - 1)
    if kmax < kmin:
        kmin = kmax
    for k in range(kmin, kmax + 1):
        try:
            km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
        except Exception:
            return None
        if k == 1:
            return km
        try:
            score = silhouette_score(X, km.labels_)
        except Exception:
            score = 0.0
        if score > best_score:
            best, best_k, best_score = km, k, score
    return best


def _heuristic_label(cluster_agents: List[Dict], top_terms: List[str]) -> str:
    """Deterministic archetype naming from behaviour signature."""
    mean = lambda key: sum(a[key] for a in cluster_agents) / len(cluster_agents)
    post, amplify = mean("post_ratio"), mean("amplify_ratio")
    passive, social = mean("passive_ratio"), mean("social_ratio")
    sent = mean("mean_sentiment")
    if passive > 0.5:
        return "Silent Observers"
    if post > 0.35 and sent < -0.15:
        return "Outraged Broadcasters"
    if post > 0.35 and sent > 0.15:
        return "Advocates & Champions"
    if amplify > 0.4:
        return "Amplifiers & Echoes"
    if social > 0.3:
        return "Connectors & Networkers"
    if post > 0.2:
        if top_terms:
            return f"Commentators · {top_terms[0]}"
        return "Commentators"
    return "Mixed Civilians"


def cluster_personas(actions: List[Dict], scored_posts: List[Dict]) -> Dict:
    """
    Returns:
      clusters: [{id, size, label, agent_ids, mean_sentiment, top_terms, signature}]
      n_clusters
    """
    features = build_agent_features(actions, scored_posts)
    if not features:
        return {"clusters": [], "n_clusters": 0}
    agent_ids = sorted(features.keys())
    agent_list = [features[i] for i in agent_ids]

    X, tfidf = _vectorise(agent_list)
    labels = None
    if X is not None and _SK:
        km = _kmeans_labels(X) if X.shape[0] >= 6 else None
        labels = km.labels_.tolist() if km is not None else None

    if labels is None:
        # rule-based fallback partition
        labels = []
        for a in agent_list:
            if a["passive_ratio"] > 0.5:
                labels.append(0)
            elif a["mean_sentiment"] < -0.15:
                labels.append(1)
            elif a["amplify_ratio"] > 0.4:
                labels.append(2)
            else:
                labels.append(3)

    n_clusters = len(set(labels))
    # top terms per cluster via tf-idf centroids (or word frequencies)
    clusters_out = []
    for cid in sorted(set(labels)):
        member_idx = [i for i, l in enumerate(labels) if l == cid]
        members = [agent_list[i] for i in member_idx]
        docs = [" ".join(m["texts"][:40]).lower() for m in members]
        freq = Counter()
        for d in docs:
            freq.update(w for w in d.split() if len(w) > 3)
        top_terms = [w for w, _ in freq.most_common(6)]
        sig = {
            "post_ratio": round(sum(m["post_ratio"] for m in members) / len(members), 3),
            "amplify_ratio": round(sum(m["amplify_ratio"] for m in members) / len(members), 3),
            "social_ratio": round(sum(m["social_ratio"] for m in members) / len(members), 3),
            "passive_ratio": round(sum(m["passive_ratio"] for m in members) / len(members), 3),
            "mean_sentiment": round(sum(m["mean_sentiment"] for m in members) / len(members), 3),
        }
        clusters_out.append({
            "id": int(cid),
            "size": len(members),
            "agent_ids": [agent_list[i]["agent_id"] for i in member_idx][:80],
            "label": _heuristic_label(members, top_terms),
            "top_terms": top_terms,
            "signature": sig,
        })
    return {"clusters": clusters_out, "n_clusters": n_clusters}
