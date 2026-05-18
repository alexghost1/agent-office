"""
Health-check automático y auto-recuperación de agentes
"""
import os
import time
import threading
from collections import defaultdict
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

HEALTH_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))
MAX_FAILURES = int(os.getenv("HEALTH_MAX_FAILURES", "3"))
RECOVERY_COOLDOWN = int(os.getenv("HEALTH_RECOVERY_COOLDOWN", "300"))


class CircuitBreaker:
    def __init__(self, name: str, max_failures: int = MAX_FAILURES, cooldown: int = RECOVERY_COOLDOWN):
        self.name = name
        self.max_failures = max_failures
        self.cooldown = cooldown
        self._failures = 0
        self._state = "closed"
        self._last_failure = 0
        self._last_success = time.time()
        self._lock = threading.RLock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == "open" and time.time() - self._last_failure > self.cooldown:
                self._state = "half-open"
                logger.info(f"⏳ CircuitBreaker {self.name}: half-open (probando recuperación)")
            return self._state

    def success(self):
        with self._lock:
            self._failures = 0
            self._state = "closed"
            self._last_success = time.time()

    def failure(self):
        with self._lock:
            self._failures += 1
            self._last_failure = time.time()
            if self._failures >= self.max_failures:
                self._state = "open"
                logger.warning(f"🔴 CircuitBreaker {self.name}: OPEN (tras {self._failures} fallos)")


class HealthChecker:
    def __init__(self):
        self._breakers = {}
        self._lock = threading.RLock()
        self._running = False
        self._thread = None

    def register(self, agent_name: str) -> CircuitBreaker:
        with self._lock:
            if agent_name not in self._breakers:
                self._breakers[agent_name] = CircuitBreaker(agent_name)
            return self._breakers[agent_name]

    def get_breaker(self, agent_name: str) -> CircuitBreaker:
        with self._lock:
            if agent_name not in self._breakers:
                return self.register(agent_name)
            return self._breakers[agent_name]

    def check(self, agent_name: str, agent_instance) -> dict:
        breaker = self.get_breaker(agent_name)
        if breaker.state == "open":
            return {"status": "unavailable", "reason": "circuit_open", "agent": agent_name}
        try:
            report = agent_instance.report()
            if report.get("status") == "operational":
                breaker.success()
                return {"status": "healthy", "agent": agent_name}
            breaker.failure()
            return {"status": "degraded", "reason": report.get("status"), "agent": agent_name}
        except Exception as e:
            breaker.failure()
            return {"status": "down", "error": str(e), "agent": agent_name}

    def recover(self, agent_name: str, agent_instance) -> bool:
        logger.info(f"🔄 Intentando recuperar {agent_name}...")
        breaker = self.get_breaker(agent_name)
        for attempt in range(1, 4):
            try:
                report = agent_instance.report()
                if report.get("status") == "operational":
                    breaker.success()
                    logger.info(f"✅ {agent_name} recuperado tras {attempt} intentos")
                    return True
            except Exception:
                pass
            time.sleep(2 ** attempt)
        logger.error(f"❌ No se pudo recuperar {agent_name} tras 3 intentos")
        return False

    def check_all(self, agents: dict) -> dict:
        results = {}
        for name, agent in agents.items():
            if agent:
                results[name] = self.check(name, agent)
            else:
                results[name] = {"status": "unavailable", "reason": "not_loaded"}
        return results

    def start_auto_recovery(self, agents: dict, interval: int = HEALTH_INTERVAL):
        if self._running:
            return

        def _loop():
            while self._running:
                results = self.check_all(agents)
                for name, status in results.items():
                    if status["status"] in ("down", "degraded") and agents.get(name):
                        if name != "nexus":
                            threading.Thread(target=self.recover, args=(name, agents[name]), daemon=True).start()
                time.sleep(interval)

        self._running = True
        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()
        logger.info(f"🩺 HealthChecker iniciado (cada {interval}s)")

    def stop(self):
        self._running = False
        logger.info("HealthChecker detenido")


health = HealthChecker()
