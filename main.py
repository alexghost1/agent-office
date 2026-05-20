#!/usr/bin/env python3
"""
OFICINA DE AGENTES IA — 400% MODE
Dashboard en vivo · Métricas real-time · Auto-recuperación
"""
import sys
import os
import signal
import time
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich import box
from rich.columns import Columns

load_dotenv()
console = Console()

AGENT_MODULES = ["cortex", "hermes", "iris", "atlas", "herald", "forge", "nexus",
                 "hunter", "copywriter", "mail_agent", "content_creator", "cmo_agent",
                 "instagram_agent", "robin"]

# Mapeo nombre_modulo → nombre_display (para agentes con guión en el nombre)
AGENT_DISPLAY_NAMES = {
    "mail_agent":       "mail-agent",
    "content_creator":  "content-creator",
    "cmo_agent":        "cmo-agent",
    "instagram_agent":  "instagram-agent",
}
REFRESH_INTERVAL = 2
DASHBOARD_ENABLED = os.getenv("DASHBOARD_ENABLED", "true").lower() == "true"


def init_agents():
    # Mapeo nombre_modulo → nombre_clase para agentes con nombres compuestos
    cls_overrides = {
        "mail_agent":       "MailAgentAgent",
        "content_creator":  "ContentCreatorAgent",
        "cmo_agent":        "CmoAgentAgent",
        "instagram_agent":  "InstagramAgentAgent",
    }
    agents = {}
    for name in AGENT_MODULES:
        try:
            module = __import__(f"agents.{name}.agent", fromlist=["*"])
            cls_name = cls_overrides.get(name, f"{name.capitalize()}Agent")
            agent_cls = getattr(module, cls_name)
            agent = agent_cls()
            # Usar nombre display (con guión) como clave pública
            display = AGENT_DISPLAY_NAMES.get(name, name)
            agents[display] = agent
        except Exception as e:
            logger.error(f"Error iniciando {name}: {e}")
            display = AGENT_DISPLAY_NAMES.get(name, name)
            agents[display] = None
    return agents


def build_dashboard(agents: dict, nexus=None) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="agents_panel", ratio=2),
        Layout(name="metrics_panel", ratio=1),
    )

    title = Text("🤖 OFICINA DE AGENTES IA — 400% MODE", style="bold magenta", justify="center")
    layout["header"].update(Panel(title, box=box.ROUNDED, style="bright_blue"))

    agent_table = Table(show_header=True, box=box.SIMPLE, title="[bold]AGENTES[/bold]")
    agent_table.add_column("Agente", style="cyan", width=10)
    agent_table.add_column("Estado", width=14)
    agent_table.add_column("Modo", width=10)

    health_statuses = {}
    if nexus:
        try:
            from core.tools.health import health
            health_statuses = health.check_all(nexus.agents)
        except Exception:
            pass

    for name in AGENT_MODULES:
        agent = agents.get(name)
        hs = health_statuses.get(name, {})
        h_status = hs.get("status", "")

        if agent is None:
            status_str = "[red]Error[/red]"
            mode_str = "[red]N/A[/red]"
        elif h_status == "healthy":
            status_str = "[bold green]✅ 400%[/bold green]"
            mode_str = "[green]Turbo[/green]"
        elif h_status == "degraded":
            status_str = "[yellow]⚠️ Degraded[/yellow]"
            mode_str = "[yellow]Limitado[/yellow]"
        elif h_status == "unavailable":
            status_str = "[red]🔴 Offline[/red]"
            mode_str = "[red]Parado[/red]"
        else:
            try:
                report = agent.report()
                if report.get("status") == "operational":
                    status_str = "[green]✅ 400%[/green]"
                    mode_str = "[green]Turbo[/green]"
                else:
                    status_str = "[red]Error[/red]"
                    mode_str = "[red]N/A[/red]"
            except Exception:
                status_str = "[red]Error[/red]"
                mode_str = "[red]N/A[/red]"

        agent_table.add_row(name.upper(), status_str, mode_str)

    metrics_text = ""
    try:
        from core.tools.metrics import metrics
        metrics_text = metrics.summary()
    except Exception:
        metrics_text = "Métricas no disponibles"

    layout["agents_panel"].update(Panel(agent_table, box=box.ROUNDED, style="bright_cyan"))
    layout["metrics_panel"].update(Panel(
        Text(metrics_text, style="bright_green"),
        title="[bold]📊 MÉTRICAS[/bold]",
        box=box.ROUNDED,
        style="bright_green",
    ))

    start_time = getattr(build_dashboard, "_start", None)
    if start_time is None:
        start_time = time.time()
        build_dashboard._start = start_time
    uptime = time.time() - start_time

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    footer_text = (
        f"[dim]{now}[/dim]  |  "
        f"[bold green]🟢 Uptime: {int(uptime//3600):02d}h{int((uptime%3600)//60):02d}m[/bold green]  |  "
        f"[dim]Ctrl+C para detener[/dim]"
    )
    layout["footer"].update(Panel(Text(footer_text, justify="center"), box=box.ROUNDED, style="dim"))

    return layout


def main():
    console.clear()
    console.print("[bold magenta]\n🔥 OFICINA DE AGENTES IA — 400% MODE INICIANDO...\n[/bold magenta]")

    with console.status("[bold green]Cargando agentes...[/bold green]") as status:
        agents = init_agents()
        status.update("[bold green]Inicializando NEXUS...[/bold green]")
        nexus = agents.get("nexus")
        if nexus:
            try:
                nexus.start()
                logger.info("🚀 NEXUS 400% scheduler activo")
            except Exception as e:
                logger.error(f"Error scheduler: {e}")
        status.update("[bold green]Sistema listo[/bold green]")
        time.sleep(0.5)

    from core.tools.notifier import Notifier
    Notifier().send("🔥 Oficina 400% iniciada — todos los agentes operativos",
                    priority="normal", agent="nexus")

    shutdown_flag = threading.Event()

    def shutdown(signum, frame):
        if shutdown_flag.is_set():
            return
        shutdown_flag.set()
        console.print("\n[bold yellow]⏳ Deteniendo oficina 400%...[/bold yellow]")
        if nexus:
            try:
                nexus.stop()
            except Exception:
                pass
        logger.info("Oficina detenida")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if DASHBOARD_ENABLED:
        with Live(build_dashboard(agents, nexus), refresh_per_second=1 / REFRESH_INTERVAL, screen=True) as live:
            while not shutdown_flag.is_set():
                live.update(build_dashboard(agents, nexus))
                time.sleep(REFRESH_INTERVAL)
    else:
        console.print(build_dashboard(agents, nexus))
        signal.pause()


if __name__ == "__main__":
    main()
