#!/usr/bin/env python3
"""
Panel de Control — Oficina de Agentes IA
Ejecuta: python control.py
"""
import sys
import json
import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich import box

load_dotenv()
console = Console()

AGENTES = {
    "1": ("nexus",  "NEXUS",  "Orquestador — dale cualquier tarea"),
    "2": ("atlas",  "ATLAS",  "Mercados — briefing, noticias, análisis"),
    "3": ("hermes", "HERMES", "Leads — buscar, puntuar, outreach"),
    "4": ("iris",   "IRIS",   "Instagram — ideas de contenido, captions"),
    "5": ("herald", "HERALD", "Email — clasificar bandeja, borradores"),
    "6": ("cortex", "CORTEX", "Memoria — guardar, buscar, patrones"),
    "7": ("forge",  "FORGE",  "Infra — logs, mejoras, optimización"),
}

TAREAS_EJEMPLO = {
    "nexus":  "Genera el briefing ejecutivo de hoy para el propietario",
    "atlas":  "Dame el resumen de mercados de hoy: IBEX, S&P500 y EUR/USD",
    "hermes": "Busca 5 leads cualificados en Instagram para servicios de banca privada",
    "iris":   "Genera 3 ideas de contenido financiero para Instagram esta semana",
    "herald": "Clasifica los emails no leídos por prioridad P0-P3",
    "cortex": "Muestra los patrones detectados en los últimos logs",
    "forge":  "Analiza los logs de hoy y propón optimizaciones",
}

def cargar_agente(nombre):
    try:
        module_name = f"agents.{nombre}.agent"
        module = __import__(module_name, fromlist=["*"])
        cls_name = f"{nombre.capitalize()}Agent"
        return getattr(module, cls_name)()
    except Exception as e:
        console.print(f"[red]Error cargando {nombre}: {e}[/red]")
        return None

def mostrar_menu():
    console.clear()
    console.print(Panel.fit(
        "[bold magenta]🤖 OFICINA DE AGENTES IA — Panel de Control[/bold magenta]\n"
        "[dim]Modo: SANDBOX — ninguna acción real se ejecutará[/dim]",
        border_style="magenta"
    ))

    tabla = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    tabla.add_column("#", width=3)
    tabla.add_column("Agente", width=10)
    tabla.add_column("Descripción", width=45)

    for num, (_, nombre, desc) in AGENTES.items():
        tabla.add_row(num, f"[bold]{nombre}[/bold]", desc)

    tabla.add_row("0", "[red]SALIR[/red]", "Cerrar el panel")
    console.print(tabla)

