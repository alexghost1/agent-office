"""
COMPLIANCE — Validador de contenido financiero SafeBrok
Última barrera antes de cualquier publicación pública.
Valida contra MiFID II + estándares de marca SafeBrok.
"""
from __future__ import annotations
import json
import datetime
import os
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from core.tools.llm_router import LLMRouter

AGENT_NAME     = "compliance"
SYSTEM_PROMPT  = (Path(__file__).parent / "prompts" / "system.md").read_text()
REPORTS_DIR    = Path(__file__).parent.parent.parent / "data" / "compliance"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ── Criterios rápidos sin LLM ─────────────────────────────────────────────────

_RENTABILIDAD_TRIGGERS = [
    "rentabilidad garantizada", "garantizo", "siempre sube", "nunca pierde",
    "ganarás", "ganarás un", "% anual garantizado", "retorno garantizado",
    "seguro que sube", "sin riesgo de pérdida", "100% seguro",
]

_URGENCIA_TRIGGERS = [
    "última oportunidad", "solo hasta el", "actúa ya", "no pierdas más tiempo",
    "el mercado no espera", "ahora o nunca", "oferta limitada",
    "últimas plazas", "cierra en", "vence el",
]

_PERSONALIZADO_TRIGGERS = [
    "deberías invertir en", "te recomiendo comprar", "compra este", "compra ya",
    "para tu situación lo mejor es", "invierte en este fondo",
    "este producto es perfecto para ti", "te recomiendo este etf",
]

_DISCLAIMER_KEYWORDS = [
    "riesgo de pérdida", "rentabilidades pasadas", "no garantizan",
    "consulta con tu asesor", "no es asesoramiento", "carácter informativo",
    "puede perder", "riesgo de capital", "inversión conlleva riesgo",
    "rentabilidad no garantizada",
]

_PRODUCTOS_FINANCIEROS = [
    "fondo de inversión", "etf", "acción", "bono", "derivado",
    "criptomoneda", "bitcoin", "ethereum", "plan de pensiones",
    "seguro de vida ahorro", "unit linked", "renta variable",
    "renta fija", "materia prima", "divisa",
]


def _quick_check(texto: str) -> dict:
    """Verificación rápida de señales obvias sin llamada LLM."""
    t = texto.lower()
    issues = {}

    if any(k in t for k in _RENTABILIDAD_TRIGGERS):
        issues["rentabilidades"] = "FALLO"
    if any(k in t for k in _URGENCIA_TRIGGERS):
        issues["urgencia_compra"] = "FALLO"
    if any(k in t for k in _PERSONALIZADO_TRIGGERS):
        issues["asesoramiento_personalizado"] = "FALLO"

    # Productos mencionados sin disclaimer → advertencia
    tiene_producto = any(k in t for k in _PRODUCTOS_FINANCIEROS)
    tiene_disclaimer = any(k in t for k in _DISCLAIMER_KEYWORDS)
    if tiene_producto and not tiene_disclaimer:
        issues["productos_sin_disclaimer"] = "REVISAR"
        issues["disclaimer_presente"] = "REVISAR"

    return issues


