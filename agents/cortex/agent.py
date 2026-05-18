"""
CORTEX Agent — Motor de memoria y aprendizaje de la Oficina de Agentes IA
"""
import os
import datetime
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

AGENT_NAME = "cortex"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


class CortexAgent:
    def __init__(self):
        self.name = AGENT_NAME
        self.system_prompt = SYSTEM_PROMPT_PATH.read_text()
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.sandbox_mode = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
        self._store = None
        logger.info(f"{self.name} inicializado | sandbox={self.sandbox_mode}")

    @property
    def store(self):
        if self._store is None:
            from core.memory.chroma_store import ChromaStore
            self._store = ChromaStore()
        return self._store

    def run(self, task: str, context: dict = None) -> dict:
        logger.info(f"{self.name} ejecutando: {task[:80]}")
        task_lower = task.lower()
        if "store" in task_lower or "guardar" in task_lower or "almacen" in task_lower:
            data = context or {}
            doc_id = self.store_event(
                data.get("agent", "system"),
                data.get("event_type", "generic"),
                data.get("data", {"task": task})
            )
            return {"agent": self.name, "task": task, "status": "ok", "doc_id": doc_id}
        if "search" in task_lower or "buscar" in task_lower or "context" in task_lower:
            ctx = context or {}
            result = self.get_context(
                ctx.get("agent", "system"),
                ctx.get("task", task)
            )
            return {"agent": self.name, "task": task, "status": "ok", "context": result}
        if "report" in task_lower or "reporte" in task_lower or "resumen" in task_lower or "daily" in task_lower:
            report = self.daily_report()
            return {"agent": self.name, "task": task, "status": "ok", "report": report}
        if "patrón" in task_lower or "pattern" in task_lower or "detectar" in task_lower:
            patterns = self.detect_patterns()
            return {"agent": self.name, "task": task, "status": "ok", "patterns": patterns}
        return {"agent": self.name, "task": task, "status": "unknown_command"}

    def report(self) -> dict:
        return {"agent": self.name, "status": "operational", "sandbox": self.sandbox_mode}

    def store_event(self, agent: str, event_type: str, data: dict) -> str:
        collection = "errors" if "error" in event_type.lower() else "strategies"
        text = f"Evento {event_type} de {agent}: {data}"
        metadata = {"agent": agent, "event_type": event_type}
        if data:
            metadata.update(data)
        return self.store.store(collection, text, metadata=metadata)

    def get_context(self, agent: str, task: str) -> str:
        return self.store.get_agent_context(agent, task)

    def detect_patterns(self) -> list[dict]:
        patterns = []
        for col_name in ["errors", "strategies"]:
            try:
                results = self.store.search(col_name, "patrón recurrente", n_results=10, min_relevance=0.3)
                if results:
                    patterns.append({"collection": col_name, "matches": results})
            except Exception:
                continue
        return patterns

    def daily_report(self) -> str:
        today = datetime.date.today().isoformat()
        lines = [f"=== Reporte CORTEX — {today} ==="]
        for col_name in ["leads", "clients", "errors", "strategies", "social_content", "market_intel"]:
            try:
                count = self.store.count(col_name)
                lines.append(f"  {col_name}: {count} registros")
            except Exception:
                lines.append(f"  {col_name}: error al contar")
        return "\n".join(lines)

    def store_lead(self, lead_data: dict) -> str:
        text = lead_data.get("name", "Lead sin nombre")
        metadata = {"agent": "hermes", "event_type": "lead"}
        metadata.update(lead_data)
        return self.store.store("leads", text, metadata=metadata)

    def search_leads(self, query: str, min_score: int = 65) -> list[dict]:
        results = self.store.search("leads", query, n_results=20, min_relevance=0.3)
        filtered = []
        for r in results:
            score = r.get("metadata", {}).get("score", 0)
            try:
                score = int(score)
            except (ValueError, TypeError):
                score = 0
            if score >= min_score:
                filtered.append(r)
        return filtered

    def store_news(self, news_list: list[dict], source_agent: str = "atlas") -> int:
        """Almacena noticias en market_intel para que otros agentes las consulten."""
        stored = 0
        for item in news_list:
            try:
                title = item.get("title", "")
                summary = item.get("summary", item.get("description", ""))
                text = f"{title}. {summary}".strip()
                if not text or text == ".":
                    continue
                metadata = {
                    "agent": source_agent,
                    "event_type": "news",
                    "title": title,
                    "source": item.get("source", ""),
                    "published": item.get("published", datetime.datetime.now().isoformat()),
                    "topic": item.get("topic", "general"),
                    "relevance": item.get("relevance", "medium"),
                }
                self.store.store("market_intel", text, metadata=metadata)
                stored += 1
            except Exception as e:
                logger.error(f"CORTEX store_news error: {e}")
        if stored:
            logger.info(f"CORTEX almacenó {stored} noticias de {source_agent}")
        return stored

    def get_news(self, topic: str = "", n: int = 5) -> list[dict]:
        """Recupera noticias relevantes para un tema. Usado por IRIS, HERMES, NEXUS."""
        try:
            query = topic if topic else "mercados finanzas actualidad"
            results = self.store.search("market_intel", query, n_results=n, min_relevance=0.2)
            news = []
            for r in results:
                meta = r.get("metadata", {})
                news.append({
                    "title": meta.get("title", r.get("text", "")[:80]),
                    "source": meta.get("source", ""),
                    "published": meta.get("published", ""),
                    "topic": meta.get("topic", ""),
                    "relevance_score": r.get("relevance_score", 0),
                })
            return news
        except Exception as e:
            logger.error(f"CORTEX get_news error: {e}")
            return []

    def store_market_data(self, data: dict, source_agent: str = "atlas"):
        """Almacena datos de mercado para contexto histórico."""
        try:
            text = f"Datos de mercado {datetime.date.today()}: {data}"
            metadata = {
                "agent": source_agent,
                "event_type": "market_snapshot",
                "date": datetime.date.today().isoformat(),
            }
            self.store.store("market_intel", text, metadata=metadata)
            logger.info("CORTEX almacenó snapshot de mercado")
        except Exception as e:
            logger.error(f"CORTEX store_market_data error: {e}")


if __name__ == "__main__":
    agent = CortexAgent()
    print(agent.report())
