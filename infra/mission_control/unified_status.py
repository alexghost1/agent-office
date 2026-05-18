#!/usr/bin/env python3
from __future__ import annotations
"""
JARVIS + Oficina de Agentes — Dashboard de Estado Unificado
Muestra estado completo del sistema AGI.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Paths
JARVIS_DIR         = Path("/Users/usuario/Mark-XXXIX")
OFFICE_DIR         = Path("/Users/usuario/agent-office")

TASKS_PATH         = JARVIS_DIR / "memory" / "autonomous_tasks.json"
CONTROL_PATH       = JARVIS_DIR / "memory" / "control.json"
MIND_LOG_PATH      = JARVIS_DIR / "memory" / "mind_log.json"
API_COSTS_PATH     = OFFICE_DIR / "data" / "logs" / "api_costs.jsonl"
CAMPAIGN_PATH      = OFFICE_DIR / "data" / "campaigns" / "plan_18may_1jun_2026.json"

AGENTS = ["nexus", "atlas", "hermes", "iris", "herald", "cortex", "forge"]


def _load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _load_jsonl(path: Path) -> List[Dict]:
    lines = []
    if not path.exists():
        return lines
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    lines.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return lines


def get_jarvis_tasks() -> dict:
    data = _load_json(TASKS_PATH, [])
    tasks = data if isinstance(data, list) else data.get("tasks", [])
    total    = len(tasks)
    done     = len([t for t in tasks if t.get("status") == "done" or t.get("done")])
    failed   = len([t for t in tasks if t.get("status") == "failed"])
    running  = len([t for t in tasks if t.get("status") == "running"])
    pending  = total - done - failed - running
    return {
        "total": total,
        "done": done,
        "failed": failed,
        "running": running,
        "pending": max(pending, 0),
        "recent": tasks[-3:] if tasks else [],
    }


def get_control_state() -> dict:
    return _load_json(CONTROL_PATH, {"paused": False, "killswitch": False, "pause_reason": ""})


def get_last_mind_cycle() -> dict:
    logs = _load_json(MIND_LOG_PATH, [])
    if not logs:
        return {}
    last = logs[-1] if isinstance(logs, list) else {}
    return last


def get_office_costs() -> dict:
    entries = _load_jsonl(API_COSTS_PATH)
    today   = datetime.now().strftime("%Y-%m-%d")
    today_total   = sum(e.get("cost", 0) for e in entries if e.get("date") == today)
    overall_total = sum(e.get("cost", 0) for e in entries)
    return {
        "today": round(today_total, 6),
        "total": round(overall_total, 6),
        "entries": len(entries),
    }


def get_campaign_posts() -> dict:
    data = _load_json(CAMPAIGN_PATH, {})
    if not data:
        return {"available": False}
    posts = data.get("posts", data.get("content", data.get("items", [])))
    if isinstance(posts, list):
        total     = len(posts)
        published = len([p for p in posts if p.get("status") == "published" or p.get("published")])
        pending   = total - published
        return {"total": total, "published": published, "pending": pending, "available": True}
    return {"available": True, "data": str(data)[:100]}


def get_agent_statuses() -> List[dict]:
    results = []
    if str(OFFICE_DIR) not in sys.path:
        sys.path.insert(0, str(OFFICE_DIR))
    try:
        from dotenv import load_dotenv
        load_dotenv(OFFICE_DIR / ".env", override=False)
    except Exception:
        pass
    for agent_name in AGENTS:
        try:
            import importlib
            mod = importlib.import_module(f"agents.{agent_name}.agent")
            cls = getattr(mod, f"{agent_name.capitalize()}Agent")
            instance = cls()
            report = instance.report()
            status = report.get("status", "unknown")
            results.append({"agent": agent_name, "status": status, "ok": status == "operational"})
        except Exception as e:
            results.append({"agent": agent_name, "status": "error", "ok": False, "error": str(e)[:60]})
    return results


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.columns import Columns
        from rich import box
        use_rich = True
        console = Console()
    except ImportError:
        use_rich = False

    tasks   = get_jarvis_tasks()
    control = get_control_state()
    mind    = get_last_mind_cycle()
    costs   = get_office_costs()
    campaign = get_campaign_posts()
    agents  = get_agent_statuses()

    if use_rich:
        # Header
        mind_state = "KILLSWITCH" if control.get("killswitch") else ("PAUSADO" if control.get("paused") else "ACTIVO")
        state_color = "red" if control.get("killswitch") else ("yellow" if control.get("paused") else "green")
        console.print(Panel(
            f"[bold]JARVIS + Oficina de Agentes  —  {now}[/bold]\n"
            f"Estado JARVIS Mind: [{state_color}]{mind_state}[/{state_color}]"
            + (f" | Razón: {control.get('pause_reason','')}" if control.get("pause_reason") else ""),
            title="AGI SISTEMA UNIFICADO",
            border_style="cyan"
        ))

        # JARVIS Tasks
        t_table = Table(title="Tareas JARVIS Mind", box=box.SIMPLE_HEAVY)
        t_table.add_column("Estado", style="cyan")
        t_table.add_column("Cantidad", justify="right")
        t_table.add_row("Pendientes", str(tasks["pending"]))
        t_table.add_row("Ejecutando", str(tasks["running"]))
        t_table.add_row("[green]Hechas", f"[green]{tasks['done']}")
        t_table.add_row("[red]Falladas", f"[red]{tasks['failed']}")
        t_table.add_row("[bold]Total", f"[bold]{tasks['total']}")

        # Costs
        c_table = Table(title="Costes Oficina API", box=box.SIMPLE_HEAVY)
        c_table.add_column("Periodo", style="cyan")
        c_table.add_column("Coste USD", justify="right")
        c_table.add_row("Hoy", f"${costs['today']:.4f}")
        c_table.add_row("Total acumulado", f"${costs['total']:.4f}")
        c_table.add_row("Registros", str(costs["entries"]))

        console.print(Columns([t_table, c_table]))

        # Agents
        a_table = Table(title="Estado Agentes Oficina", box=box.SIMPLE_HEAVY)
        a_table.add_column("Agente", style="bold")
        a_table.add_column("Estado")
        for ag in agents:
            color = "green" if ag["ok"] else "red"
            a_table.add_row(ag["agent"].upper(), f"[{color}]{ag['status']}[/{color}]")
        console.print(a_table)

        # Campaign
        if campaign.get("available"):
            c_info = (
                f"Total: {campaign.get('total','?')} | "
                f"Publicados: {campaign.get('published','?')} | "
                f"Pendientes: {campaign.get('pending','?')}"
            )
        else:
            c_info = "No disponible"
        console.print(Panel(c_info, title="Campaña 18-May / 1-Jun 2026", border_style="blue"))

        # Last mind cycle
        if mind:
            console.print(Panel(
                f"Tipo: {mind.get('type','?')} | Ts: {mind.get('ts','?')}",
                title="Último ciclo JARVIS Mind",
                border_style="magenta"
            ))

    else:
        # Plain print fallback
        sep = "-" * 60
        print(sep)
        print(f"AGI SISTEMA UNIFICADO — {now}")
        print(sep)
        mind_state = "KILLSWITCH" if control.get("killswitch") else ("PAUSADO" if control.get("paused") else "ACTIVO")
        print(f"JARVIS Mind: {mind_state}")
        if control.get("pause_reason"):
            print(f"  Razón pausa: {control['pause_reason']}")
        print()
        print("TAREAS JARVIS:")
        print(f"  Pendientes : {tasks['pending']}")
        print(f"  Ejecutando : {tasks['running']}")
        print(f"  Hechas     : {tasks['done']}")
        print(f"  Falladas   : {tasks['failed']}")
        print(f"  Total      : {tasks['total']}")
        print()
        print("COSTES OFICINA API:")
        print(f"  Hoy        : ${costs['today']:.4f}")
        print(f"  Acumulado  : ${costs['total']:.4f}")
        print(f"  Registros  : {costs['entries']}")
        print()
        print("AGENTES OFICINA:")
        for ag in agents:
            mark = "OK" if ag["ok"] else "ERR"
            print(f"  [{mark}] {ag['agent'].upper():10} {ag['status']}")
        print()
        print("CAMPAÑA 18-May/1-Jun 2026:")
        if campaign.get("available"):
            print(f"  Total: {campaign.get('total','?')} | Publicados: {campaign.get('published','?')} | Pendientes: {campaign.get('pending','?')}")
        else:
            print("  No disponible")
        if mind:
            print()
            print(f"ÚLTIMO CICLO MIND: tipo={mind.get('type','?')} | {mind.get('ts','?')}")
        print(sep)


if __name__ == "__main__":
    main()
