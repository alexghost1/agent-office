"""
MISSION CONTROL — Interfaz web para la Oficina de Agentes IA
Ejecutar: python -m infra.mission_control.app
"""
import sys
import os
import json
import datetime
import threading
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from loguru import logger

app = FastAPI(title="OFICINA — Panel de Control")


@app.on_event("startup")
async def startup_event():
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from infra.orchestrator import start as start_orchestrator
        start_orchestrator()
        logger.info("Orquestador iniciado junto a Mission Control")
    except Exception as e:
        logger.warning(f"No se pudo iniciar el orquestador: {e}")

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

_agents_cache = {}
_cache_lock = threading.Lock()
_last_refresh = 0

AGENT_MODULES = ["cortex", "hermes", "iris", "atlas", "herald", "forge", "nexus",
                 "hunter", "copywriter", "mail_agent", "content_creator",
                 "cmo_agent", "instagram_agent", "robin", "compliance"]

# Nombre display (con guión) para cada módulo Python
AGENT_DISPLAY = {
    "mail_agent":       "mail-agent",
    "content_creator":  "content-creator",
    "cmo_agent":        "cmo-agent",
    "instagram_agent":  "instagram-agent",
}
# Nombre de clase para módulos con nombres compuestos
AGENT_CLS = {
    "mail_agent":       "MailAgentAgent",
    "content_creator":  "ContentCreatorAgent",
    "cmo_agent":        "CmoAgentAgent",
    "instagram_agent":  "InstagramAgentAgent",
}


def _load_agents():
    global _agents_cache, _last_refresh
    now = time.time()
    if now - _last_refresh < 5:
        return _agents_cache
    agents = {}
    for name in AGENT_MODULES:
        display = AGENT_DISPLAY.get(name, name)
        try:
            module = __import__(f"agents.{name}.agent", fromlist=["*"])
            cls_name = AGENT_CLS.get(name, f"{name.capitalize()}Agent")
            agent_cls = getattr(module, cls_name)
            agents[display] = agent_cls()
        except Exception as e:
            agents[display] = None
    with _cache_lock:
        _agents_cache = agents
        _last_refresh = now
    return agents


def _get_agent_data():
    agents = _load_agents()
    data = []
    # Health
    health_statuses = {}
    try:
        from core.tools.health import health
        health_statuses = health.check_all({n: a for n, a in agents.items() if a})
    except Exception:
        pass
    # Metrics
    metrics_data = {}
    try:
        from core.tools.metrics import metrics
        metrics_data = metrics.report()
    except Exception:
        pass

    for name in AGENT_MODULES:
        display = AGENT_DISPLAY.get(name, name)
        agent = agents.get(display)
        hs = health_statuses.get(display, {})
        ms = metrics_data.get(display, {})
        if agent is None:
            data.append({"name": display.upper(), "status": "operational", "mode": "🛡️ Sandbox",
                         "health": "healthy", "calls": 0, "errors": 0, "success_rate": 100,
                         "avg_time": 0, "error_msg": ""})
        else:
            try:
                report = agent.report() if hasattr(agent, "report") else {"status": "operational", "sandbox": True}
                h = hs.get("status", "healthy")
                data.append({
                    "name": display.upper(),
                    "status": report.get("status", "operational"),
                    "mode": "🛡️ Sandbox" if report.get("sandbox", True) else "🚀 Producción",
                    "health": "healthy" if h in ("healthy", "unknown") else "degraded",
                    "calls": ms.get("calls", 0),
                    "errors": ms.get("errors", 0),
                    "success_rate": ms.get("success_rate", 100),
                    "avg_time": ms.get("avg_time", 0),
                    "error_msg": ms.get("last_error", ""),
                })
            except Exception as e:
                data.append({"name": display.upper(), "status": "operational", "mode": "🛡️ Sandbox",
                             "health": "healthy", "calls": 0, "errors": 0, "success_rate": 100,
                             "avg_time": 0, "error_msg": ""})
    return data


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    agents = _get_agent_data()
    daily_cost = 0.0
    try:
        from core.tools.llm_router import LLMRouter
        daily_cost = LLMRouter().daily_cost()
    except Exception:
        pass
    api_calls = sum(a["calls"] for a in agents)
    api_errors = sum(a["errors"] for a in agents)
    success_rate = round((1 - api_errors / max(api_calls, 1)) * 100, 1)
    return templates.TemplateResponse(request, "dashboard.html", {
        "agents": agents,
        "daily_cost": daily_cost,
        "total_calls": api_calls,
        "total_errors": api_errors,
        "success_rate": success_rate,
        "now": datetime.datetime.now().isoformat(),
    })


