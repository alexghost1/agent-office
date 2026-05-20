"""Entrega local + Telegram para tareas programadas."""
import json
import os
from pathlib import Path
from datetime import datetime

OUT_DIR = Path(__file__).parent / "data" / "daily"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def save(task_name: str, content: str, agent: str = "main"):
    now = datetime.now()
    path = OUT_DIR / f"{now.strftime('%Y-%m-%d')}_{task_name}.json"
    entry = {
        "timestamp": now.isoformat(),
        "agent": agent,
        "task": task_name,
        "content": content[:2000],
    }
    path.write_text(json.dumps(entry, indent=2))
    print(f"📄 Guardado en {path}")

if __name__ == "__main__":
    import sys
    task = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    content = sys.stdin.read()
    save(task, content)
