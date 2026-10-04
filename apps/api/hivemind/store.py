"""SQLite persistence: projects, runs and a full event log per run.

The event log is the source of truth for timeline replay — scrubbing the
timeline and live reconnects both read from it, so replays never re-call
the LLM.
"""
import json
import sqlite3
import threading
import time
from typing import Any

from .config import get_settings


class Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.db = sqlite3.connect(
            get_settings().db_path, check_same_thread=False
        )
        self.db.row_factory = sqlite3.Row
        with self._lock, self.db:
            self.db.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects(
                    id TEXT PRIMARY KEY, name TEXT, question TEXT,
                    seed_text TEXT, status TEXT, created_at REAL,
                    agent_count INT DEFAULT 0, platform_count INT DEFAULT 0,
                    graph_json TEXT, personas_json TEXT, current_run_id TEXT
                );
                CREATE TABLE IF NOT EXISTS runs(
                    id TEXT PRIMARY KEY, project_id TEXT, status TEXT,
                    rounds INT, round_idx INT DEFAULT 0, seed INT,
                    speed REAL, created_at REAL, report_json TEXT,
                    summary_json TEXT
                );
                CREATE TABLE IF NOT EXISTS events(
                    run_id TEXT, seq INTEGER, type TEXT, payload TEXT,
                    PRIMARY KEY(run_id, seq)
                );
                CREATE TABLE IF NOT EXISTS chats(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT, scope TEXT, agent_id TEXT,
                    role TEXT, content TEXT, ts REAL
                );
                """
            )

    # ── projects ────────────────────────────────────────────────────────
    def put_project(self, p: dict) -> None:
        with self._lock, self.db:
            self.db.execute(
                """INSERT OR REPLACE INTO projects
                (id,name,question,seed_text,status,created_at,agent_count,
                 platform_count,graph_json,personas_json,current_run_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    p["id"], p["name"], p["question"], p["seedText"],
                    p["status"], p["createdAt"], p.get("agentCount", 0),
                    p.get("platformCount", 0),
                    json.dumps(p.get("graph")),
                    json.dumps(p.get("personas")),
                    p.get("currentRunId"),
                ),
            )

    def _row_to_project(self, r: sqlite3.Row, full: bool = True) -> dict:
        p: dict[str, Any] = {
            "id": r["id"], "name": r["name"], "question": r["question"],
            "seedText": r["seed_text"], "status": r["status"],
            "createdAt": r["created_at"], "agentCount": r["agent_count"],
            "platformCount": r["platform_count"],
            "currentRunId": r["current_run_id"],
        }
        if full:
            graph = json.loads(r["graph_json"]) if r["graph_json"] else None
            personas = json.loads(r["personas_json"]) if r["personas_json"] else None
            if graph:
                p["graph"] = graph
                p["graphSummary"] = {
                    "nodes": len(graph.get("nodes", [])),
                    "edges": len(graph.get("edges", [])),
                    "communities": len({n.get("community", 0) for n in graph.get("nodes", [])}),
                }
            if personas is not None:
                p["personas"] = personas
        return p

    def get_project(self, pid: str) -> dict | None:
        with self._lock:
            r = self.db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        return self._row_to_project(r) if r else None

    def list_projects(self) -> list[dict]:
        with self._lock:
            rows = self.db.execute(
                "SELECT * FROM projects ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_project(r, full=False) for r in rows]

    # ── runs ────────────────────────────────────────────────────────────
    def put_run(self, run: dict) -> None:
        with self._lock, self.db:
            self.db.execute(
                """INSERT OR REPLACE INTO runs
                (id,project_id,status,rounds,round_idx,seed,speed,created_at,
                 report_json,summary_json)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    run["id"], run["projectId"], run["status"], run["rounds"],
                    run.get("round", 0), run.get("seed", 42), run.get("speed", 1.5),
                    run.get("createdAt", time.time()),
                    json.dumps(run.get("report")) if run.get("report") else None,
                    json.dumps(run.get("summary")) if run.get("summary") else None,
                ),
            )

    def get_run(self, rid: str) -> dict | None:
        with self._lock:
            r = self.db.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
        if not r:
            return None
        run = {
            "id": r["id"], "projectId": r["project_id"], "status": r["status"],
            "rounds": r["rounds"], "round": r["round_idx"], "seed": r["seed"],
            "speed": r["speed"], "createdAt": r["created_at"],
            "report": json.loads(r["report_json"]) if r["report_json"] else None,
            "summary": json.loads(r["summary_json"]) if r["summary_json"] else None,
        }
        with self._lock:
            seq = self.db.execute(
                "SELECT COALESCE(MAX(seq),0) AS m FROM events WHERE run_id=?", (rid,)
            ).fetchone()["m"]
        run["seq"] = seq
        return run

    def put_report(self, rid: str, report: dict) -> None:
        with self._lock, self.db:
            self.db.execute(
                "UPDATE runs SET report_json=? WHERE id=?",
                (json.dumps(report), rid),
            )

    # ── event log ───────────────────────────────────────────────────────
    def max_seq(self, run_id: str) -> int:
        with self._lock:
            r = self.db.execute(
                "SELECT COALESCE(MAX(seq),0) AS m FROM events WHERE run_id=?", (run_id,)
            ).fetchone()
        return int(r["m"])

    def append_event(self, run_id: str, seq: int, type_: str, payload: dict) -> None:
        with self._lock, self.db:
            self.db.execute(
                "INSERT INTO events(run_id,seq,type,payload) VALUES(?,?,?,?)",
                (run_id, seq, type_, json.dumps(payload)),
            )

    def events_after(self, run_id: str, after: int = 0, limit: int = 100_000) -> list[dict]:
        with self._lock:
            rows = self.db.execute(
                "SELECT seq,type,payload FROM events WHERE run_id=? AND seq>? "
                "ORDER BY seq LIMIT ?",
                (run_id, after, limit),
            ).fetchall()
        return [
            {"seq": r["seq"], "type": r["type"], **json.loads(r["payload"])}
            for r in rows
        ]

    # ── chat history ────────────────────────────────────────────────────
    def add_chat(self, run_id: str, scope: str, agent_id: str | None,
                 role: str, content: str) -> None:
        with self._lock, self.db:
            self.db.execute(
                "INSERT INTO chats(run_id,scope,agent_id,role,content,ts)"
                " VALUES(?,?,?,?,?,?)",
                (run_id, scope, agent_id or "", role, content, time.time()),
            )


store = Store()
