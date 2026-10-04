"""GraphRAG: seed text → entity graph (networkx) with community detection.

Demo mode extracts entities heuristically (capitalized phrases + frequent
content words); live mode can ask the LLM for entities. Both paths emit the
same JSON contract consumed by the frontend force-graph and the engine.
"""
import random
import re
from collections import Counter

import networkx as nx

from . import llm
from .demo import GENERIC_TOPICS

STOP = set("""the a an and or but of to in on for with from by at as is are was were be been
being it its this that these those we you they he she i not no do does did done have has had
will would can could should may might must about into over under more most other some any
new says said also after before between during their there here what when where which who how
all each one two three out up down so if then than too very just whether however because
through toward within without across against per via off both next last first second every
never always often maybe perhaps likely unlikely really actually nearly almost quite rather
opening opens been got gets make makes made take takes call calls calling much many few
hours minutes days weeks months year years ago later inside outside above below""".split())

CAP_PHRASE = re.compile(r"\b([A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*){0,2})\b")


def _extract_entities_demo(text: str, rng: random.Random) -> list[str]:
    caps = [p.strip() for p in CAP_PHRASE.findall(text) if len(p.strip()) > 2]
    words = re.findall(r"[a-zA-Z][a-z\-]{4,}", text.lower())
    freq = Counter(w for w in words if w not in STOP and not w.endswith("ing"))
    ents = list(dict.fromkeys(caps))  # order-preserving dedupe
    ents += [w for w, _ in freq.most_common(15)]
    seen, out = set(), []
    for e in ents:
        k = e.lower()
        if k not in seen and len(e) < 40:
            seen.add(k)
            out.append(e)
    rng.shuffle(out)
    pad = [t for t in GENERIC_TOPICS if t.lower() not in seen]
    out.extend(pad[: max(0, 14 - len(out))])
    return out[:16]


def _extract_entities_live(text: str) -> list[str] | None:
    result = llm.complete_json(
        "You extract entities for a knowledge graph. Return JSON: "
        '{"entities":["...", up to 16 short entity/topic names present in the text]}',
        text[:6000],
        max_tokens=400,
    )
    if result and isinstance(result.get("entities"), list) and result["entities"]:
        return [str(e)[:40] for e in result["entities"]][:16]
    return None


def build_graph(seed_text: str, seed: int) -> dict:
    """Nodes = extracted entities; edges = sentence-level co-occurrence."""
    rng = random.Random(seed)
    entities = None if llm.mode() == "demo" else _extract_entities_live(seed_text)
    if not entities:
        entities = _extract_entities_demo(seed_text, rng)

    sentences = re.split(r"[.!?\n]", seed_text) or [seed_text]
    g = nx.Graph()
    for i, e in enumerate(entities):
        g.add_node(i, label=e, community=0, weight=1)

    def mentions(s: str, e: str) -> bool:
        return e.lower() in s.lower()

    for si, s in enumerate(sentences):
        present = [i for i, e in enumerate(entities) if mentions(s, e)]
        for a in range(len(present)):
            g.nodes[present[a]]["weight"] += 1
            for b in range(a + 1, len(present)):
                ua, ub = present[a], present[b]
                if g.has_edge(ua, ub):
                    g[ua][ub]["weight"] += 1
                else:
                    g.add_edge(ua, ub, weight=1)

    # Guarantee connectivity: link isolates to their nearest topical neighbor
    deg = dict(g.degree())
    iso = [n for n in g.nodes if deg.get(n, 0) == 0]
    hubs = sorted(g.nodes, key=lambda n: -deg.get(n, 0))[:4] or list(g.nodes)[:1]
    for n in iso:
        if hubs and n != hubs[0]:
            g.add_edge(n, rng.choice(hubs), weight=1)

    for i, community in enumerate(nx.community.greedy_modularity_communities(g, weight="weight")):
        for n in community:
            g.nodes[n]["community"] = i

    nodes = [
        {"id": int(n), "label": g.nodes[n]["label"],
         "community": int(g.nodes[n]["community"]), "weight": int(g.nodes[n]["weight"])}
        for n in g.nodes
    ]
    edges = [
        {"a": int(u), "b": int(v), "w": int(d.get("weight", 1))}
        for u, v, d in g.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}


def node_labels(graph: dict) -> list[str]:
    return [n["label"] for n in graph.get("nodes", [])]


def retrieve_context(graph: dict, query: str, k: int = 6) -> str:
    """Lightweight GraphRAG retrieval: entities sharing tokens with query,
    plus their connected neighbors."""
    q = set(re.findall(r"[a-z]{3,}", query.lower()))
    nodes = graph.get("nodes", [])
    adjacency: dict[int, list[int]] = {n["id"]: [] for n in nodes}
    for e in graph.get("edges", []):
        adjacency[e["a"]].append(e["b"])
        adjacency[e["b"]].append(e["a"])

    scored = []
    for n in nodes:
        label = n["label"].lower()
        overlap = len(q & set(re.findall(r"[a-z]{3,}", label)))
        scored.append((overlap * 10 + n.get("weight", 1), n))
    scored.sort(key=lambda t: -t[0])
    picked = [n for _, n in scored[:k]]
    lines = []
    for n in picked:
        neigh = [nodes[j]["label"] for j in adjacency.get(n["id"], [])[:4] if j < len(nodes)]
        rel = f" — linked to: {', '.join(neigh)}" if neigh else ""
        lines.append(f"{n['label']}{rel}")
    return "\n".join(lines)
