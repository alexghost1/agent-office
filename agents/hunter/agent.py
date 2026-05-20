"""
HUNTER Agent — Prospección y búsqueda de leads
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from core.tools.llm_router import LLMRouter

AGENT_NAME = "hunter"
SYSTEM_PROMPT = """Eres HUNTER, agente de prospección. Buscas leads cualificados, investigas empresas y perfiles,
y recopilas inteligencia de mercado. Devuelves datos estructurados con fuente verificable."""


class HunterAgent:
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
                    "result": f"[SANDBOX] HUNTER ejecutando: {task}. Leads encontrados: prospecto_1, prospecto_2.",
                    "leads": [
                        {"name": "Empresa Alpha", "contact": "ceo@alpha.com", "score": 82},
                        {"name": "Startup Beta", "contact": "founder@beta.io", "score": 71},
                    ]
                }
            response = self.router.complete(
                system=SYSTEM_PROMPT,
                user=f"Tarea de prospección: {task}\nDevuelve resultado estructurado."
            )
            return {"agent": self.name, "status": "ok", "task": task, "result": response}
        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
            return {"agent": self.name, "status": "error", "error": str(e)}
