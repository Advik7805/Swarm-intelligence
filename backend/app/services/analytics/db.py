"""
HiveMind Analytics — SQLite persistence
=======================================

Durable store for simulation analytics. Every run's scored posts, agents,
network metrics, persona clusters, sentiment timeline and prediction
confidence land here — powering the History dashboard and cross-run
comparisons without recompute.

Schema is created idempotently on first use. SQLite in WAL mode keeps
concurrent Flask threads safe. The DB file lives under backend/uploads/
(already git-ignored) so runs are reproducible from the action logs.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

_DEFAULT_PATH = os.path.join(
    os.path.dirname(__file__), "../../uploads/hivemind.db")

_LOCAL = threading.local()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    simulation_id TEXT PRIMARY KEY,
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL,
    status        TEXT NOT NULL DEFAULT 'analyzed',
    n_agents      INTEGER DEFAULT 0,
    n_rounds      INTEGER DEFAULT 0,
    n_posts       INTEGER DEFAULT 0,
    platforms     TEXT DEFAULT '',
    topic         TEXT DEFAULT '',
    sentiment_summary TEXT,
    network_summary   TEXT,
    confidence_summary TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);

CREATE TABLE IF NOT EXISTS posts (
    simulation_id TEXT NOT NULL,
    round         INTEGER NOT NULL,
    platform      TEXT,
    agent_id      INTEGER,
    agent_name    TEXT,
    post_id       TEXT,
    content       TEXT,
    like_count    INTEGER DEFAULT 0,
    sentiment_compound REAL,
    sentiment_positive REAL,
    sentiment_negative REAL,
    emotion       TEXT,
    intensity     REAL,
    PRIMARY KEY (simulation_id, post_id, round, agent_id)
);

CREATE TABLE IF NOT EXISTS agents (
    simulation_id TEXT NOT NULL,
    agent_id      INTEGER NOT NULL,
    name          TEXT,
    profession    TEXT,
    mbti          TEXT,
    country       TEXT,
    influence     REAL DEFAULT 0,
    pagerank      REAL DEFAULT 0,
    community_id  INTEGER DEFAULT -1,
    cluster_id    INTEGER DEFAULT -1,
    mean_sentiment REAL DEFAULT 0,
    PRIMARY KEY (simulation_id, agent_id)
);

CREATE TABLE IF NOT EXISTS network_metrics (
    simulation_id TEXT PRIMARY KEY,
    stats         TEXT,
    influencers   TEXT,
    communities   TEXT
);

CREATE TABLE IF NOT EXISTS clusters (
    simulation_id TEXT NOT NULL,
    cluster_id    INTEGER NOT NULL,
    label         TEXT,
    size          INTEGER,
    top_terms     TEXT,
    signature     TEXT,
    PRIMARY KEY (simulation_id, cluster_id)
);

CREATE TABLE IF NOT EXISTS confidence (
    simulation_id TEXT PRIMARY KEY,
    score         REAL,
    band          TEXT,
    factors       TEXT,
    detail        TEXT
);
"""


_SCHEMA_DONE = False


