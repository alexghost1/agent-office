"""
ChromaStore — Memoria vectorial persistente para la Oficina de Agentes IA
"""
import os
import uuid
import datetime
from pathlib import Path
from loguru import logger
import chromadb
from chromadb.config import Settings

CHROMA_DIR = Path(os.getenv("CHROMA_PERSIST_DIR",
                             Path(__file__).parent.parent.parent / "data" / "vectors"))

COLLECTIONS = ["leads", "clients", "errors", "strategies", "social_content", "market_intel"]


class ChromaStore:
    def __init__(self):
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collections = {}
        for name in COLLECTIONS:
            try:
                col = self.client.get_or_create_collection(name=name)
                self.collections[name] = col
            except Exception as e:
                logger.error(f"Error creando colección {name}: {e}")
        logger.info(f"ChromaStore inicializado | colecciones: {list(self.collections.keys())}")

    def store(self, collection: str, text: str,
              metadata: dict = None, doc_id: str = None) -> str:
        if collection not in self.collections:
            raise ValueError(f"Colección no válida: {collection}. Válidas: {COLLECTIONS}")
        col = self.collections[collection]
        doc_id = doc_id or str(uuid.uuid4())
        meta = {
            "timestamp": datetime.datetime.now().isoformat(),
            "agent_source": metadata.get("agent", "system") if metadata else "system",
        }
        if metadata:
            meta.update(metadata)
        try:
            col.add(documents=[text], metadatas=[meta], ids=[doc_id])
            logger.debug(f"Stored in {collection} [{doc_id[:8]}]: {text[:60]}")
            return doc_id
        except Exception as e:
            logger.error(f"Error storing in {collection}: {e}")
            raise

    def search(self, collection: str, query: str,
               n_results: int = 5, min_relevance: float = 0.75) -> list[dict]:
        if collection not in self.collections:
            raise ValueError(f"Colección no válida: {collection}")
        col = self.collections[collection]
        try:
            results = col.query(query_texts=[query], n_results=n_results * 2)
            if not results["ids"] or not results["ids"][0]:
                return []
            items = []
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results.get("distances") else 2.0
                relevance = max(0.0, 1.0 - (distance / 2.0))
                if relevance < min_relevance:
                    continue
                items.append({
                    "id": doc_id,
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "relevance_score": round(relevance, 4),
                })
                if len(items) >= n_results:
                    break
            return items
        except Exception as e:
            logger.error(f"Error searching {collection}: {e}")
            return []

    def get_agent_context(self, agent_name: str, current_task: str) -> str:
        context_parts = []
        for col_name in ["errors", "strategies"]:
            try:
                results = self.search(
                    collection=col_name,
                    query=f"{agent_name} {current_task}",
                    n_results=3,
                    min_relevance=0.5,
                )
                for r in results:
                    context_parts.append(f"[{col_name}] {r['text']}")
            except Exception:
                continue
        if not context_parts:
            return ""
        return "Contexto previo:\n" + "\n".join(context_parts)

    def delete_collection(self, collection: str):
        if collection in self.collections:
            try:
                self.client.delete_collection(collection)
                del self.collections[collection]
                logger.info(f"Colección {collection} eliminada")
            except Exception as e:
                logger.error(f"Error eliminando colección {collection}: {e}")

    def count(self, collection: str) -> int:
        if collection not in self.collections:
            return 0
        try:
            return self.collections[collection].count()
        except Exception:
            return 0
