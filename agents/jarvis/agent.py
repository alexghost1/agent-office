"""
JARVIS Agent — Asistente personal de Alexandre García
Cerebro propio + memoria persistente + puente con la Oficina + control remoto
"""
import os
import json
import datetime
import threading
import uuid
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from core.tools.llm_router import LLMRouter

AGENT_NAME = "jarvis"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"

DATA_DIR              = Path(__file__).parent.parent.parent / "data" / "jarvis"
CONTROL_PATH          = DATA_DIR / "control.json"
MIND_LOG_PATH         = DATA_DIR / "mind_log.json"
AUTONOMOUS_TASKS_PATH = DATA_DIR / "autonomous_tasks.json"
CHAT_HISTORY_PATH     = DATA_DIR / "chat_history.jsonl"

MAX_MIND_LOG    = 200
MAX_CHAT_RETURN = 50

# Bridge con los agentes de la Oficina
OFFICE_AGENTS = {
    "nexus":  "agents.nexus.agent.NexusAgent",
    "atlas":  "agents.atlas.agent.AtlasAgent",
    "hermes": "agents.hermes.agent.HermesAgent",
    "iris":   "agents.iris.agent.IrisAgent",
    "herald": "agents.herald.agent.HeraldAgent",
    "cortex": "agents.cortex.agent.CortexAgent",
    "forge":  "agents.forge.agent.ForgeAgent",
}