class ComplianceAgent:
    def __init__(self):
        self.name       = AGENT_NAME
        self.router     = LLMRouter()
        self.sandbox    = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
        logger.info(f"{self.name} — Validador MiFID II | sandbox={self.sandbox}")

    # ── API pública ───────────────────────────────────────────────────────────

    def validate(self, content: str, context: str = "") -> dict:
        """
        Valida contenido contra los 6 criterios MiFID II + marca SafeBrok.
        Devuelve dict con veredicto, score, criterios y corrección si procede.
        """
        logger.info(f"COMPLIANCE validando: {content[:60]}...")

        # 1. Check rápido sin LLM
        quick_issues = _quick_check(content)

        # 2. Si hay fallos obvios, podemos devolver ya BLOQUEADO sin gastar tokens
        #    pero siempre pasamos por LLM para tener la corrección sugerida.
        force_block = bool(quick_issues)

        prompt = f"""{SYSTEM_PROMPT}

---

Contenido a validar:
\"\"\"
{content}
\"\"\"

Contexto adicional: {context or 'Post de Instagram para cuenta de asesor financiero SafeBrok.'}

{"NOTA: El análisis rápido ya detectó señales en: " + str(list(quick_issues.keys())) + ". Confirma y añade corrección." if force_block else ""}

Evalúa los 6 criterios y responde ÚNICAMENTE con el JSON estructurado indicado en tu sistema.
No añadas texto fuera del JSON."""

        try:
            raw = self.router.call(
                prompt,
                task_description="validación compliance MiFID II contenido financiero",
                max_tokens=1000,
            )
            result = self._parse_result(raw, quick_issues)
        except Exception as e:
            logger.error(f"COMPLIANCE LLM error: {e} — usando quick check")
            result = self._fallback_result(quick_issues, content)

        # 3. Guardar reporte
        self._save_report(content, result)

        # 4. Notificar si bloqueado
        if result.get("veredicto") == "BLOQUEADO":
            self._notify_blocked(result)

        return result

    def batch_validate(self, items: list[dict]) -> list[dict]:
        """Valida una lista de contenidos. Cada item: {"id": str, "content": str}."""
        results = []
        for item in items:
            r = self.validate(item.get("content", ""), item.get("context", ""))
            r["id"] = item.get("id", "")
            results.append(r)
        return results

    def run(self, task: str, context: dict = None) -> dict:
        ctx = context or {}
        task_lower = task.lower()

        # Detectar contenido a validar
        content_to_check = ctx.get("content", "") or ctx.get("texto", "") or ctx.get("caption", "")

        if not content_to_check:
            # Si la tarea es texto largo (el propio contenido a validar)
            if len(task) > 80 and not any(k in task_lower for k in ["valida", "revisar", "check", "analiza"]):
                content_to_check = task
            elif "valida" in task_lower or "revisar" in task_lower or "check" in task_lower:
                # La tarea describe qué validar pero el contenido viene en context
                content_to_check = ctx.get("text", task)
            else:
                content_to_check = task

        if not content_to_check.strip():
            return {"agent": self.name, "status": "error", "error": "No se recibió contenido para validar"}

        result = self.validate(content_to_check, ctx.get("context", ""))
        result["agent"] = self.name
        result["status"] = "ok"
        return result

    def report(self) -> dict:
        # Estadísticas de los últimos reportes
        reports = sorted(REPORTS_DIR.glob("*.json"), reverse=True)[:20]
        ok = bloq = 0
        for r in reports:
            try:
                d = json.loads(r.read_text())
                if d.get("veredicto") == "OK":
                    ok += 1
                else:
                    bloq += 1
            except Exception:
                pass
        return {
            "agent": self.name,
            "status": "operational",
            "sandbox": self.sandbox,
            "ultimos_reportes": len(reports),
            "aprobados": ok,
            "bloqueados": bloq,
            "tasa_aprobacion": f"{round(ok / max(ok + bloq, 1) * 100)}%",
        }

    # ── Internos ──────────────────────────────────────────────────────────────

    def _parse_result(self, raw: str, quick_issues: dict) -> dict:
        """Extrae JSON de la respuesta del LLM."""
        try:
            # Buscar bloque JSON
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
                # Merge con quick_issues si hay discrepancia (quick siempre gana para FALLOs)
                if quick_issues:
                    criterios = data.get("criterios", {})
                    for k, v in quick_issues.items():
                        if v == "FALLO":
                            criterios[k] = "FALLO"
                    data["criterios"] = criterios
                    # Recalcular veredicto
                    if any(v == "FALLO" for v in criterios.values()):
                        data["veredicto"] = "BLOQUEADO"
                return data
        except Exception as e:
            logger.warning(f"COMPLIANCE parse error: {e}")
        return self._fallback_result(quick_issues, raw)

    def _fallback_result(self, quick_issues: dict, content: str) -> dict:
        """Resultado de emergencia si el LLM falla."""
        fallos = [f"{k}: {v}" for k, v in quick_issues.items() if v == "FALLO"]
        veredicto = "BLOQUEADO" if fallos else "OK"
        score = 100 - (len(fallos) * 20)
        return {
            "veredicto": veredicto,
            "score_cumplimiento": max(score, 0),
            "criterios": {
                "rentabilidades": quick_issues.get("rentabilidades", "OK"),
                "asesoramiento_personalizado": quick_issues.get("asesoramiento_personalizado", "OK"),
                "urgencia_compra": quick_issues.get("urgencia_compra", "OK"),
                "productos_sin_disclaimer": quick_issues.get("productos_sin_disclaimer", "OK"),
                "disclaimer_presente": quick_issues.get("disclaimer_presente", "OK"),
                "tono_marca": "OK",
            },
            "fallos": fallos,
            "correccion_sugerida": "",
            "alerta_alexandre": f"⚠️ Contenido bloqueado: {', '.join(fallos)}" if fallos else "",
            "fuente": "quick_check_fallback",
        }

    def _save_report(self, content: str, result: dict):
        try:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = REPORTS_DIR / f"check_{ts}_{result.get('veredicto','?')}.json"
            report = {
                "timestamp": datetime.datetime.now().isoformat(),
                "content_preview": content[:200],
                **result,
            }
            path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"COMPLIANCE save_report error: {e}")

    def _notify_blocked(self, result: dict):
        try:
            from core.tools.notifier import Notifier
            fallos = result.get("fallos", [])
            correccion = result.get("correccion_sugerida", "")
            msg = (
                f"🚨 COMPLIANCE — Contenido BLOQUEADO\n\n"
                f"Criterios fallados:\n" +
                "\n".join(f"  ❌ {f}" for f in fallos) +
                (f"\n\n✏️ Corrección sugerida:\n{correccion[:400]}" if correccion else "") +
                f"\n\nScore: {result.get('score_cumplimiento', 0)}/100"
            )
            Notifier().send(msg, priority="high", agent=AGENT_NAME)
        except Exception as e:
            logger.warning(f"COMPLIANCE notify error: {e}")


