"""Deep interaction: chat 1:1 with any simulated agent (in character,
grounded in its run memory) or with the ReportAgent over the report."""
import re
from typing import Any

from . import llm


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


_DEF_MEM_CAP = 40


def agent_memory_from_log(events: list[dict], agent_id: str) -> list[str]:
    out: list[str] = []
    for ev in events:
        if ev.get("type") == "round_batch":
            for a in ev.get("actions", []):
                if a.get("agentId") == agent_id:
                    out.append(f"R{a['round']}: I {a['action']}ed — “{a['text']}”")
                elif agent_id in a.get("targets", []):
                    out.append(f"R{a['round']}: {a.get('name','Someone')} {a['action']}d me — “{a['text']}”")
        elif ev.get("type") == "metrics":
            pass
        elif ev.get("type") == "event_injected":
            out.append(f"R{ev.get('tick','?')}: An event hit the world — “{ev.get('text','')}”")
    return out[-_DEF_MEM_CAP:]


def stance_label(s: float) -> str:
    if s > 0.5: return "strongly supportive"
    if s > 0.15: return "leaning supportive"
    if s < -0.5: return "strongly opposed"
    if s < -0.15: return "leaning opposed"
    return "broadly neutral"


def agent_chat(persona: dict, memory: list[str], message: str) -> str:
    name = persona.get("name", "Agent")
    system = (
        f"You are {name}, a {persona.get('archetype','')} in a completed social "
        f"simulation. Bio: {persona.get('bio','')} You are {stance_label(persona.get('stance',0))} "
        f"about the central topic. Answer in first person, in character, 2-4 short "
        f"sentences, plain English. Never reveal you are an AI."
    )
    recalled = "\n".join(f"- {m}" for m in _recall(memory, message, 8))
    if llm.mode() == "live":
        reply = llm.complete(system, f"Your memory from the simulation:\n{recalled}\n\n"
                                     f"Question from the observer: {message}", max_tokens=160)
        if reply:
            return reply
    # demo fallback: grounded template using real memory
    best = _recall(memory, message, 2)
    cite = f' I remember when {best[0].lower()}.' if best else ""
    return (
        f"As a {persona.get('archetype','observer')} I come out {stance_label(persona.get('stance',0))} "
        f"on this.{cite} Honestly, that's the view the swarm pushed me toward — "
        f"and I stand by it, roughly speaking."
    )


def report_chat(report: dict, message: str) -> str:
    q = _tokens(message)
    candidates: list[tuple[int, str]] = []
    for f in report.get("keyFindings", []):
        score = len(q & _tokens(f.get("claim", "")))
        ev = f.get("evidence", [])
        quote = f' — e.g. “{ev[0].get("quote","")}” (R{ev[0].get("round")})' if ev else ""
        candidates.append((score, f"{f.get('claim','')}{quote}"))
    for b in report.get("scenarioBranches", []):
        score = len(q & _tokens(b.get("name", "") + " " + b.get("outcome", "")))
        candidates.append((score, f"In the '{b.get('name')}' branch ({b.get('probability',0)*100:.0f}%): {b.get('outcome','')}"))
    candidates.sort(key=lambda c: -c[0])

    if llm.mode() == "live":
        import json
        reply = llm.complete(
            "You are the HIVE MIND ReportAgent. Answer questions about the prediction "
            "report faithfully and concisely (2-5 sentences), citing evidence when useful.",
            f"Report JSON:\n{json.dumps(report)[:4500]}\n\nQuestion: {message}",
            max_tokens=300,
        )
        if reply:
            return reply
    top = candidates[0][1] if candidates and candidates[0][0] > 0 else report.get("summary", "")
    extra = candidates[1][1] if len(candidates) > 1 and candidates[1][0] > 0 else ""
    return f"{top}{' ' + extra if extra else ''}"


def _recall(memory: list[str], query: str, k: int) -> list[str]:
    if not query.strip():
        return memory[-k:]
    q = _tokens(query)
    scored = sorted(memory, key=lambda m: len(q & _tokens(m)), reverse=True)
    top = [m for m in scored if len(q & _tokens(m)) > 0][:k]
    return top or memory[-k:]
