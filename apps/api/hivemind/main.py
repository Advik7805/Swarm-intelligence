"""HIVE MIND API — FastAPI entrypoint. REST under /api, simulation stream at /ws."""
import asyncio
import base64
import time
import uuid

from fastapi import FastAPI, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import chat, graphrag, llm, personas as personas_mod, reporter
from .config import get_settings
from .engine import engines, get_bus, start_engine
from .ingest import combine, extract_file
from .models import (BuildRequest, ChatReply, ChatRequest, ControlRequest,
                     Project, RunStatus, SimulateRequest)
from .store import store

app = FastAPI(title="HIVE MIND API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def _err(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"error": message})


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {
        "ok": True,
        "service": "hive-mind",
        "llm": llm.mode(),
        "model": ("demo-pack" if llm.mode() == "demo"
                  else s.ollama_model or s.llm_model_name or "openai-compatible"),
    }


# ── projects ─────────────────────────────────────────────────────────────
@app.post("/api/projects", status_code=201)
async def create_project(request: Request) -> dict:
    """Accepts JSON {name, question, seedText} or multipart multipart/form-data
    with the same fields plus up to 8 files (pdf/txt/md/csv)."""
    content_type = request.headers.get("content-type", "")
    files: list[tuple[str, bytes]] = []
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        name, question = str(form.get("name", "")), str(form.get("question", ""))
        seed_text = str(form.get("seedText", ""))
        for item in form.getlist("files"):
            if isinstance(item, UploadFile):
                files.append((item.filename or "file", await item.read()))
        files = files[:8]
    else:
        body = await request.json()
        name, question = body.get("name", ""), body.get("question", "")
        seed_text = body.get("seedText", "")
        for f in body.get("files", [])[:8]:  # optional: [{name, contentBase64}]
            try:
                files.append((f["name"], base64.b64decode(f["contentBase64"])))
            except Exception:
                continue
    if not name.strip() or not question.strip():
        raise _err(422, "Both 'name' and 'question' are required.")
    try:
        seed = combine(seed_text, files)
    except ValueError as e:
        raise _err(422, str(e))
    project = {
        "id": uuid.uuid4().hex[:12],
        "name": name.strip()[:120],
        "question": question.strip()[:500],
        "seedText": seed[:200_000],
        "status": "created",
        "createdAt": time.time(),
    }
    store.put_project(project)
    return {"id": project["id"], "status": "created"}


@app.get("/api/projects")
def list_projects() -> list[dict]:
    return store.list_projects()


@app.get("/api/projects/{pid}")
def get_project(pid: str) -> dict:
    p = store.get_project(pid)
    if not p:
        raise _err(404, "project not found")
    return p


@app.post("/api/projects/{pid}/build")
def build_world(pid: str, req: BuildRequest) -> dict:
    p = store.get_project(pid)
    if not p:
        raise _err(404, "project not found")
    p["status"] = "building"
    store.put_project(p)
    try:
        graph = graphrag.build_graph(p["seedText"], req.seed)
        agent_personas = personas_mod.generate_personas(
            graph, req.agentCount, req.platformCount, req.seed)
        p.update({
            "status": "built", "graph": graph, "personas": agent_personas,
            "agentCount": len(agent_personas), "platformCount": req.platformCount,
        })
        store.put_project(p)
        return {"status": "built", "agents": len(agent_personas),
                "nodes": len(graph["nodes"]), "edges": len(graph["edges"])}
    except Exception as e:
        p["status"] = "failed"
        store.put_project(p)
        raise _err(500, f"build failed: {e}")


@app.post("/api/projects/{pid}/simulate", status_code=202)
async def simulate(pid: str, req: SimulateRequest) -> dict:
    p = store.get_project(pid)
    if not p:
        raise _err(404, "project not found")
    if p["status"] != "built" or not p.get("personas"):
        raise _err(409, "project must be built before simulation")
    run = {
        "id": uuid.uuid4().hex[:12], "projectId": pid, "status": "queued",
        "rounds": req.rounds, "round": 0, "seed": req.seed, "speed": req.speed,
        "createdAt": time.time(),
    }
    await start_engine(run, p)
    p["status"] = "simulating"
    p["currentRunId"] = run["id"]
    store.put_project(p)
    return {"runId": run["id"], "mode": llm.mode()}


# ── runs ─────────────────────────────────────────────────────────────────
@app.get("/api/runs/{rid}")
def run_status(rid: str) -> RunStatus:
    run = store.get_run(rid)
    if not run:
        raise _err(404, "run not found")
    return RunStatus(
        runId=rid, projectId=run["projectId"], status=run["status"],
        round=run.get("round", 0), rounds=run["rounds"], seq=run["seq"],
        mode=llm.mode(), hasReport=bool(run.get("report")),
    )


@app.post("/api/runs/{rid}/control")
async def control(rid: str, req: ControlRequest) -> dict:
    engine = engines.get(rid)
    if not engine:
        raise _err(409, "run is not live on this server (finished or restarted); "
                        "the event log remains fully replayable")
    if req.action == "pause":
        await engine.pause()
    elif req.action == "resume":
        await engine.extend(req.rounds or 20)
    elif req.action == "stop":
        await engine.stop()
    elif req.action == "setSpeed" and req.speed:
        await engine.set_speed(req.speed)
    elif req.action == "injectEvent":
        if not req.text or not req.text.strip():
            raise _err(422, "injectEvent requires 'text'")
        await engine.inject(req.text.strip())
    return {"ok": True}


# ── report ───────────────────────────────────────────────────────────────
@app.post("/api/runs/{rid}/report", status_code=202)
def generate_report(rid: str) -> dict:
    run = store.get_run(rid)
    if not run:
        raise _err(404, "run not found")
    if run.get("report"):
        return run["report"]
    if run.get("round", 0) < 1:
        raise _err(409, "run needs at least 1 completed round before reporting")
    project = store.get_project(run["projectId"])
    if not project:
        raise _err(404, "project not found")
    bus = get_bus(rid)
    bus.publish("report_progress", {"stage": "collecting"})
    report = reporter.generate(rid, run, project)
    bus.publish("report_progress", {"stage": "writing"})
    store.put_report(rid, report)
    return report


@app.get("/api/runs/{rid}/report")
def get_report(rid: str) -> dict:
    run = store.get_run(rid)
    if not run:
        raise _err(404, "run not found")
    if not run.get("report"):
        raise _err(404, "no report yet — POST /api/runs/{rid}/report first")
    return run["report"]


# ── deep interaction ─────────────────────────────────────────────────────
@app.post("/api/runs/{rid}/chat/agent/{agent_id}")
def chat_with_agent(rid: str, agent_id: str, req: ChatRequest) -> ChatReply:
    run = store.get_run(rid)
    if not run:
        raise _err(404, "run not found")
    project = store.get_project(run["projectId"])
    if not project:
        raise _err(404, "project not found")
    personas = (run.get("summary") or {}).get("personas") or project.get("personas") or []
    persona = next((p for p in personas if p["id"] == agent_id), None)
    if not persona:
        raise _err(404, "agent not found in this run")
    events = store.events_after(rid)
    memory = chat.agent_memory_from_log(events, agent_id)
    reply = chat.agent_chat(persona, memory, req.message)
    store.add_chat(rid, "agent", agent_id, "user", req.message)
    store.add_chat(rid, "agent", agent_id, "assistant", reply)
    return ChatReply(reply=reply, agentId=agent_id)


@app.post("/api/runs/{rid}/chat/report")
def chat_with_report(rid: str, req: ChatRequest) -> ChatReply:
    run = store.get_run(rid)
    if not run:
        raise _err(404, "run not found")
    if not run.get("report"):
        raise _err(404, "no report yet — generate it first")
    reply = chat.report_chat(run["report"], req.message)
    store.add_chat(rid, "report", None, "user", req.message)
    store.add_chat(rid, "report", None, "assistant", reply)
    return ChatReply(reply=reply)


@app.get("/api/runs/{rid}/agents/{agent_id}/memory")
def agent_memory(rid: str, agent_id: str) -> dict:
    run = store.get_run(rid)
    if not run:
        raise _err(404, "run not found")
    events = store.events_after(rid)
    memory = chat.agent_memory_from_log(events, agent_id)
    # stance-per-round trace for the sparkline
    by_round: dict[int, list[float]] = {}
    for ev in events:
        if ev.get("type") == "round_batch":
            for a in ev.get("actions", []):
                if a.get("agentId") == agent_id:
                    by_round.setdefault(a["round"], []).append(a["sentiment"])
    trace = [{"round": r, "sentiment": round(sum(v) / len(v), 3)}
             for r, v in sorted(by_round.items())]
    return {"memory": memory, "stanceTrace": trace}


# ── websocket stream ─────────────────────────────────────────────────────
@app.websocket("/ws/runs/{rid}")
async def ws_run(ws: WebSocket, rid: str, after: int = 0) -> None:
    await ws.accept()
    run = store.get_run(rid)
    if not run:
        await ws.send_json({"type": "error", "runId": rid, "message": "run not found"})
        await ws.close()
        return
    # 1) replay persisted events (timeline/reconnect correctness)
    for ev in store.events_after(rid, after=after):
        await ws.send_json(ev)
    live_states = {"queued", "running", "paused"}
    if run["status"] in live_states:
        bus = get_bus(rid)
        q = bus.subscribe()
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=30.0)
                    await ws.send_json(msg)
                except asyncio.TimeoutError:
                    await ws.send_json({"type": "ping", "runId": rid, "ts": time.time()})
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            bus.unsubscribe(q)


@app.on_event("startup")
def banner() -> None:
    print(f"\n  HIVE MIND api up — LLM mode: {llm.mode()}  "
          f"(db: {get_settings().db_path})\n")
