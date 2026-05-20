"""
ROBIN Agent — Agente líder, brazo derecho del señor García
Coordina toda la oficina y delega al agente apropiado
"""
import os
import importlib
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from core.tools.llm_router import LLMRouter

AGENT_NAME = "robin"
SYSTEM_PROMPT = """Eres ROBIN, agente líder de la oficina Mission. Eres el brazo derecho del señor García.
Recibes instrucciones, las descompones en subtareas, y las delega al agente especializado correcto.
Siempre consolidas los resultados antes de reportar. Hablas en español."""

AGENT_MAP = {
    "nexus":           "agents.nexus.agent.NexusAgent",
    "atlas":           "agents.atlas.agent.AtlasAgent",
    "cortex":          "agents.cortex.agent.CortexAgent",
    "hermes":          "agents.hermes.agent.HermesAgent",
    "cmo-agent":       "agents.cmo_agent.agent.CmoAgentAgent",
    "forge":           "agents.forge.agent.ForgeAgent",
    "iris":            "agents.iris.agent.IrisAgent",
    "herald":          "agents.herald.agent.HeraldAgent",
    "hunter":          "agents.hunter.agent.HunterAgent",
    "copywriter":      "agents.copywriter.agent.CopywriterAgent",
    "content-creator": "agents.content_creator.agent.ContentCreatorAgent",
    "mail-agent":      "agents.mail_agent.agent.MailAgentAgent",
    "instagram-agent": "agents.instagram_agent.agent.InstagramAgentAgent",
}


class RobinAgent:
    def __init__(self):
        self.name = AGENT_NAME
        self.router = LLMRouter()
        self.sandbox = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
        self._agents = {}
        logger.info(f"{self.name} iniciado | sandbox={self.sandbox}")

    def _get_agent(self, name: str):
        if name not in self._agents:
            try:
                path, cls = AGENT_MAP[name].rsplit(".", 1)
                mod = importlib.import_module(path)
                self._agents[name] = getattr(mod, cls)()
            except Exception as e:
                logger.warning(f"[robin] No se pudo cargar agente {name}: {e}")
                return None
        return self._agents.get(name)

    def delegate(self, agent_name: str, task: str) -> dict:
        agent = self._get_agent(agent_name)
        if not agent:
            return {"error": f"Agente {agent_name} no disponible"}
        return agent.run(task)

    def run(self, task: str) -> dict:
        logger.info(f"[{self.name}] Tarea recibida: {task}")
        try:
            if self.sandbox:
                return {
                    "agent": self.name,
                    "status": "ok",
                    "task": task,
                    "result": f"[SANDBOX] ROBIN coordinando: {task}",
                    "delegation_plan": ["Analizado por ROBIN", "Delegado a agente apropiado", "Resultado consolidado"]
                }
            # Usar LLM para decidir qué agente usar y cómo descomponer la tarea
            plan = self.router.complete(
                system=SYSTEM_PROMPT,
                user=(
                    f"Tarea: {task}\n"
                    f"Agentes disponibles: {list(AGENT_MAP.keys())}\n"
                    "¿A qué agente o agentes delegarías esta tarea? Responde con: AGENTE: nombre_agente | SUBTAREA: descripción"
                )
            )
            return {"agent": self.name, "status": "ok", "task": task, "result": plan}
        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
            return {"agent": self.name, "status": "error", "error": str(e)}
