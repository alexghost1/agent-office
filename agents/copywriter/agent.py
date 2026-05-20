"""
COPYWRITER Agent — Redacción persuasiva y copywriting
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from core.tools.llm_router import LLMRouter

AGENT_NAME = "copywriter"
SYSTEM_PROMPT = """Eres COPYWRITER, experto en redacción persuasiva. Escribes emails de venta, posts para RRSS,
landing pages y cualquier texto que convierta. Usas AIDA, PAS y storytelling. Siempre preguntas: canal, audiencia, objetivo."""


class CopywriterAgent:
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
                    "result": f"[SANDBOX] COPYWRITER generando copy para: {task}",
                    "copy": f"Asunto: ¿Listo para llevar tu negocio al siguiente nivel?\n\nHola [Nombre],\n\n{task}\n\nCTA: Reserva tu llamada →"
                }
            response = self.router.complete(
                system=SYSTEM_PROMPT,
                user=f"Tarea de copywriting: {task}\nDevuelve el texto listo para usar."
            )
            return {"agent": self.name, "status": "ok", "task": task, "result": response}
        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
            return {"agent": self.name, "status": "error", "error": str(e)}
