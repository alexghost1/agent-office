"""
NEXUS Agent — Orquestador central 400% mode
Parallel execution · Circuit breaker · Priority queue · Auto-recovery
"""
import os
import time
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import PriorityQueue
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

AGENT_NAME = "nexus"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"

AGENTS_MAP = {
    "cortex": "agents.cortex.agent",
    "hermes": "agents.hermes.agent",
    "iris": "agents.iris.agent",
    "atlas": "agents.atlas.agent",
    "herald": "agents.herald.agent",
    "forge": "agents.forge.agent",
}

MAX_WORKERS = int(os.getenv("NEXUS_MAX_WORKERS", "4"))


class NexusAgent:
    def __init__(self):
        self.name = AGENT_NAME
        self.system_prompt = SYSTEM_PROMPT_PATH.read_text()
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.sandbox_mode = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
        self.max_retries = int(os.getenv("AGENT_MAX_RETRIES", "3"))
        self.agents = {}
        self.scheduler = None
        self._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="nexus")
        self._task_queue = PriorityQueue()
        self._queue_worker = None
        self._running = False
        self._load_agents()
        self._init_health()
        self._start_queue_worker()
        logger.info(f"{self.name} 400% | workers={MAX_WORKERS} | sandbox={self.sandbox_mode}")

    def _load_agents(self):
        for name, module_path in AGENTS_MAP.items():
            try:
                module = __import__(module_path, fromlist=["*"])
                cls_name = f"{name.capitalize()}Agent"
                agent_cls = getattr(module, cls_name)
                self.agents[name] = agent_cls()
            except Exception as e:
                logger.error(f"Error cargando {name}: {e}")
                self.agents[name] = None

    def _init_health(self):
        try:
            from core.tools.health import health
            for name in self.agents:
                health.register(name)
        except Exception:
            pass

    def _start_queue_worker(self):
        def _drain():
            while True:
                try:
                    priority, task, context, future = self._task_queue.get(timeout=1)
                    try:
                        result = self._execute(task, context)
                        future.set_result(result)
                    except Exception as e:
                        future.set_exception(e)
                except Exception:
                    continue
        self._queue_worker = threading.Thread(target=_drain, daemon=True)
        self._queue_worker.start()

    def get_agent(self, name: str):
        return self.agents.get(name)

    def report(self) -> dict:
        return {"agent": self.name, "status": "operational", "sandbox": self.sandbox_mode}

    def run(self, task: str, context: dict = None) -> dict:
        return self.orchestrate(task, context=context)

    def orchestrate(self, task: str, priority: int = 5, context: dict = None) -> dict:
        logger.info(f"Orquestando: {task[:60]} (prioridad {priority})")
        from core.tools.metrics import metrics
        agent_name = self._route_task(task)
        if not agent_name:
            return {"agent": self.name, "status": "error", "error": f"No se pudo rutear: {task}"}
        agent = self.get_agent(agent_name)
        if not agent:
            return {"agent": self.name, "status": "error", "error": f"Agente {agent_name} no disponible"}

        from core.tools.health import health
        breaker = health.get_breaker(agent_name)
        if breaker.state == "open":
            logger.warning(f"Circuit open for {agent_name}, buscando fallback")
            alt = self._find_fallback(task, agent_name)
            if alt:
                return self._execute(alt["task"], context, alt["agent"])
            return {"agent": self.name, "status": "error", "error": f"{agent_name} circuit open, sin fallback"}

        start = time.time()
        try:
            result = self._execute(task, context, agent)
            elapsed = time.time() - start
            metrics.record(agent_name, task, elapsed, True)
            breaker.success()
            result["orchestrated_by"] = self.name
            result["elapsed"] = round(elapsed, 3)
            return result
        except Exception as e:
            elapsed = time.time() - start
            metrics.record(agent_name, task, elapsed, False, str(e))
            breaker.failure()
            logger.error(f"Fallo en {agent_name} ({elapsed:.2f}s): {e}")
            return self.handle_agent_failure(agent_name, task, str(e))

    def orchestrate_async(self, task: str, priority: int = 5, context: dict = None):
        from concurrent.futures import Future
        future = Future()
        self._task_queue.put((priority, task, context, future))
        return future

    def orchestrate_batch(self, tasks: list[tuple[str, int]], context: dict = None) -> list[dict]:
        futures = {self.orchestrate_async(task, pri, context): (task, pri) for task, pri in tasks}
        results = []
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                task, pri = futures[future]
                results.append({"task": task, "status": "error", "error": str(e)})
        return results

    def _route_task(self, task: str) -> str:
        task_lower = task.lower()
        routing = {
            "cortex": ["memoria", "almacen", "buscar", "patrón", "aprender", "recordar",
                       "contexto", "recuperar", "chroma"],
            "hermes": ["lead", "outreach", "contactar", "extraer", "cualificar", "crm",
                       "pipeline", "prospecto"],
            "iris":   ["instagram", "post", "publicar", "social", "story", "reel", "caption",
                       "hashtag", "seguidor", "estrategia", "crecimiento", "redes", "contenido",
                       "sidecar", "plan mensual", "plan del mes", "revisión", "quincenal",
                       "métrica", "engagement", "audiencia", "feed"],
            "atlas":  ["mercado", "financiero", "research", "briefing", "ibex", "inversión",
                       "crypto", "bitcoin", "btc", "ethereum", "acciones"],
            "herald": ["email", "correo", "gmail", "bandeja", "inbox", "herald", "draft",
                       "borrador"],
            "forge":  ["código", "infra", "github", "commit", "implementar", "bug", "log",
                       "deploy", "ollama", "modelo"],
        }
        for agent, keywords in routing.items():
            for kw in keywords:
                if kw in task_lower:
                    return agent
        if "report" in task_lower or "resumen" in task_lower:
            return "cortex"
        from core.tools.llm_router import LLMRouter
        router = LLMRouter()
        model = router.route(task)
        if model == "ollama":
            return "forge"
        return "cortex"

    def _find_fallback(self, task: str, failed_agent: str) -> dict:
        fallback_map = {
            "hermes": ("cortex", "buscar leads en memoria"),
            "iris":   ("forge", "generar contenido automático"),
            "atlas":  ("cortex", "recuperar último briefing"),
            "herald": ("forge", "simular envío de email"),
            "cortex": ("nexus", "esperar recuperación de CORTEX"),
            "forge":  ("nexus", "esperar recuperación de FORGE"),
        }
        if failed_agent in fallback_map:
            alt_name, alt_task = fallback_map[failed_agent]
            return {"agent": alt_name, "task": alt_task}
        return None

    def _execute(self, task: str, context: dict = None, agent=None) -> dict:
        agent_name = self._route_task(task)
        agent = agent or self.get_agent(agent_name)
        if not agent:
            return {"agent": self.name, "status": "error", "error": f"Agente {agent_name} no disponible"}
        if hasattr(agent, "sandbox_mode"):
            pass
        return agent.run(task, context=context)

    def handle_agent_failure(self, agent_name: str, task: str, error: str) -> dict:
        logger.warning(f"Manejando fallo de {agent_name}: {error[:80]}")
        from core.memory.chroma_store import ChromaStore
        try:
            store = ChromaStore()
            store.store("errors", f"Fallo en {agent_name}: {error}",
                        metadata={"agent": agent_name, "task": task, "severity": "high"})
        except Exception:
            pass
        from core.tools.notifier import Notifier
        retry_count = getattr(self, f"_{agent_name}_retries", 0) + 1
        setattr(self, f"_{agent_name}_retries", retry_count)
        if retry_count >= 3:
            Notifier().send(f"⚠️ {agent_name} ha fallado {retry_count} veces seguidas: {error[:100]}",
                            priority="critical", agent=self.name)

        alt = self._find_fallback(task, agent_name)
        if alt and self.get_agent(alt["agent"]):
            logger.info(f"Reasignando a {alt['agent']}: {alt['task']}")
            try:
                return self.get_agent(alt["agent"]).run(alt["task"])
            except Exception:
                pass
        from core.tools.health import health
        health.get_breaker(agent_name).failure()
        return {"agent": self.name, "status": "error",
                "error": f"Fallo en {agent_name}: {error}", "task": task}

    def hourly_cycle(self):
        logger.info("🔥 Ciclo horario ejecutándose...")
        from core.tools.metrics import metrics
        results = {}
        def check(name, agent):
            try:
                r = agent.report()
                return name, r.get("status", "unknown")
            except Exception as e:
                return name, f"error: {e}"
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(check, n, a): n for n, a in self.agents.items() if a}
            for future in as_completed(futures):
                name, status = future.result()
                results[name] = status
        logger.info(f"Estado: {results}")
        ms = metrics.summary()
        logger.info(f"Métricas:\n{ms}")
        metrics.save_snapshot()
        return results

    def daily_briefing(self) -> str:
        today = datetime.date.today().isoformat()
        lines = [f"=== Briefing Diario NEXUS 400% — {today} ==="]
        for name, agent in self.agents.items():
            if agent:
                try:
                    report = agent.report()
                    lines.append(f"  {name.upper()}: {report.get('status', 'unknown')}")
                except Exception:
                    lines.append(f"  {name.upper()}: error")
            else:
                lines.append(f"  {name.upper()}: no disponible")
        try:
            from core.tools.metrics import metrics
            lines.append(f"\n{metrics.summary()}")
        except Exception:
            pass
        atlas = self.get_agent("atlas")
        if atlas:
            try:
                briefing = atlas.run("generar briefing matutino con crypto", {"type": "briefing"})
                text = briefing.get("briefing", str(briefing))
                lines.append(f"\nBriefing ATLAS:\n{text[:300]}")
            except Exception:
                lines.append("\nBriefing ATLAS: no disponible")
        return "\n".join(lines)

    def weekly_improvements(self) -> list[str]:
        improvements = []
        try:
            from core.tools.metrics import metrics
            r = metrics.report()
            for name, m in sorted(r.items()):
                if m["success_rate"] < 90:
                    improvements.append(f"{name.upper()}: tasa de éxito {m['success_rate']}% — requiere revisión")
                elif m["avg_time"] > 5:
                    improvements.append(f"{name.upper()}: latencia alta ({m['avg_time']}s avg)")
                else:
                    improvements.append(f"{name.upper()}: ✅ rendimiento óptimo")
        except Exception:
            for name in self.agents:
                improvements.append(f"{name.upper()}: sin métricas disponibles")
        return improvements

    def start(self):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            self.scheduler = BackgroundScheduler()
            self.scheduler.add_job(self.hourly_cycle, "interval", hours=1,
                                   id="hourly_cycle", name="Ciclo horario")
            self.scheduler.add_job(self._morning_briefing, "cron", hour=7, minute=0,
                                   id="morning_briefing", name="Briefing matutino")
            self.scheduler.add_job(self._morning_post, "cron", hour=9, minute=0,
                                   id="morning_post", name="Post diario IRIS")
            self.scheduler.add_job(self._evening_summary, "cron", hour=18, minute=0,
                                   id="evening_summary", name="Resumen vespertino")
            self.scheduler.add_job(self._daily_metrics_snapshot, "cron", hour=23, minute=55,
                                   id="daily_metrics", name="Snapshot métricas")
            self.scheduler.add_job(self._weekly_review, "cron", day_of_week="fri", hour=16, minute=0,
                                   id="weekly_review", name="Revisión semanal")
            # IRIS: Plan mensual de contenido (día 1 de cada mes)
            self.scheduler.add_job(self._plan_mensual_iris, "cron", day=1, hour=9, minute=0,
                                   id="plan_mensual_iris", name="Plan mensual IRIS")
            # IRIS: Revisión quincenal (día 15 de cada mes)
            self.scheduler.add_job(self._revision_quincenal_iris, "cron", day=15, hour=10, minute=0,
                                   id="revision_quincenal_iris", name="Revisión quincenal IRIS")
            self.scheduler.start()
            logger.info("Scheduler NEXUS 400% iniciado")
        except Exception as e:
            logger.error(f"Error iniciando scheduler: {e}")

        try:
            from core.tools.health import health
            health.start_auto_recovery(self.agents, interval=60)
        except Exception:
            pass

    def stop(self):
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
        self._executor.shutdown(wait=False)
        try:
            from core.tools.health import health
            health.stop()
        except Exception:
            pass
        logger.info("NEXUS 400% detenido")

    def _morning_briefing(self):
        atlas = self.get_agent("atlas")
        if atlas:
            try:
                result = atlas.run("generar briefing matutino completo con crypto")
                logger.info(f"Briefing matutino generado")
            except Exception as e:
                logger.error(f"Error en briefing: {e}")

    def _morning_post(self):
        iris = self.get_agent("iris")
        if iris:
            try:
                result = iris.run("generar y programar post del día")
                logger.info(f"Post diario: {str(result)[:100]}")
            except Exception as e:
                logger.error(f"Error en post: {e}")

    def _evening_summary(self):
        summary = self.daily_briefing()
        logger.info(f"Resumen vespertino generado")
        from core.tools.notifier import Notifier
        try:
            Notifier().daily_summary(summary)
        except Exception as e:
            logger.error(f"Error enviando resumen: {e}")

    def _daily_metrics_snapshot(self):
        try:
            from core.tools.metrics import metrics
            metrics.save_snapshot()
            logger.info("Snapshot de métricas guardado")
        except Exception as e:
            logger.error(f"Error en snapshot: {e}")

    def _plan_mensual_iris(self):
        iris = self.get_agent("iris")
        if iris:
            try:
                result = iris.run("sidecar plan mensual de contenido")
                plan = result.get("plan_mensual", {})
                total = plan.get("total_posts", 0)
                semanas = len(plan.get("semanas", []))
                logger.info(f"📅 Plan mensual IRIS generado: {total} posts en {semanas} semanas")
            except Exception as e:
                logger.error(f"Error en plan mensual IRIS: {e}")

    def _revision_quincenal_iris(self):
        iris = self.get_agent("iris")
        if iris:
            try:
                result = iris.run("revisión quincenal de contenido día 15")
                revision = result.get("revision", {})
                sugerencias = len(revision.get("sugerencias", []))
                logger.info(f"🔍 Revisión quincenal IRIS: {sugerencias} sugerencias")
            except Exception as e:
                logger.error(f"Error en revisión quincenal IRIS: {e}")

    def _weekly_review(self):
        improvements = self.weekly_improvements()
        logger.info(f"Mejoras semanales: {len(improvements)} items")
        from core.tools.notifier import Notifier
        try:
            Notifier().send("Mejoras semanales:\n" + "\n".join(improvements),
                            priority="normal", agent=self.name)
        except Exception as e:
            logger.error(f"Error enviando mejoras: {e}")


if __name__ == "__main__":
    agent = NexusAgent()
    print(agent.report())
