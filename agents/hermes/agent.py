"""
HERMES Agent — Generación de leads y outreach
"""
import os
import datetime
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

AGENT_NAME = "hermes"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


class LeadExtractor:
    def __init__(self):
        self.sandbox = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"

    def search_instagram_leads(self, hashtags: list[str] = None, min_followers: int = 5000) -> list[dict]:
        if self.sandbox:
            logger.info(f"[SANDBOX] Búsqueda de leads con hashtags: {hashtags}")
            return [
                {"username": "ejemplo_empresario", "followers": 12500, "bio": "CEO en sector tech | inversor",
                 "engagement_rate": 0.045, "score": 75},
                {"username": "inversor_2024", "followers": 8700, "bio": "Business Angel | Startup Advisor",
                 "engagement_rate": 0.032, "score": 68},
            ]
        return []

    def score_lead(self, lead_data: dict) -> int:
        score = 0
        followers = lead_data.get("followers", 0)
        if 5000 <= followers < 50000:
            score += 20
        elif followers >= 50000:
            score += 30

        bio = lead_data.get("bio", "").lower()
        if any(w in bio for w in ["empresa", "ceo", "founder", "emprend", "director", "business"]):
            score += 20

        engagement = lead_data.get("engagement_rate", 0)
        if engagement > 0.03:
            score += 15

        return min(score, 100)

    def generate_outreach_message(self, lead: dict, step: int = 1) -> str:
        name = lead.get("username", "")
        if step == 1:
            return (
                f"Hola {name}, vi tu perfil y me gusta cómo estás construyendo tu presencia en el sector. "
                f"Por cierto, soy asesor financiero y ayudo a profesionales como tú a optimizar su patrimonio. "
                f"¿Te parece interesante?"
            )
        elif step == 2:
            return (
                f"Hola {name}, hace unos días te escribí. Solo quería compartirte este artículo "
                f"sobre planificación patrimonial para emprendedores. "
                f"Creo que puede serte útil. ¡Un saludo!"
            )
        else:
            return (
                f"Hola {name}, quería proponerte una llamada de 15 minutos para ver si puedo "
                f"aportarte valor en tu planificación financiera. Sin compromiso. ¿Cuándo te viene bien?"
            )


