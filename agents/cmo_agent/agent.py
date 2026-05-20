"""
CMO-AGENT — Director de Marketing, orquesta la cadena de marketing
"""
import os
import importlib
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from core.tools.llm_router import LLMRouter

AGENT_NAME = "cmo-agent"
SYSTEM_PROMPT = """Eres CMO-AGENT, Director de Marketing. Defines estrategia, coordinas campañas multicanal
y delegas a los agentes especializados: hunter, copywriter, content-creator, mail-agent, instagram-agent, iris, herald."""

# Mapeo de subagentes que puede delegar
SUBAGENTS = {
    "hunter":           "agents.hunter.agent.HunterAgent",
    "copywriter":       "agents.copywriter.agent.CopywriterAgent",
    "content-creator":  "agents.content_creator.agent.ContentCreatorAgent",
    "mail-agent":       "agents.mail_agent.agent.MailAgentAgent",
    "instagram-agent":  "agents.instagram_agent.agent.InstagramAgentAgent",
}


class CmoAgentAgent:
    def __init__(self):
        self.name = AGENT_NAME
        self.router = LLMRouter()
        self.sandbox = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
        self._subagents = {}
        logger.info(f"{self.name} iniciado | sandbox={self.sandbox}")

    def _get_subagent(self, name: str):
        if name not in self._subagents:
            try:
                path, cls = SUBAGENTS[name].rsplit(".", 1)
                mod = importlib.import_module(path)
                self._subagents[name] = getattr(mod, cls)()
            except Exception as e:
                logger.warning(f"[cmo-agent] No se pudo cargar subagente {name}: {e}")
                return None
        return self._subagents.get(name)

    def run(self, task: str) -> dict:
        logger.info(f"[{self.name}] Tarea: {task}")
        try:
            if self.sandbox:
                return {
                    "agent": self.name,
                    "status": "ok",
                    "task": task,
                    "result": f"[SANDBOX] CMO-AGENT planificando campaña para: {task}",
                    "plan": ["1. HUNTER busca leads", "2. COPYWRITER redacta emails", "3. MAIL-AGENT envía secuencia"]
                }
            response = self.router.complete(
                system=SYSTEM_PROMPT,
                user=f"Tarea de marketing: {task}\nCrea un plan de acción y delega a los subagentes apropiados."
            )
            return {"agent": self.name, "status": "ok", "task": task, "result": response}
        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
            return {"agent": self.name, "status": "error", "error": str(e)}