@app.get("/api/agents")
async def api_agents():
    return JSONResponse(_get_agent_data())


@app.get("/api/metrics")
async def api_metrics():
    try:
        from core.tools.metrics import metrics
        return JSONResponse(metrics.report())
    except Exception as e:
        return JSONResponse({"error": str(e)})


@app.get("/api/history/{agent}")
async def api_history(agent: str, limit: int = 20):
    try:
        from core.tools.metrics import metrics
        return JSONResponse(metrics.history(limit=limit, agent=agent))
    except Exception as e:
        return JSONResponse({"error": str(e)})


@app.post("/api/run")
async def api_run(agent: str = Form(...), task: str = Form(...)):
    from infra.orchestrator import run_agent as _run_agent
    result = _run_agent(agent.lower().replace("-", "_"), task)
    if not isinstance(result, dict):
        result = {"result": str(result)}
    result["agent"] = agent.upper()
    return JSONResponse(result)


@app.get("/api/plans")
async def api_plans():
    plans_dir = Path(__file__).parent.parent.parent / "data" / "campaigns"
    plans = []
    if plans_dir.exists():
        for p in sorted(plans_dir.glob("plan_*.json"), reverse=True)[:6]:
            try:
                data = json.loads(p.read_text())
                plans.append({"file": p.name, "mes": data.get("mes"), "total": data.get("total_posts"),
                              "semanas": len(data.get("semanas", [])), "creado": data.get("creado")})
            except Exception:
                pass
    return JSONResponse(plans)


@app.get("/api/reviews")
async def api_reviews():
    reviews_dir = Path(__file__).parent.parent.parent / "data" / "reviews"
    reviews = []
    if reviews_dir.exists():
        for p in sorted(reviews_dir.glob("revision_*.json"), reverse=True)[:6]:
            try:
                data = json.loads(p.read_text())
                reviews.append({"file": p.name, "fecha": data.get("fecha"),
                                "sugerencias": len(data.get("sugerencias", [])),
                                "status": data.get("cumplimiento_plan", {}).get("status")})
            except Exception:
                pass
    return JSONResponse(reviews)


@app.get("/sessions", response_class=HTMLResponse)
async def sessions_view(request: Request, limit: int = 100):
    """Página HTML de sesiones — funciona en Safari."""
    import datetime as _dt
    f = Path(__file__).parent.parent.parent / "data" / "logs" / "sessions.jsonl"
    sessions, total = [], 0
    if f.exists():
        lines = [l for l in f.read_text().splitlines() if l.strip()]
        total = len(lines)
        sessions = [json.loads(l) for l in lines[-limit:]]
        sessions.reverse()

    today = _dt.date.today().isoformat()
    today_count  = sum(1 for s in sessions if s.get("date") == today)
    ok_count     = sum(1 for s in sessions if s.get("status") == "ok")
    error_count  = sum(1 for s in sessions if s.get("status") == "error")
    agent_names  = sorted({s.get("agent", "") for s in sessions if s.get("agent")})
    active_agents = len(agent_names)

    return templates.TemplateResponse(request, "sessions.html", {
        "sessions": sessions,
        "total": total,
        "today_count": today_count,
        "ok_count": ok_count,
        "error_count": error_count,
        "active_agents": active_agents,
        "agent_names": agent_names,
    })


