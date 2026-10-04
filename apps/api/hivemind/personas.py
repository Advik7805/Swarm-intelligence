"""Persona generation: spawn N agents grounded in the seed knowledge graph."""
import random
import uuid

from .demo import ARCHETYPES, BIO_TEMPLATES, FIRST, GOALS, LAST


def _pick_archetype(rng: random.Random) -> str:
    names = [a for a, _ in ARCHETYPES]
    weights = [w for _, w in ARCHETYPES]
    return rng.choices(names, weights=weights, k=1)[0]


def generate_personas(graph: dict, count: int, platforms: int, seed: int) -> list[dict]:
    rng = random.Random(seed * 7919 + count)
    labels = [n["label"] for n in graph.get("nodes", [])] or ["the situation"]
    # Community sentiment bias: communities get a leaning, personas inherit it
    communities = sorted({n.get("community", 0) for n in graph.get("nodes", [])})
    lean = {c: rng.uniform(-0.55, 0.55) for c in communities}
    node_comm = {n["id"]: n.get("community", 0) for n in graph.get("nodes", [])}

    used: set[str] = set()
    personas: list[dict] = []
    for i in range(count):
        while True:
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            if name not in used:
                used.add(name)
                break
        arch = _pick_archetype(rng)
        i1, i2 = rng.sample(labels, k=2) if len(labels) >= 2 else (labels[0], labels[0])
        node_ids = rng.sample(range(len(graph.get("nodes", []))),
                              k=min(3, len(graph.get("nodes", [])))) or [0]
        comm = node_comm.get(node_ids[0], 0)
        stance = max(-1.0, min(1.0, rng.gauss(lean.get(comm, 0.0), 0.3)))
        goals = rng.sample(GOALS, k=2)
        personas.append({
            "id": uuid.uuid4().hex[:10],
            "name": name,
            "archetype": arch,
            "bio": rng.choice(BIO_TEMPLATES).format(arch=arch, i1=i1, i2=i2),
            "goals": goals,
            "interests": sorted({i1, i2}),
            "stance": round(stance, 3),
            "openness": round(rng.uniform(0.15, 0.95), 3),
            "aggression": round(rng.uniform(0.05, 0.9), 3),
            "followers": int(max(40, rng.lognormvariate(6.4, 0.9))),
            "platform": f"Arena {'A' if i % platforms == 0 else 'B'}" if platforms == 2 else "Arena A",
            "faction": int(comm),
        })
    return personas
