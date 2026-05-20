"""
CONTENT-CREATOR Agent — Producción de contenido multimedia
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from core.tools.llm_router import LLMRouter

AGENT_NAME = "content-creator"
SYSTEM_PROMPT = """Eres CONTENT-CREATOR, especialista en producción de contenido. Creas guiones, artículos,
newsletters y calendarios editoriales. Adaptas el formato al canal de destino."""


class ContentCreatorAgent:
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
                    "result": f"[SANDBOX] CONTENT-CREATOR generando para: {task}",
                    "content": {"tipo": "guion", "duracion": "3 min", "formato": "vídeo vertical"}
                }
            response = self.router.complete(system=SYSTEM_PROMPT, user=task)
            return {"agent": self.name, "status": "ok", "task": task, "result": response}
        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
            return {"agent": self.name, "status": "error", "error": str(e)}