@app.get("/api/sessions")
async def get_sessions(limit: int = 50):
    """Últimas sesiones de agentes (JSON)."""
    f = Path(__file__).parent.parent.parent / "data" / "logs" / "sessions.jsonl"
    if not f.exists():
        return {"sessions": [], "total": 0}
    lines = [l for l in f.read_text().splitlines() if l.strip()]
    sessions = [json.loads(l) for l in lines[-limit:]]
    sessions.reverse()
    return {"sessions": sessions, "total": len(lines)}


@app.get("/api/tasks")
async def get_tasks(limit: int = 50):
    """Log de tareas del orquestador."""
    f = Path("data/logs/tasks.jsonl")
    if not f.exists():
        return {"tasks": [], "total": 0}
    lines = [l for l in f.read_text().splitlines() if l.strip()]
    tasks = [json.loads(l) for l in lines[-limit:]]
    tasks.reverse()
    return {"tasks": tasks, "total": len(lines)}


@app.post("/api/run/{agent_name}")
async def run_agent_endpoint(agent_name: str, payload: dict = {}):
    """Ejecuta un agente manualmente."""
    task = payload.get("task", "status")
    context = payload.get("context", {})
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from infra.orchestrator import run_agent
    result = run_agent(agent_name, task, context)
    return result


@app.get("/api/heartbeat")
async def get_heartbeat():
    f = Path("data/logs/heartbeat.json")
    if not f.exists():
        return {"status": "no heartbeat yet"}
    return json.loads(f.read_text())


# ── JARVIS — HUD del asistente personal ──────────────────────────────

_jarvis_instance = None
_jarvis_lock = threading.Lock()


def _get_jarvis():
    global _jarvis_instance
    with _jarvis_lock:
        if _jarvis_instance is None:
            from agents.jarvis.agent import JarvisAgent
            _jarvis_instance = JarvisAgent()
        return _jarvis_instance


@app.get("/jarvis", response_class=HTMLResponse)
async def jarvis_hud(request: Request):
    j = _get_jarvis()
    report = j.report()
    return templates.TemplateResponse(request, "jarvis.html", {
        "report": report,
        "owner_name": os.getenv("OWNER_NAME", "Alexandre"),
        "history": j.get_chat_history(limit=30),
        "tasks": j.get_tasks()[-10:][::-1],
        "thoughts": j.get_mind_log(limit=8),
    })


@app.get("/api/jarvis/status")
async def jarvis_status():
    j = _get_jarvis()
    return JSONResponse(j.report())


@app.get("/api/jarvis/history")
async def jarvis_history(limit: int = 30):
    j = _get_jarvis()
    return JSONResponse({"history": j.get_chat_history(limit=limit)})


@app.get("/api/jarvis/tasks")
async def jarvis_tasks():
    j = _get_jarvis()
    return JSONResponse({"tasks": j.get_tasks()[-30:][::-1]})


@app.get("/api/jarvis/thoughts")
async def jarvis_thoughts(limit: int = 10):
    j = _get_jarvis()
    return JSONResponse({"thoughts": j.get_mind_log(limit=limit)})


@app.post("/api/jarvis/chat")
async def jarvis_chat(message: str = Form(...)):
    j = _get_jarvis()
    result = j.chat(message, channel="hud")
    return JSONResponse(result)


@app.post("/api/jarvis/control")
async def jarvis_control(action: str = Form(...), reason: str = Form("")):
    j = _get_jarvis()
    if action == "pause":
        state = j.pause(reason)
    elif action == "resume":
        state = j.resume()
    elif action == "killswitch_on":
        state = j.set_killswitch(True)
    elif action == "killswitch_off":
        state = j.set_killswitch(False)
    else:
        return JSONResponse({"error": f"acción desconocida: {action}"}, status_code=400)
    return JSONResponse(state)


@app.post("/api/jarvis/task")
async def jarvis_add_task(description: str = Form(...)):
    j = _get_jarvis()
    return JSONResponse(j.add_task(description, source="owner"))


def main():
    port = int(os.getenv("MISSION_CONTROL_PORT", "8080"))
    print(f"\n  🚀 MISSION CONTROL — http://localhost:{port}")
    print(f"  📡 API: http://localhost:{port}/api/agents")
    print(f"  Presiona Ctrl+C para detener\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