_lock = threading.Lock()


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save_json(path: Path, data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    tmp.replace(path)


class JarvisAgent:
    """Asistente personal — cerebro propio, memoria, puente con la Oficina y control remoto."""

    def __init__(self):
        self.name = AGENT_NAME
        self.system_prompt = SYSTEM_PROMPT_PATH.read_text()
        self.router = LLMRouter()
        self.sandbox = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
        self.owner_name = os.getenv("OWNER_NAME", "Alexandre")
        self._office_agents = {}
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"{self.name} iniciado | sandbox={self.sandbox}")

    # ── Control remoto (kill switch / pausa) ─────────────────────────

    def get_control(self) -> dict:
        return _load_json(CONTROL_PATH, {"paused": False, "killswitch": False, "pause_reason": ""})

    def _set_control(self, **changes) -> dict:
        with _lock:
            state = self.get_control()
            state.update(changes)
            state["updated"] = datetime.datetime.now().isoformat()
            _save_json(CONTROL_PATH, state)
            return state

    def pause(self, reason: str = "") -> dict:
        logger.info(f"[{self.name}] ⏸ Pausado por {self.owner_name}: {reason}")
        return self._set_control(paused=True, pause_reason=reason)

    def resume(self) -> dict:
        logger.info(f"[{self.name}] ▶ Reanudado por {self.owner_name}")
        return self._set_control(paused=False, pause_reason="")

    def set_killswitch(self, active: bool) -> dict:
        logger.warning(f"[{self.name}] ⛔ Kill switch {'ACTIVADO' if active else 'desactivado'}")
        return self._set_control(killswitch=active)

    def is_active(self) -> bool:
        c = self.get_control()
        return not c.get("paused", False) and not c.get("killswitch", False)

    # ── Memoria: mind log ─────────────────────────────────────────────

    def _log_thought(self, kind: str, content: str, meta: dict = None):
        with _lock:
            log = _load_json(MIND_LOG_PATH, [])
            log.append({
                "ts": datetime.datetime.now().isoformat(),
                "kind": kind,
                "content": content[:2000],
                "meta": meta or {},
            })
            log = log[-MAX_MIND_LOG:]
            _save_json(MIND_LOG_PATH, log)

    def get_mind_log(self, limit: int = 20) -> list:
        log = _load_json(MIND_LOG_PATH, [])
        return log[-limit:][::-1]

    def _log_chat(self, role: str, content: str, channel: str = "hud"):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.datetime.now().isoformat(),
            "role": role,
            "content": content,
            "channel": channel,
        }
        with _lock, open(CHAT_HISTORY_PATH, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_chat_history(self, limit: int = MAX_CHAT_RETURN) -> list:
        if not CHAT_HISTORY_PATH.exists():
            return []
        lines = [l for l in CHAT_HISTORY_PATH.read_text().splitlines() if l.strip()]
        return [json.loads(l) for l in lines[-limit:]]

    # ── Memoria: tareas autónomas ─────────────────────────────────────

    def get_tasks(self, status: str = None) -> list:
        tasks = _load_json(AUTONOMOUS_TASKS_PATH, [])
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        return tasks

    def add_task(self, description: str, source: str = "owner") -> dict:
        with _lock:
            tasks = _load_json(AUTONOMOUS_TASKS_PATH, [])
            task = {
                "id": uuid.uuid4().hex[:8],
                "description": description,
                "status": "pending",
                "source": source,
                "created": datetime.datetime.now().isoformat(),
                "updated": datetime.datetime.now().isoformat(),
            }
            tasks.append(task)
            _save_json(AUTONOMOUS_TASKS_PATH, tasks)
            return task

    def update_task(self, task_id: str, status: str, note: str = "") -> dict:
        with _lock:
            tasks = _load_json(AUTONOMOUS_TASKS_PATH, [])
            for t in tasks:
                if t["id"] == task_id:
                    t["status"] = status
                    t["updated"] = datetime.datetime.now().isoformat()
                    if note:
                        t["note"] = note
                    _save_json(AUTONOMOUS_TASKS_PATH, tasks)
                    return t
            return {"error": f"tarea {task_id} no encontrada"}

    # ── Puente con la Oficina ─────────────────────────────────────────

    def _get_office_agent(self, name: str):
        name = name.lower().replace("-", "_")
        if name not in self._office_agents:
            path = OFFICE_AGENTS.get(name)
            if not path:
                return None
            try:
                import importlib
                mod_path, cls_name = path.rsplit(".", 1)
                mod = importlib.import_module(mod_path)
                self._office_agents[name] = getattr(mod, cls_name)()
            except Exception as e:
                logger.warning(f"[{self.name}] No se pudo cargar agente de Oficina {name}: {e}")
                return None
        return self._office_agents.get(name)

    def office_status(self) -> dict:
        """Resumen de qué agentes de la Oficina están operativos."""
        status = {}
        for name in OFFICE_AGENTS:
            agent = self._get_office_agent(name)
            status[name] = "operativo" if agent is not None else "no disponible"
        return status

    def delegate(self, agent_name: str, task: str) -> dict:
        """Llama a un agente de la Oficina y devuelve su resultado."""
        if not self.is_active():
            return {"status": "blocked", "error": "JARVIS está pausado o en killswitch — no se delega"}
        agent_name = agent_name.lower().replace("-", "_")
        agent = self._get_office_agent(agent_name)
        if not agent:
            return {"status": "error", "error": f"Agente de Oficina '{agent_name}' no disponible"}
        try:
            result = agent.run(task)
            self._log_thought("delegacion", f"Delegué a {agent_name.upper()}: {task}", {"agent": agent_name, "result": str(result)[:300]})
            return result if isinstance(result, dict) else {"status": "ok", "result": str(result)}
        except Exception as e:
            logger.error(f"[{self.name}] Error delegando a {agent_name}: {e}")
            return {"status": "error", "error": str(e)}

    # ── Decisión: ¿respondo yo o delego? ──────────────────────────────

    def _route(self, message: str) -> str | None:
        """Decide a qué agente de la Oficina (si alguno) corresponde la petición."""
        msg = message.lower()
        routes = {
            "atlas":  ["mercado", "bolsa", "ibex", "s&p", "crypto", "bitcoin", "noticias", "briefing"],
            "hermes": ["lead", "leads", "prospecto", "outreach", "cliente potencial"],
            "iris":   ["instagram", "contenido", "post", "caption", "redes sociales"],
            "herald": ["email", "correo", "bandeja", "inbox"],
            "cortex": ["memoria", "patrón", "patrones", "recuerda"],
            "forge":  ["log", "logs", "infraestructura", "deploy", "código", "bug"],
            "nexus":  ["oficina entera", "coordina", "orquesta"],
        }
        for agent, keywords in routes.items():
            if any(kw in msg for kw in keywords):
                return agent
        return None

    # ── Interacción principal: chat ───────────────────────────────────

    def chat(self, message: str, channel: str = "hud") -> dict:
        """Punto de entrada conversacional — usado por el HUD, Telegram, etc."""
        self._log_chat("owner", message, channel=channel)

        control = self.get_control()
        if control.get("killswitch"):
            reply = "⛔ Estoy en killswitch. No puedo actuar hasta que lo desactives."
            self._log_chat("jarvis", reply, channel=channel)
            return {"status": "blocked", "reply": reply, "control": control}

        target = self._route(message)
        delegated = None
        if target and not control.get("paused"):
            delegated = self.delegate(target, message)

        if self.sandbox:
            if delegated is not None:
                reply = (f"[SANDBOX] Te escuché — esto le toca a {target.upper()}, lo consulté por ti: "
                         f"{str(delegated.get('result', delegated))[:280]}")
            else:
                reply = f"[SANDBOX] Recibido, {self.owner_name}. Aquí estoy — modo sandbox, sin ejecutar acciones reales: «{message[:160]}»"
            self._log_chat("jarvis", reply, channel=channel)
            self._log_thought("chat", f"{self.owner_name}: {message}", {"channel": channel, "delegated_to": target})
            return {"status": "ok", "reply": reply, "delegated_to": target, "control": control}

        try:
            context = ""
            if delegated is not None:
                context = f"\n\nConsulté a {target.upper()} y respondió: {str(delegated.get('result', delegated))[:600]}"
            reply = self.router.call(
                prompt=f"{self.owner_name} te dice: {message}{context}\n\nResponde como JARVIS, en español, directo y útil.",
                task_description="chat personal con el propietario",
                system=self.system_prompt,
            )
            self._log_chat("jarvis", reply, channel=channel)
            self._log_thought("chat", f"{self.owner_name}: {message}", {"channel": channel, "delegated_to": target})
            return {"status": "ok", "reply": reply, "delegated_to": target, "control": control}
        except Exception as e:
            err = f"Tuve un problema procesando eso: {e}"
            self._log_chat("jarvis", err, channel=channel)
            logger.error(f"[{self.name}] Error en chat: {e}")
            return {"status": "error", "reply": err, "error": str(e)}

    def run(self, task: str, context: dict = None) -> dict:
        """Compatibilidad con el patrón Agent.run() de la Oficina (orquestador, HUD)."""
        result = self.chat(task, channel="run")
        return {
            "agent": self.name,
            "status": result.get("status", "ok"),
            "task": task,
            "result": result.get("reply", ""),
            "delegated_to": result.get("delegated_to"),
        }

    # ── Ciclo de pensamiento autónomo ─────────────────────────────────

    def think_cycle(self) -> dict:
        """Revisa el estado de la Oficina, gestiona tareas pendientes y registra el ciclo."""
        if not self.is_active():
            self._log_thought("ciclo", "Ciclo saltado — JARVIS pausado o en killswitch")
            return {"status": "skipped", "reason": "paused_or_killswitch"}

        office = self.office_status()
        pending = self.get_tasks(status="pending")
        summary = (f"Ciclo de revisión — Oficina: "
                   f"{sum(1 for v in office.values() if v == 'operativo')}/{len(office)} agentes operativos. "
                   f"Tareas pendientes: {len(pending)}.")
        self._log_thought("ciclo", summary, {"office": office, "pending_tasks": len(pending)})
        logger.info(f"[{self.name}] {summary}")
        return {"status": "ok", "summary": summary, "office": office, "pending_tasks": len(pending)}

    # ── Estado / reporte ──────────────────────────────────────────────

    def report(self) -> dict:
        control = self.get_control()
        tasks = self.get_tasks()
        return {
            "status": "operational" if self.is_active() else "paused",
            "sandbox": self.sandbox,
            "control": control,
            "tasks_total": len(tasks),
            "tasks_pending": len([t for t in tasks if t.get("status") == "pending"]),
            "tasks_done": len([t for t in tasks if t.get("status") == "done"]),
            "last_thoughts": self.get_mind_log(limit=3),
        }