class HermesAgent:
    def __init__(self):
        self.name = AGENT_NAME
        self.system_prompt = SYSTEM_PROMPT_PATH.read_text()
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.sandbox_mode = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
        self.extractor = LeadExtractor()
        logger.info(f"{self.name} inicializado | sandbox={self.sandbox_mode}")

    def run(self, task: str, context: dict = None) -> dict:
        logger.info(f"{self.name} ejecutando: {task[:80]}")
        task_lower = task.lower()
        # Detectar ubicación en la tarea
        ubicacion = self._detectar_ubicacion(task_lower)

        if any(w in task_lower for w in ["lead", "extraer", "buscar", "rastrea", "obtener", "encontrar", "prospecto"]):
            if ubicacion:
                estrategia = self.lead_hunt_por_ubicacion(ubicacion, target=(context or {}).get("target", 10))
                return {"agent": self.name, "status": "ok", **estrategia}
            else:
                leads = self.daily_lead_hunt(target=(context or {}).get("target", 10))
                return {"agent": self.name, "status": "ok", "leads": leads}
        if any(w in task_lower for w in ["outreach", "contactar", "mensaje", "secuencia"]):
            result = self.run_outreach_sequence()
            return {"agent": self.name, "status": "ok", "outreach": result}
        if any(w in task_lower for w in ["cualificar", "qualify", "puntuar", "score"]):
            lead = context or {}
            score = self.extractor.score_lead(lead)
            return {"agent": self.name, "status": "ok", "score": score, "lead": lead}
        if any(w in task_lower for w in ["crm", "actualizar", "pipeline", "reporte"]):
            report = self.weekly_pipeline_report()
            return {"agent": self.name, "status": "ok", "pipeline": report}
        return {"agent": self.name, "task": task, "status": "unknown_command"}

    def _detectar_ubicacion(self, task_lower: str) -> str:
        ubicaciones = [
            "tarragona", "reus", "barcelona", "madrid", "valencia", "sevilla",
            "bilbao", "zaragoza", "málaga", "alicante", "murcia", "palma",
            "cataluña", "catalunya", "españa", "latam", "mexico", "argentina",
        ]
        for u in ubicaciones:
            if u in task_lower:
                return u
        return ""

    def report(self) -> dict:
        return {"agent": self.name, "status": "operational", "sandbox": self.sandbox_mode}

    def lead_hunt_por_ubicacion(self, ubicacion: str, target: int = 10) -> dict:
        """Estrategia de búsqueda de leads para una ubicación específica."""
        ubicacion_cap = ubicacion.capitalize()

        # Hashtags específicos por ubicación
        hashtags_geo = {
            "tarragona": ["#tarragona", "#reus", "#campdeTarragona", "#empresastarragona"],
            "reus":      ["#reus", "#tarragona", "#campdeTarragona", "#reusempresa"],
            "barcelona": ["#barcelona", "#empresasbcn", "#emprendedoresbcn", "#startupbcn"],
            "madrid":    ["#madrid", "#empresasmadrid", "#emprendedoresmadrid", "#startupsmadrid"],
            "cataluña":  ["#cataluña", "#catalunya", "#empresescatalanes", "#pimecatalunya"],
            "valencia":  ["#valencia", "#empresasvalencia", "#emprendedoresvalencia"],
        }

        # Hashtags financieros base + geo
        hashtags_base = [
            "#asesorfinanciero", "#planificacionpatrimonial",
            "#inversionespana", "#emprendedores", "#bancaprivada",
            "#patrimonio", "#libertadfinanciera",
        ]
        hashtags_geo_loc = hashtags_geo.get(ubicacion, [f"#{ubicacion}", f"#empresas{ubicacion}"])
        hashtags_total = hashtags_base + hashtags_geo_loc

        # Canales de búsqueda estratégicos
        canales = [
            {
                "canal": "Instagram",
                "hashtags": hashtags_total,
                "criterio": f"Empresarios y directivos activos en {ubicacion_cap} con perfil financiero",
                "filtros": "seguidores >2000, bio menciona empresa/negocio, posts activos últimos 30 días",
                "volumen_estimado": "15-30 perfiles/día",
            },
            {
                "canal": "LinkedIn",
                "busqueda": f"CEO OR Director OR Empresario en {ubicacion_cap}",
                "filtros": "sector: servicios, inmobiliario, industria, comercio",
                "nota": "Requiere Sales Navigator o búsqueda manual",
                "volumen_estimado": "10-20 perfiles/día",
            },
            {
                "canal": "Google Maps / Directorios",
                "busqueda": f"empresas medianas {ubicacion_cap} site:infocif.es OR site:einforma.com",
                "criterio": "Empresas con facturación >500k€, propietario identificable",
                "volumen_estimado": "5-10 empresas/día",
            },
            {
                "canal": "Eventos locales",
                "fuentes": [
                    f"Cámara de Comercio de {ubicacion_cap}",
                    "CECOT (patronal empresarial Tarragona)" if "tarragona" in ubicacion or "reus" in ubicacion else f"Patronal de {ubicacion_cap}",
                    "Networking eventos Eventbrite",
                ],
                "nota": "Leads de mayor calidad, conversión más alta",
            },
        ]

        # Mensaje de outreach adaptado a la zona
        mensaje_ejemplo = self.extractor.generate_outreach_message({
            "username": f"empresario_{ubicacion}",
            "bio": f"Empresario en {ubicacion_cap}",
            "location": ubicacion_cap,
        }, step=1)

        # Guardar estrategia en CORTEX
        try:
            from core.memory.chroma_store import ChromaStore
            store = ChromaStore()
            store.store("strategies", f"Estrategia leads {ubicacion_cap}: {str(canales[:2])}",
                        metadata={"agent": "hermes", "ubicacion": ubicacion, "event_type": "lead_strategy"})
        except Exception:
            pass

        logger.info(f"HERMES generó estrategia de leads para {ubicacion_cap}")

        return {
            "ubicacion": ubicacion_cap,
            "estrategia": canales,
            "hashtags_instagram": hashtags_total,
            "mensaje_outreach_ejemplo": mensaje_ejemplo,
            "proximos_pasos": [
                f"1. Buscar en Instagram: {' '.join(hashtags_geo_loc[:3])}",
                f"2. Revisar directorio CECOT/Cámara Comercio {ubicacion_cap}",
                f"3. Configurar alerta Google: 'empresario {ubicacion_cap} patrimonio'",
                f"4. Conectar Apify para scraping automático de Instagram",
            ],
            "sandbox": self.sandbox_mode,
        }

    def daily_lead_hunt(self, target: int = 10) -> list[dict]:
        hashtags = ["#asesorfinanciero", "#planificacionpatrimonial", "#inversionespana",
                     "#emprendedores", "#bancaprivada"]
        leads = self.extractor.search_instagram_leads(hashtags=hashtags, min_followers=5000)
        for lead in leads:
            lead["score"] = self.extractor.score_lead(lead)
        qualified = [l for l in leads if l["score"] >= 65]
        logger.info(f"Lead hunt: {len(leads)} encontrados, {len(qualified)} cualificados")
        try:
            from core.memory.chroma_store import ChromaStore
            store = ChromaStore()
            for lead in qualified:
                store.store("leads", f"Lead: {lead.get('username', '')} - {lead.get('bio', '')}",
                            metadata={"agent": "hermes", "score": lead.get("score", 0), "source": "instagram"})
        except Exception:
            pass
        return qualified[:target]

    def run_outreach_sequence(self):
        try:
            from core.memory.chroma_store import ChromaStore
            store = ChromaStore()
            leads = store.search("leads", "lead outreach pendiente", n_results=5, min_relevance=0.0)
            results = []
            for lead in leads:
                msg = self.extractor.generate_outreach_message(
                    lead["metadata"], step=1)
                results.append({"lead": lead["metadata"].get("username", ""), "message": msg[:60]})
            return results
        except Exception as e:
            logger.error(f"Error en outreach: {e}")
            return []

    def qualify_inbound(self, contact_data: dict) -> dict:
        score = self.extractor.score_lead(contact_data)
        return {"score": score, "qualified": score >= 65, "data": contact_data}

    def update_crm(self, lead_id: str, event: str, notes: str):
        try:
            from core.memory.chroma_store import ChromaStore
            store = ChromaStore()
            store.store("leads", notes, metadata={"agent": "hermes", "lead_id": lead_id, "event": event})
            return True
        except Exception:
            return False

    def weekly_pipeline_report(self) -> dict:
        try:
            from core.memory.chroma_store import ChromaStore
            store = ChromaStore()
            total = store.count("leads")
            return {"total_leads": total, "status": "ok"}
        except Exception:
            return {"total_leads": 0, "status": "error"}


if __name__ == "__main__":
    agent = HermesAgent()
    print(agent.report())
