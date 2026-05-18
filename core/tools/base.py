"""
Framework base de Tools para los agentes
Cada tool hereda de BaseTool e implementa execute()
"""
from abc import ABC, abstractmethod
from typing import Any
from loguru import logger


class BaseTool(ABC):
    name: str = "base_tool"
    description: str = "Tool base"

    @abstractmethod
    def execute(self, **kwargs) -> dict:
        """Ejecutar la tool. Retorna dict con result, error, metadata."""
        pass

    def safe_execute(self, **kwargs) -> dict:
        """Ejecutar con manejo de errores automático."""
        try:
            result = self.execute(**kwargs)
            logger.debug(f"[{self.name}] OK: {str(result)[:100]}")
            return {"success": True, "result": result, "error": None}
        except Exception as e:
            logger.error(f"[{self.name}] ERROR: {e}")
            return {"success": False, "result": None, "error": str(e)}


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Buscar información en internet"

    def execute(self, query: str, max_results: int = 5) -> dict:
        # TODO: Claude Code implementará con requests + scraping o Serper API
        return {"query": query, "results": [], "status": "pending_implementation"}


class InstagramTool(BaseTool):
    name = "instagram"
    description = "Interactuar con Instagram Graph API"

    def execute(self, action: str, **kwargs) -> dict:
        # TODO: Claude Code implementará con requests a Graph API
        return {"action": action, "status": "pending_implementation"}


class GmailTool(BaseTool):
    name = "gmail"
    description = "Leer y enviar emails via Gmail API"

    def execute(self, action: str, **kwargs) -> dict:
        # TODO: Claude Code implementará con google-api-python-client
        return {"action": action, "status": "pending_implementation"}


class ChromaMemoryTool(BaseTool):
    name = "chroma_memory"
    description = "Almacenar y recuperar memoria vectorial"

    def execute(self, action: str, collection: str, **kwargs) -> dict:
        # TODO: Claude Code implementará con chromadb
        return {"action": action, "collection": collection, "status": "pending_implementation"}


class OllamaTool(BaseTool):
    name = "ollama"
    description = "Ejecutar LLM local via Ollama"

    def execute(self, prompt: str, model: str = None) -> dict:
        import os, requests
        url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        try:
            resp = requests.post(f"{url}/api/generate",
                                 json={"model": model, "prompt": prompt, "stream": False},
                                 timeout=60)
            return {"response": resp.json().get("response", ""), "model": model}
        except Exception as e:
            return {"error": str(e), "status": "ollama_unavailable"}


class GithubTool(BaseTool):
    name = "github"
    description = "Interactuar con repositorio GitHub"

    def execute(self, action: str, **kwargs) -> dict:
        # TODO: Claude Code implementará con PyGithub
        return {"action": action, "status": "pending_implementation"}
