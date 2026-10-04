"""Shared pydantic schemas for the REST API and the WebSocket event stream."""
from typing import Any, Literal
from pydantic import BaseModel, Field

Status = Literal["created", "building", "built", "simulating", "complete", "failed"]
RunState = Literal["queued", "running", "paused", "stopped", "reporting", "complete", "failed"]


# ── Requests ────────────────────────────────────────────────────────────────
class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    question: str = Field(min_length=1, max_length=500)
    seedText: str = ""


class BuildRequest(BaseModel):
    agentCount: int = Field(default=60, ge=10, le=500)
    platformCount: int = Field(default=2, ge=1, le=2)
    seed: int = 42


class SimulateRequest(BaseModel):
    rounds: int = Field(default=25, ge=5, le=200)
    speed: float = Field(default=1.5, gt=0, le=100)  # rounds per second
    seed: int = 42


class ControlRequest(BaseModel):
    action: Literal["pause", "resume", "stop", "setSpeed", "injectEvent"]
    speed: float | None = Field(default=None, gt=0, le=100)
    text: str | None = Field(default=None, max_length=500)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


# ── Domain ──────────────────────────────────────────────────────────────────
class Persona(BaseModel):
    id: str
    name: str
    archetype: str
    bio: str
    goals: list[str]
    interests: list[str] = []
    stance: float = 0.0
    openness: float = 0.5
    aggression: float = 0.5
    followers: int = 100
    platform: str = "Arena A"
    faction: int = 0


class Project(BaseModel):
    id: str
    name: str
    question: str
    seedText: str
    status: Status = "created"
    createdAt: float
    agentCount: int = 0
    platformCount: int = 0
    graphSummary: dict[str, Any] | None = None
    personas: list[Persona] | None = None
    currentRunId: str | None = None


class RunStatus(BaseModel):
    runId: str
    projectId: str
    status: RunState
    round: int = 0
    rounds: int = 0
    seq: int = 0
    mode: str = "demo"
    hasReport: bool = False


class Report(BaseModel):
    summary: str = ""
    overallPrediction: str = ""
    confidence: float = 0.0
    keyFindings: list[dict[str, Any]] = []
    scenarioBranches: list[dict[str, Any]] = []
    injectableSuggestions: list[str] = []
    topAgents: list[dict[str, Any]] = []
    meta: dict[str, Any] = {}


class ChatReply(BaseModel):
    reply: str
    agentId: str | None = None


# ── WebSocket event types (payloads are JSON dicts on the wire) ─────────────
# round_started   {runId, round, rounds}
# round_batch     {runId, round, actions:[AgentAction...]}
#   AgentAction   {id, agentId, name, faction, platform, action, sentiment,
#                  text, targets[], influence, round}
# metrics         {runId, round, sentimentAvg, activityCount,
#                  factionShares{}, topInfluencers[{}]}
# event_injected  {runId, tick, text}
# report_progress {runId, stage}
# run_complete    {runId, summary{}}
# error           {runId, message}
