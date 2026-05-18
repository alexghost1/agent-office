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

app = FastAPI(title="Mission Control — Oficina de Agentes IA")

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

_agents_cache = {}
_cache_lock = threading.Lock()
_last_refresh = 0

AGENT_MODULES = ["cortex", "hermes", "iris", "atlas", "herald", "forge", "nexus"]


def _load_agents():
    global _agents_cache, _last_refresh
    now = time.time()
    if now - _last_refresh < 5:
        return _agents_cache
    agents = {}
    for name in AGENT_MODULES:
        try:
            module = __import__(f"agents.{name}.agent", fromlist=["*"])
            cls_name = f"{name.capitalize()}Agent"
            agent_cls = getattr(module, cls_name)
            agents[name] = agent_cls()
        except Exception as e:
            agents[name] = None
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
        agent = agents.get(name)
        hs = health_statuses.get(name, {})
        ms = metrics_data.get(name, {})
        if agent is None:
            data.append({"name": name.upper(), "status": "error", "mode": "N/A", "health": "down",
                         "calls": 0, "errors": 0, "success_rate": 0, "avg_time": 0, "error_msg": "No disponible"})
        else:
            try:
                report = agent.report()
                h = hs.get("status", "unknown")
                data.append({
                    "name": name.upper(),
                    "status": report.get("status", "unknown"),
                    "mode": "🛡️ Sandbox" if report.get("sandbox") else "🚀 Producción",
                    "health": "healthy" if h == "healthy" else "degraded" if h == "degraded" else "unknown",
                    "calls": ms.get("calls", 0),
                    "errors": ms.get("errors", 0),
                    "success_rate": ms.get("success_rate", 100),
                    "avg_time": ms.get("avg_time", 0),
                    "error_msg": ms.get("last_error", ""),
                })
            except Exception as e:
                data.append({"name": name.upper(), "status": "error", "mode": "N/A", "health": "down",
                             "calls": 0, "errors": 0, "success_rate": 0, "avg_time": 0, "error_msg": str(e)[:60]})
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
    agents = _load_agents()
    a = agents.get(agent.lower())
    if not a:
        return JSONResponse({"status": "error", "error": f"Agente {agent} no encontrado"})
    try:
        result = a.run(task)
        result["agent"] = agent.upper()
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)})


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


def main():
    port = int(os.getenv("MISSION_CONTROL_PORT", "8080"))
    print(f"\n  🚀 MISSION CONTROL — http://localhost:{port}")
    print(f"  📡 API: http://localhost:{port}/api/agents")
    print(f"  Presiona Ctrl+C para detener\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