def ejecutar_tarea(agente_key, agente_nombre, tarea):
    console.print(f"\n[cyan]→ Enviando tarea a {agente_nombre}...[/cyan]")
    console.print(f"[dim]Tarea: {tarea}[/dim]\n")

    agente = cargar_agente(agente_key)
    if not agente:
        return

    try:
        resultado = agente.run(tarea)
        console.print(Panel(
            _formatear_resultado(resultado),
            title=f"[green]✓ Respuesta de {agente_nombre}[/green]",
            border_style="green",
            padding=(1, 2)
        ))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def _formatear_resultado(resultado):
    if not isinstance(resultado, dict):
        return str(resultado)

    lines = []

    # Mercados tradicionales
    if "market" in resultado:
        lines.append("[bold cyan]── MERCADOS ──[/bold cyan]")
        for nombre, datos in resultado["market"].items():
            if isinstance(datos, dict):
                last = datos.get("last", datos.get("usd", "?"))
                cambio = datos.get("change_5d", datos.get("change_24h", 0)) or 0
                flecha = "📈" if cambio >= 0 else "📉"
                signo = "+" if cambio >= 0 else ""
                lines.append(f"  {flecha} {nombre}: {last:,.2f}  ({signo}{cambio:.2f}%)")

    # Crypto
    if "crypto" in resultado:
        lines.append("\n[bold yellow]── CRYPTO ──[/bold yellow]")
        for sym, datos in resultado["crypto"].items():
            if sym == "total_market_cap":
                mcap = datos.get("usd", 0)
                ch = datos.get("change_24h", 0) or 0
                signo = "+" if ch >= 0 else ""
                lines.append(f"  🌐 Market Cap Total: ${mcap/1e12:.2f}T  ({signo}{ch:.2f}%)")
            elif isinstance(datos, dict):
                price = datos.get("usd", "?")
                ch24 = datos.get("change_24h", 0) or 0
                ch7d = datos.get("change_7d", 0) or 0
                flecha = "📈" if ch24 >= 0 else "📉"
                signo = "+" if ch24 >= 0 else ""
                lines.append(f"  {flecha} {sym}: ${price:,.2f}  24h: {signo}{ch24:.2f}%  7d: {ch7d:.2f}%")

    # Noticias con fuentes
    if "news" in resultado:
        fuentes = resultado.get("fuentes_consultadas", [])
        total = resultado.get("noticias", len(resultado["news"]))
        lines.append(f"\n[bold green]── NOTICIAS ({total} artículos · {len(fuentes)} fuentes) ──[/bold green]")
        if fuentes:
            lines.append(f"  [dim]Fuentes: {', '.join(sorted(fuentes)[:8])}[/dim]")
        for i, art in enumerate(resultado["news"], 1):
            score = art.get("user_score", 0.5)
            stars = "⭐" if score > 0.7 else ""
            lines.append(f"  {i}. [{art.get('source','')}] {art.get('title','')[:65]} {stars}")

    # Estrategia de leads por ubicación
    if "ubicacion" in resultado and "estrategia" in resultado:
        lines.append(f"\n[bold magenta]── ESTRATEGIA LEADS: {resultado['ubicacion'].upper()} ──[/bold magenta]")
        for canal in resultado.get("estrategia", []):
            lines.append(f"\n  [bold cyan]📍 {canal.get('canal','').upper()}[/bold cyan]")
            for k, v in canal.items():
                if k == "canal":
                    continue
                if isinstance(v, list):
                    lines.append(f"    {k}: {', '.join(v[:4])}")
                else:
                    lines.append(f"    {k}: {str(v)[:80]}")
        if resultado.get("proximos_pasos"):
            lines.append("\n  [bold yellow]PRÓXIMOS PASOS:[/bold yellow]")
            for paso in resultado["proximos_pasos"]:
                lines.append(f"    {paso}")

    # Resto de campos
    for k, v in resultado.items():
        if k in ("agent", "sandbox", "timestamp", "market", "crypto", "status",
                 "news", "noticias", "fuentes_consultadas", "guardado_en_cortex",
                 "ubicacion", "estrategia", "proximos_pasos", "hashtags_instagram",
                 "mensaje_outreach_ejemplo"):
            continue
        if isinstance(v, str) and len(v) > 20:
            lines.append(f"\n[bold]{k.upper()}:[/bold]\n{v}")
        elif isinstance(v, (dict, list)):
            lines.append(f"\n[bold]{k}:[/bold] {json.dumps(v, ensure_ascii=False, indent=2)}")
        else:
            lines.append(f"[bold]{k}:[/bold] {v}")

    return "\n".join(lines) if lines else str(resultado)

def main():
    while True:
        mostrar_menu()
        opcion = Prompt.ask("\n[bold]Elige un agente[/bold]", default="0")

        if opcion == "0":
            console.print("\n[dim]Oficina detenida. Hasta pronto.[/dim]\n")
            break

        if opcion not in AGENTES:
            console.print("[red]Opción no válida[/red]")
            continue

        agente_key, agente_nombre, _ = AGENTES[opcion]
        ejemplo = TAREAS_EJEMPLO[agente_key]

        console.print(f"\n[bold cyan]Agente seleccionado: {agente_nombre}[/bold cyan]")
        console.print(f"[dim]Ejemplo: {ejemplo}[/dim]")

        tarea = Prompt.ask(
            "\n[bold]¿Qué tarea le asignas?[/bold]\n[dim](ENTER para usar el ejemplo)[/dim]",
            default=ejemplo
        )

        ejecutar_tarea(agente_key, agente_nombre, tarea)
        Prompt.ask("\n[dim]Pulsa ENTER para volver al menú[/dim]", default="")

if __name__ == "__main__":
    main()