# ── Función standalone para llamar desde IRIS ─────────────────────────────────

def check_before_publish(content: str, context: str = "") -> dict:
    """
    Punto de entrada para que IRIS (u otros agentes) validen antes de publicar.
    Devuelve: {"ok": bool, "result": dict_completo}
    """
    agent = ComplianceAgent()
    result = agent.validate(content, context)
    return {
        "ok": result.get("veredicto") == "OK",
        "veredicto": result.get("veredicto"),
        "score": result.get("score_cumplimiento"),
        "fallos": result.get("fallos", []),
        "correccion": result.get("correccion_sugerida", ""),
        "result": result,
    }


if __name__ == "__main__":
    # Test rápido
    agent = ComplianceAgent()
    test_cases = [
        "¿Quieres rentabilidades garantizadas del 12% anual? Invierte en este ETF ahora, última oportunidad antes del cierre del mercado.",
        "El IBEX 35 cerró la semana con una subida del 1.2%. La inflación en España se sitúa en el 2.8%. Recuerda que invertir conlleva riesgo de pérdida.",
        "Los fondos indexados son una herramienta de inversión con costes bajos. Rentabilidades pasadas no garantizan resultados futuros.",
    ]
    for i, t in enumerate(test_cases, 1):
        r = agent.validate(t)
        print(f"\nTest {i}: {r.get('veredicto')} (score: {r.get('score_cumplimiento')})")
        if r.get("fallos"):
            for f in r["fallos"]:
                print(f"  ❌ {f}")