def _conn() -> sqlite3.Connection:
    global _SCHEMA_DONE
    conn = getattr(_LOCAL, "conn", None)
    if conn is None:
        os.makedirs(os.path.dirname(_db_path()), exist_ok=True)
        conn = sqlite3.connect(_db_path(), timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        _LOCAL.conn = conn
    if not _SCHEMA_DONE:
        conn.executescript(_SCHEMA)
        conn.commit()
        _SCHEMA_DONE = True
    return conn


def _db_path() -> str:
    return os.environ.get("HIVEMIND_DB_PATH", _DEFAULT_PATH)


class AnalyticsDB:
    """Thin data-access wrapper; one connection per thread."""

    # ------------------------------------------------------------- runs
    @staticmethod
    def upsert_run(simulation_id: str, n_agents: int = 0, n_rounds: int = 0,
                   n_posts: int = 0, platforms: str = "", topic: str = "",
                   sentiment_summary: Optional[Dict] = None,
                   network_summary: Optional[Dict] = None,
                   confidence_summary: Optional[Dict] = None) -> None:
        now = time.time()
        _conn().execute(
            """INSERT INTO runs (simulation_id, created_at, updated_at, status,
                n_agents, n_rounds, n_posts, platforms, topic,
                sentiment_summary, network_summary, confidence_summary)
               VALUES (?,?,?,'analyzed',?,?,?,?,?,?,?,?)
               ON CONFLICT(simulation_id) DO UPDATE SET
                 updated_at=excluded.updated_at, status='analyzed',
                 n_agents=excluded.n_agents, n_rounds=excluded.n_rounds,
                 n_posts=excluded.n_posts, platforms=excluded.platforms,
                 topic=excluded.topic,
                 sentiment_summary=excluded.sentiment_summary,
                 network_summary=excluded.network_summary,
                 confidence_summary=excluded.confidence_summary""",
            (simulation_id, now, now, n_agents, n_rounds, n_posts, platforms,
             topic,
             json.dumps(sentiment_summary or {}),
             json.dumps(network_summary or {}),
             json.dumps(confidence_summary or {})))
        _conn().commit()

    @staticmethod
    def get_run(simulation_id: str) -> Optional[Dict]:
        row = _conn().execute(
            "SELECT * FROM runs WHERE simulation_id=?",
            (simulation_id,)).fetchone()
        return AnalyticsDB._row_to_dict(row) if row else None

    @staticmethod
    def list_runs(limit: int = 50) -> List[Dict]:
        rows = _conn().execute(
            "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?",
            (limit,)).fetchall()
        return [AnalyticsDB._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------ posts
    @staticmethod
    def insert_posts(simulation_id: str, posts: List[Dict]) -> None:
        conn = _conn()
        conn.executemany(
            """INSERT OR REPLACE INTO posts
               (simulation_id, round, platform, agent_id, agent_name, post_id,
                content, like_count, sentiment_compound, sentiment_positive,
                sentiment_negative, emotion, intensity)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(simulation_id, p.get("round", 0), p.get("platform", ""),
              p.get("agent_id", 0), p.get("agent_name", ""),
              str(p.get("post_id", "")), p.get("content", "")[:2000],
              p.get("like_count", 0), p.get("sentiment_compound", 0),
              p.get("sentiment_positive", 0), p.get("sentiment_negative", 0),
              p.get("emotion", "neutral"), p.get("intensity", 0))
             for p in posts])
        conn.commit()

    @staticmethod
    def get_posts(simulation_id: str, limit: int = 2000) -> List[Dict]:
        rows = _conn().execute(
            """SELECT * FROM posts WHERE simulation_id=?
               ORDER BY round ASC LIMIT ?""",
            (simulation_id, limit)).fetchall()
        return [AnalyticsDB._row_to_dict(r) for r in rows]

    # ----------------------------------------------------------- agents
    @staticmethod
    def upsert_agents(simulation_id: str, agents: List[Dict]) -> None:
        conn = _conn()
        conn.executemany(
            """INSERT OR REPLACE INTO agents
               (simulation_id, agent_id, name, profession, mbti, country,
                influence, pagerank, community_id, cluster_id, mean_sentiment)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [(simulation_id, a["agent_id"], a.get("name"),
              a.get("profession"), a.get("mbti"), a.get("country"),
              a.get("influence", 0), a.get("pagerank", 0),
              a.get("community_id", -1), a.get("cluster_id", -1),
              a.get("mean_sentiment", 0)) for a in agents])
        conn.commit()

    @staticmethod
    def get_agents(simulation_id: str) -> List[Dict]:
        rows = _conn().execute(
            "SELECT * FROM agents WHERE simulation_id=? ORDER BY influence DESC",
            (simulation_id,)).fetchall()
        return [AnalyticsDB._row_to_dict(r) for r in rows]

    # --------------------------------------------------- network/others
    @staticmethod
    def save_network(simulation_id: str, stats: Dict, influencers: List,
                     communities: List) -> None:
        _conn().execute(
            """INSERT OR REPLACE INTO network_metrics
               (simulation_id, stats, influencers, communities)
               VALUES (?,?,?,?)""",
            (simulation_id, json.dumps(stats), json.dumps(influencers),
             json.dumps(communities)))
        _conn().commit()

    @staticmethod
    def save_clusters(simulation_id: str, clusters: List[Dict]) -> None:
        conn = _conn()
        conn.executemany(
            """INSERT OR REPLACE INTO clusters
               (simulation_id, cluster_id, label, size, top_terms, signature)
               VALUES (?,?,?,?,?,?)""",
            [(simulation_id, c["id"], c["label"], c["size"],
              json.dumps(c.get("top_terms", [])),
              json.dumps(c.get("signature", {}))) for c in clusters])
        conn.commit()

    @staticmethod
    def save_confidence(simulation_id: str, confidence: Dict) -> None:
        _conn().execute(
            """INSERT OR REPLACE INTO confidence
               (simulation_id, score, band, factors, detail)
               VALUES (?,?,?,?,?)""",
            (simulation_id, confidence.get("score", 0),
             confidence.get("band", "low"),
             json.dumps(confidence.get("factors", {})),
             json.dumps(confidence.get("detail", {}))))
        _conn().commit()

    # ------------------------------------------------------- accessors
    @staticmethod
    def get_network(simulation_id: str) -> Optional[Dict]:
        row = _conn().execute(
            "SELECT * FROM network_metrics WHERE simulation_id=?",
            (simulation_id,)).fetchone()
        if not row:
            return None
        d = AnalyticsDB._row_to_dict(row)
        for k in ("stats", "influencers", "communities"):
            d[k] = json.loads(d.get(k) or "{}")
        return d

    @staticmethod
    def get_clusters(simulation_id: str) -> List[Dict]:
        rows = _conn().execute(
            "SELECT * FROM clusters WHERE simulation_id=?",
            (simulation_id,)).fetchall()
        out = []
        for r in rows:
            d = AnalyticsDB._row_to_dict(r)
            d["top_terms"] = json.loads(d.get("top_terms") or "[]")
            d["signature"] = json.loads(d.get("signature") or "{}")
            out.append(d)
        return out

    @staticmethod
    def get_confidence(simulation_id: str) -> Optional[Dict]:
        row = _conn().execute(
            "SELECT * FROM confidence WHERE simulation_id=?",
            (simulation_id,)).fetchone()
        if not row:
            return None
        d = AnalyticsDB._row_to_dict(row)
        d["factors"] = json.loads(d.get("factors") or "{}")
        d["detail"] = json.loads(d.get("detail") or "{}")
        return d

    # ----------------------------------------------------------- utils
    @staticmethod
    def has_run(simulation_id: str) -> bool:
        return AnalyticsDB.get_run(simulation_id) is not None

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return {k: row[k] for k in row.keys()}
