"""Per-agent memory: short-term event window + salient long-term entries,
with token-overlap retrieval for grounding actions and 1:1 chat."""
import re
from collections import deque


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


class AgentMemory:
    def __init__(self, short_size: int = 24):
        self.short: deque[str] = deque(maxlen=short_size)
        self.long: list[str] = []

    def add(self, entry: str, salient: bool = False) -> None:
        self.short.append(entry)
        if salient or len(self.short) == self.short.maxlen:
            self.long.append(entry)

    def recall(self, query: str = "", k: int = 8) -> list[str]:
        all_entries = list(self.short) + self.long
        if not query:
            return all_entries[-k:]
        q = _tokens(query)
        scored = sorted(all_entries, key=lambda e: len(q & _tokens(e)), reverse=True)
        top = [e for e in scored[:k]]
        seen, out = set(), []
        for e in top:
            if e not in seen:
                seen.add(e)
                out.append(e)
        return out


class MemoryBank:
    def __init__(self):
        self._mem: dict[str, AgentMemory] = {}

    def get(self, agent_id: str) -> AgentMemory:
        if agent_id not in self._mem:
            self._mem[agent_id] = AgentMemory()
        return self._mem[agent_id]

    def to_dict(self, agent_id: str) -> dict:
        m = self.get(agent_id)
        return {"short": list(m.short), "long": m.long[-40:]}
