"""
INSTAGRAM-AGENT — Gestión operativa de Instagram
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from core.tools.llm_router import LLMRouter

AGENT_NAME = "instagram-agent"
SYSTEM_PROMPT = """Eres INSTAGRAM-AGENT, especialista en gestión operativa de Instagram.
Publicas posts, stories y reels, gestionas comentarios y DMs, y haces seguimiento de métricas."""


class InstagramAgentAgent:
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
                    "result": f"[SANDBOX] INSTAGRAM-AGENT ejecutando: {task}",
                    "post": {"status": "scheduled", "format": "carousel", "reach_estimate": "2.4K"}
                }
            response = self.router.complete(system=SYSTEM_PROMPT, user=task)
            return {"agent": self.name, "status": "ok", "task": task, "result": response}
        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
            return {"agent": self.name, "status": "error", "error": str(e)}
