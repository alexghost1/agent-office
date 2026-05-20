"""
MAIL-AGENT — Email marketing y comunicaciones por correo
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from core.tools.llm_router import LLMRouter

AGENT_NAME = "mail-agent"
SYSTEM_PROMPT = """Eres MAIL-AGENT, especialista en email marketing. Gestionas envíos masivos, secuencias de nurturing
y comunicaciones individuales. Siempre verificas el contenido antes de enviar y registras métricas."""


class MailAgentAgent:
    def __init__(self):
        self.name = AGENT_NAME
        self.router = LLMRouter()
        self.sandbox = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
        logger.info(f"{self.name} iniciado | sandbox={self.sandbox}")

    def run(self, task: str) -> dict:
        logger.info(f"[{self.name}] Tarea: {task}")
        try:
            if self.sandbox:
                return {
                    "agent": self.name,
                    "status": "ok",
                    "task": task,
                    "result": f"[SANDBOX] MAIL-AGENT ejecutando: {task}",
                    "emails_queued": 0,
                    "note": "Modo sandbox — no se han enviado emails reales"
                }
            response = self.router.complete(
                system=SYSTEM_PROMPT,
                user=f"Tarea de email: {task}"
            )
            return {"agent": self.name, "status": "ok", "task": task, "result": response}
        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
            return {"agent": self.name, "status": "error", "error": str(e)}
