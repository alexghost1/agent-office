"""
Instagram Watchlist Monitor — IRIS
Lee las 3 colecciones, detecta señales relevantes y genera el digest diario.
"""
from __future__ import annotations
import datetime
import json
import os
import random
from pathlib import Path
from loguru import logger

WATCHLIST_PATH = Path(__file__).parent.parent.parent.parent / "data" / "instagram" / "watchlist.json"
REPORTS_DIR    = Path(__file__).parent.parent.parent.parent / "data" / "instagram" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_watchlist() -> dict:
    if not WATCHLIST_PATH.exists():
        return {}
    return json.loads(WATCHLIST_PATH.read_text())


def _fetch_account_activity(handle: str, token: str) -> dict:
    """Intenta obtener actividad real via Graph API; si no hay token, devuelve vacío."""
    if not token:
        return {}
    try:
        import requests
        # Búsqueda pública de usuario — requiere token de usuario con permisos instagram_basic
        url = f"https://graph.facebook.com/v19.0/{handle}?fields=media_count,biography&access_token={token}"
        resp = requests.get(url, timeout=10)
        return resp.json() if resp.status_code == 200 else {}
    except Exception:
        return {}


def generate_daily_report(router=None) -> dict:
    """
    Genera el reporte diario de monitoreo de las 100 cuentas.
    Con token de Instagram: datos reales. Sin token: análisis estratégico con LLM.
    """
    watchlist = _load_watchlist()
    if not watchlist:
        return {"status": "error", "error": "Watchlist no encontrada"}

    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    today = datetime.date.today().isoformat()
    colecciones = watchlist.get("colecciones", {})

    sections = {}
    for col_name, col_data in colecciones.items():
        cuentas = col_data.get("cuentas", [])
        high_rel = [c for c in cuentas if c.get("relevancia") == "alta"]
        sections[col_name] = {
            "total": len(cuentas),
            "alta_relevancia": len(high_rel),
            "descripcion": col_data.get("descripcion", ""),
            "objetivo": col_data.get("objetivo", ""),
            "cuentas_muestra": [c["handle"] for c in high_rel[:5]],
        }

    if router:
        resumen = _generate_llm_digest(colecciones, router)
    else:
        resumen = _generate_static_digest(colecciones)

    report = {
        "fecha": today,
        "tipo": "monitoreo_diario_instagram",
        "colecciones": sections,
        "total_cuentas": watchlist.get("total", 100),
        "resumen_estrategico": resumen,
        "alertas": _detect_alerts(colecciones),
        "acciones_recomendadas": _suggest_actions(colecciones),
        "proxima_revision": today,
    }

    path = REPORTS_DIR / f"monitor_{today}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    logger.info(f"IRIS Watchlist: reporte guardado en {path}")
    return report


def _generate_llm_digest(colecciones: dict, router) -> str:
    competencia = [c["handle"] for c in colecciones.get("competencia", {}).get("cuentas", []) if c.get("relevancia") == "alta"]
    inspiracion = [c["handle"] for c in colecciones.get("contenido_inspiracion", {}).get("cuentas", []) if c.get("relevancia") == "alta"]
    prospects   = [c["handle"] for c in colecciones.get("prospects_entorno_local", {}).get("cuentas", []) if c.get("relevancia") == "alta"]

    today = datetime.date.today().strftime("%A %d de %B")
    prompt = f"""Eres IRIS, directora de redes sociales de Alexandre García (asesor financiero, SafeBrok, Tarragona).

Hoy es {today}. Tienes 3 colecciones privadas de Instagram bajo vigilancia:

COMPETENCIA ({len(competencia)} cuentas clave): {', '.join(competencia[:8])}
CONTENIDO/INSPIRACIÓN ({len(inspiracion)} cuentas clave): {', '.join(inspiracion[:8])}
PROSPECTS Y ENTORNO LOCAL ({len(prospects)} cuentas clave): {', '.join(prospects[:8])}

Genera el resumen estratégico diario de 15 minutos para Alexandre. Estructura:

1. **COMPETENCIA — 3 puntos de atención hoy**
   - Qué deberías revisar en las cuentas de banca privada y asesores digitales
   - Posibles movimientos estacionales (mayo 2026: declaración de la renta, mercados)
   - Gap de contenido detectable que puedes explotar

2. **INSPIRACIÓN — 2 formatos a analizar hoy**
   - Qué tipo de contenido suele funcionar esta época del año en finanzas España
   - Formato específico a intentar esta semana (con por qué)

3. **PROSPECTS — 2 señales locales a detectar**
   - Qué buscar en las cuentas de Tarragona y entorno (eventos, noticias empresa, inmobiliario)
   - Una acción concreta de networking digital hoy

4. **ACCIÓN DEL DÍA** — Una sola cosa que Alexandre debe hacer en Instagram en los próximos 30 minutos

Sé específico, práctico y orientado a generar leads cualificados en Tarragona. Tono: briefing ejecutivo, directo."""

    try:
        return router.call(
            prompt,
            task_description="digest diario monitoreo Instagram cuentas",
            max_tokens=900,
        )
    except Exception as e:
        logger.error(f"IRIS LLM digest error: {e}")
        return _generate_static_digest(colecciones)


