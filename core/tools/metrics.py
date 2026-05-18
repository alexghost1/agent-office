"""
Métricas de performance para toda la oficina
Tiempos de respuesta, tasa de éxito/error, uptime
"""
import os
import time
import json
import datetime
import threading
from collections import defaultdict
from pathlib import Path
from loguru import logger

METRICS_DIR = Path(os.getenv("LOGS_DIR", Path(__file__).parent.parent.parent / "data" / "logs")) / "metrics"
MAX_HISTORY = 10000


class MetricsCollector:
    def __init__(self):
        self._lock = threading.RLock()
        self._agents = defaultdict(lambda: {
            "calls": 0, "errors": 0, "total_time": 0.0, "min_time": float("inf"),
            "max_time": 0.0, "last_call": None, "last_error": None, "uptime_start": time.time(),
        })
        self._history = []
        self._start = time.time()
        METRICS_DIR.mkdir(parents=True, exist_ok=True)

    def record(self, agent: str, task: str, duration: float, success: bool, error: str = None):
        with self._lock:
            a = self._agents[agent]
            a["calls"] += 1
            a["total_time"] += duration
            a["min_time"] = min(a["min_time"], duration)
            a["max_time"] = max(a["max_time"], duration)
            a["last_call"] = datetime.datetime.now().isoformat()
            if not success:
                a["errors"] += 1
                a["last_error"] = error
            entry = {
                "agent": agent, "task": task[:80], "duration": round(duration, 4),
                "success": success, "error": error, "timestamp": a["last_call"],
            }
            self._history.append(entry)
            if len(self._history) > MAX_HISTORY:
                self._history = self._history[-MAX_HISTORY:]

    def report(self, agent: str = None) -> dict:
        with self._lock:
            if agent:
                agents_data = {agent: dict(self._agents[agent])}
            else:
                agents_data = {k: dict(v) for k, v in self._agents.items()}
        result = {}
        for name, data in agents_data.items():
            calls = data["calls"]
            avg = round(data["total_time"] / calls, 3) if calls else 0
            success_rate = round((1 - data["errors"] / calls) * 100, 1) if calls else 100.0
            uptime = round(time.time() - data["uptime_start"])
            result[name] = {
                "calls": calls, "errors": data["errors"],
                "success_rate": success_rate, "avg_time": avg,
                "min_time": round(data["min_time"], 3) if calls else 0,
                "max_time": round(data["max_time"], 3) if calls else 0,
                "uptime_seconds": uptime, "last_call": data["last_call"],
                "last_error": data["last_error"],
            }
        return result

    def history(self, limit: int = 20, agent: str = None) -> list[dict]:
        with self._lock:
            h = self._history
            if agent:
                h = [e for e in h if e["agent"] == agent]
            return h[-limit:]

    def summary(self) -> str:
        r = self.report()
        lines = ["📊 MÉTRICAS DE LA OFICINA", f"  {'='*40}"]
        total_calls = sum(v["calls"] for v in r.values())
        total_errors = sum(v["errors"] for v in r.values())
        lines.append(f"  Total llamadas: {total_calls}")
        lines.append(f"  Total errores:  {total_errors}")
        lines.append(f"  Tasa global:    {round((1-total_errors/max(total_calls,1))*100,1)}%")
        lines.append("")
        for name, m in sorted(r.items()):
            status = "✅" if m["success_rate"] >= 95 else "⚠️" if m["success_rate"] >= 80 else "❌"
            lines.append(f"  {status} {name.upper():8s} | {m['calls']:4d} calls | {m['success_rate']:5.1f}% OK | ⚡{m['avg_time']:6.3f}s avg")
        return "\n".join(lines)

    def save_snapshot(self):
        path = METRICS_DIR / f"metrics_{datetime.date.today().isoformat()}.json"
        data = {"timestamp": datetime.datetime.now().isoformat(), "agents": self.report()}
        try:
            if path.exists():
                existing = json.loads(path.read_text())
                if isinstance(existing, list):
                    existing.append(data)
                else:
                    existing = [existing, data]
                path.write_text(json.dumps(existing, indent=2, default=str))
            else:
                path.write_text(json.dumps([data], indent=2, default=str))
        except Exception as e:
            logger.error(f"Error guardando métricas: {e}")


metrics = MetricsCollector()
