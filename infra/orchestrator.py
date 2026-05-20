"""
Orquestador de la Oficina — mantiene los agentes activos y ejecuta tareas periódicas
"""
from __future__ import annotations
import json
import time
import datetime
import threading
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

BASE_DIR  = Path(__file__).parent.parent
LOGS_DIR  = BASE_DIR / "data" / "logs"
TASKS_DIR = BASE_DIR / "data" / "tasks"
TASKS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

SESSIONS_FILE = LOGS_DIR / "sessions.jsonl"
TASKS_FILE    = LOGS_DIR / "tasks.jsonl"


def _log_session(agent: str, task: str, result: dict):
    """Persiste cada ejecución de agente."""
    entry = {
        "ts": datetime.datetime.now().isoformat(),
        "date": datetime.date.today().isoformat(),
        "agent": agent,
        "task": task[:120],
        "status": result.get("status", "unknown"),
        "summary": str(result)[:300],
    }
    with open(SESSIONS_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _log_task(task_name: str, status: str, detail: str = ""):
    entry = {
        "ts": datetime.datetime.now().isoformat(),
        "task": task_name,
        "status": status,
        "detail": detail[:200],
    }
    with open(TASKS_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_agent(agent_name: str, task: str, context: dict = None) -> dict:
    """Importa y ejecuta un agente, loguea la sesión."""
    try:
        import importlib, sys
        sys.path.insert(0, str(BASE_DIR))
        mod = importlib.import_module(f"agents.{agent_name}.agent")
        # Find the agent class (first class that ends in 'Agent')
        agent_class = None
        for name in dir(mod):
            obj = getattr(mod, name)
            if isinstance(obj, type) and name.endswith("Agent") and name != "Agent":
                agent_class = obj
                break
        if not agent_class:
            raise ValueError(f"No Agent class found in agents.{agent_name}.agent")
        agent_obj = agent_class()
        result = agent_obj.run(task, context or {})
        _log_session(agent_name, task, result if isinstance(result, dict) else {"result": str(result)})
        logger.info(f"[{agent_name}] ✅ {task[:50]}")
        return result if isinstance(result, dict) else {"status": "ok", "result": str(result)}
    except Exception as e:
        err = {"status": "error", "error": str(e)}
        _log_session(agent_name, task, err)
        logger.error(f"[{agent_name}] ❌ {e}")
        return err


# ── Tareas periódicas ─────────────────────────────────────────

def _morning_routine():
    """07:00 — briefing de mercados, leads y monitoreo Instagram."""
    logger.info("🌅 Morning routine")
    _log_task("morning_routine", "started")

    # ATLAS — noticias financieras
    run_agent("atlas", "resumen de noticias financieras y de mercados de hoy para banca privada España")

    # IRIS — monitoreo diario de las 100 cuentas Instagram vigiladas
    run_agent("iris", "monitoreo diario watchlist instagram: digest de las 100 cuentas")

    # HUNTER — buscar leads nuevos
    run_agent("hunter", "buscar leads potenciales: empresarios y familias con patrimonio en Tarragona y Costa Dorada")

    # CORTEX — guardar en memoria
    run_agent("cortex", "store morning briefing completed", {"agent": "orchestrator", "event_type": "morning_routine", "data": {"date": datetime.date.today().isoformat()}})

    _log_task("morning_routine", "done")


def _midday_routine():
    """13:00 — revisión de contenido y leads."""
    logger.info("☀️ Midday routine")
    _log_task("midday_routine", "started")

    # IRIS — estado de contenido Instagram
    run_agent("iris", "revisar estado del plan de contenido y próximas publicaciones pendientes")

    # HERMES — revisar leads pendientes de contacto
    run_agent("hermes", "revisar leads pendientes y generar mensajes de seguimiento")

    _log_task("midday_routine", "done")


def _evening_routine():
    """20:00 — resumen del día."""
    logger.info("🌙 Evening routine")
    _log_task("evening_routine", "started")

    # CORTEX — reporte diario
    run_agent("cortex", "daily report resumen de actividad del día")

    # Nexus: lightweight summary only (no full agent orchestration)
    run_agent("nexus", "resumen ligero: cuántas sesiones se ejecutaron hoy y coste total API")

    _log_task("evening_routine", "done")


def _heartbeat():
    """Cada 30 min — mantener sistema vivo y guardar estado."""
    logger.debug("💓 Heartbeat")
    entry = {
        "ts": datetime.datetime.now().isoformat(),
        "status": "alive",
        "agents": ["atlas", "cortex", "forge", "herald", "hermes", "hunter", "iris", "nexus"],
    }
    hb_file = LOGS_DIR / "heartbeat.json"
    hb_file.write_text(json.dumps(entry, indent=2))


# ── Scheduler loop ────────────────────────────────────────────

def _scheduler_loop():
    ran_today: set[str] = set()
    last_heartbeat = 0.0

    logger.info("🚀 Orquestador iniciado")

    while True:
        now   = datetime.datetime.now()
        today = now.date().isoformat()
        hour  = now.hour
        minute = now.minute

        # Reset diario
        if today not in ran_today:
            ran_today = {today}

        # Heartbeat cada 30 min
        if time.time() - last_heartbeat > 1800:
            _heartbeat()
            last_heartbeat = time.time()

        # Morning 07:00
        if hour == 7 and minute < 5 and f"morning_{today}" not in ran_today:
            ran_today.add(f"morning_{today}")
            threading.Thread(target=_morning_routine, daemon=True).start()

        # Midday 13:00
        if hour == 13 and minute < 5 and f"midday_{today}" not in ran_today:
            ran_today.add(f"midday_{today}")
            threading.Thread(target=_midday_routine, daemon=True).start()

        # Evening 20:00
        if hour == 20 and minute < 5 and f"evening_{today}" not in ran_today:
            ran_today.add(f"evening_{today}")
            threading.Thread(target=_evening_routine, daemon=True).start()

        time.sleep(60)


def start():
    t = threading.Thread(target=_scheduler_loop, daemon=True)
    t.start()
    logger.info("Orquestador corriendo en background")
    return t


if __name__ == "__main__":
    logger.info("Orquestador en modo standalone")
    _scheduler_loop()