def _generate_static_digest(colecciones: dict) -> str:
    today = datetime.date.today().strftime("%d/%m/%Y")
    comp   = colecciones.get("competencia", {}).get("cuentas", [])
    inspir = colecciones.get("contenido_inspiracion", {}).get("cuentas", [])
    prosp  = colecciones.get("prospects_entorno_local", {}).get("cuentas", [])

    picks_comp   = random.sample([c["handle"] for c in comp   if c.get("relevancia") == "alta"], min(3, len([c for c in comp   if c.get("relevancia") == "alta"])))
    picks_inspir = random.sample([c["handle"] for c in inspir if c.get("relevancia") == "alta"], min(2, len([c for c in inspir if c.get("relevancia") == "alta"])))
    picks_prosp  = random.sample([c["handle"] for c in prosp  if c.get("relevancia") == "alta"], min(3, len([c for c in prosp  if c.get("relevancia") == "alta"])))

    return (
        f"DIGEST {today}\n\n"
        f"COMPETENCIA — Revisar hoy: @{'  @'.join(picks_comp)}\n"
        f"→ Analizar temas usados, frecuencia y formato de sus últimas 3 publicaciones.\n\n"
        f"INSPIRACIÓN — Cuentas a estudiar hoy: @{'  @'.join(picks_inspir)}\n"
        f"→ Identificar el post con más engagement de la semana y adaptar el formato.\n\n"
        f"PROSPECTS — Señales locales: @{'  @'.join(picks_prosp)}\n"
        f"→ Buscar publicaciones sobre eventos empresariales, ventas de activos o cambios corporativos.\n\n"
        f"ACCIÓN DEL DÍA: Deja un comentario de valor en el post más reciente de una cuenta de competencia alta relevancia. "
        f"Visibilidad orgánica ante su audiencia — que es exactamente tu audiencia objetivo."
    )


def _detect_alerts(colecciones: dict) -> list[dict]:
    alerts = []
    today = datetime.date.today()
    # Señales estacionales automáticas
    mes = today.month
    if mes == 5:
        alerts.append({"tipo": "estacional", "mensaje": "Mayo: temporada declaración de renta — alta demanda de contenido fiscal", "urgencia": "alta"})
        alerts.append({"tipo": "oportunidad", "mensaje": "Competidores activos en contenido IRPF — diferenciarte con enfoque patrimonial", "urgencia": "media"})
    if mes == 6:
        alerts.append({"tipo": "estacional", "mensaje": "Junio: revisión semestral de carteras — momento ideal para publicar análisis", "urgencia": "alta"})
    alerts.append({"tipo": "monitoreo", "mensaje": f"Verificar cuentas inmobiliario lujo Tarragona — mercado activo en {today.strftime('%B')}", "urgencia": "media"})
    return alerts


def _suggest_actions(colecciones: dict) -> list[dict]:
    today = datetime.date.today()
    actions = [
        {
            "accion": "Revisar últimas 3 publicaciones de @indexacapital y @myinvestor_es",
            "razon": "Principales competidores digitales — detectar temas que están usando",
            "tiempo": "5 min",
            "prioridad": "alta"
        },
        {
            "accion": "Buscar en @cambratarragonaofi y @tarragona_connecta eventos próximos",
            "razon": "Identificar eventos de networking donde presentarte como asesor",
            "tiempo": "3 min",
            "prioridad": "alta"
        },
        {
            "accion": "Revisar el post más viral de la semana en @garciademarina o @patrimonioypropósito",
            "razon": "Adaptar formato exitoso al estilo SafeBrok",
            "tiempo": "5 min",
            "prioridad": "media"
        },
        {
            "accion": "Comentar con valor en una publicación de @remax_tarragona o @engelvoelkers_tarragona",
            "razon": "Visibilidad ante clientes potenciales HNWI que siguen cuentas inmobiliarias de lujo",
            "tiempo": "2 min",
            "prioridad": "alta"
        },
    ]
    return actions


def update_account_notes(handle: str, coleccion: str, notes: str) -> bool:
    """Actualiza las notas de una cuenta en la watchlist."""
    try:
        watchlist = _load_watchlist()
        cuentas = watchlist["colecciones"][coleccion]["cuentas"]
        for c in cuentas:
            if c["handle"] == handle:
                c["notas"] = notes
                c["last_updated"] = datetime.date.today().isoformat()
                break
        WATCHLIST_PATH.write_text(json.dumps(watchlist, indent=2, ensure_ascii=False))
        return True
    except Exception as e:
        logger.error(f"Error actualizando watchlist: {e}")
        return False


def get_watchlist_summary() -> dict:
    watchlist = _load_watchlist()
    cols = watchlist.get("colecciones", {})
    return {
        col: {
            "total": len(data.get("cuentas", [])),
            "alta_relevancia": sum(1 for c in data.get("cuentas", []) if c.get("relevancia") == "alta"),
            "objetivo": data.get("objetivo", ""),
        }
        for col, data in cols.items()
    }
