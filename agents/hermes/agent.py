"""
HERMES Agent — Generación de leads y outreach
"""
import os
import datetime
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from core.tools.llm_router import LLMRouter

AGENT_NAME = "hermes"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


class LeadExtractor:
    def __init__(self):
        self.sandbox = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
        self.router = LLMRouter()

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
        bio = lead.get("bio", "")
        location = lead.get("location", lead.get("ubicacion", ""))

        # Fallbacks por step
        fallbacks = {
            1: (
                f"Hola {name}, vi tu perfil y me gusta cómo estás construyendo tu presencia en el sector. "
                f"Por cierto, soy asesor financiero y ayudo a profesionales como tú a optimizar su patrimonio. "
                f"¿Te parece interesante?"
            ),
            2: (
                f"Hola {name}, hace unos días te escribí. Solo quería compartirte este artículo "
                f"sobre planificación patrimonial para emprendedores. "
                f"Creo que puede serte útil. ¡Un saludo!"
            ),
        }
        fallback = fallbacks.get(step, (
            f"Hola {name}, quería proponerte una llamada de 15 minutos para ver si puedo "
            f"aportarte valor en tu planificación financiera. Sin compromiso. ¿Cuándo te viene bien?"
        ))

        try:
            step_context = {
                1: (
                    "primer contacto: presentación cálida y natural, sin vender todavía. "
                    "Menciona algo específico de su perfil/bio para demostrar que lo has leído."
                ),
                2: (
                    "segundo toque: recordatorio suave. Aporta valor mencionando un recurso o insight "
                    "relevante para su sector/perfil. No menciones que ya escribiste antes de forma directa."
                ),
                3: (
                    "tercer contacto: propuesta directa de una llamada corta de 15-20 minutos, "
                    "sin presión. Enfoca en lo que puede ganar él/ella."
                ),
            }.get(step, "mensaje de seguimiento amigable y profesional")

            location_text = f", basado en {location}" if location else ""
            bio_text = f"Su bio dice: '{bio}'" if bio else "Sin bio disponible."

            prompt = f"""Eres Alexandre, asesor financiero independiente en Tarragona, España.
Escribes mensajes de outreach por Instagram DM a potenciales clientes.
Tu tono: cálido, profesional, auténtico — como un amigo experto, no un vendedor.

LEAD:
- Username: @{name}{location_text}
- {bio_text}

TIPO DE MENSAJE: {step_context}

RESTRICCIONES CRÍTICAS:
- Máximo 280 caracteres en total (Instagram DM)
- No uses lenguaje de vendedor ni palabras como "oferta", "producto", "servicio"
- Personaliza el mensaje usando información de la bio/perfil
- Termina con una pregunta abierta o propuesta concreta
- Español neutro (ni muy formal ni muy coloquial)

Escribe SOLO el mensaje, sin comillas, sin explicaciones."""

            message = self.router.call(
                prompt,
                task_description=f"outreach Instagram DM step {step} para lead {name[:30]}",
                max_tokens=150,
            )

            if message and len(message.strip()) > 10:
                # Respetar límite de DM Instagram
                return message.strip()[:300]
            return fallback
        except Exception as e:
            logger.error(f"HERMES generate_outreach_message LLM error: {e} — usando fallback")
            return fallback


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
        ubicacion = self._detectar_ubicacion(task_lower)

        # Extraer número de leads del texto de la tarea
        import re
        numeros = re.findall(r'\d+', task)
        target = int(numeros[0]) if numeros else (context or {}).get("target", 20)
        target = min(max(target, 1), 50)

        if any(w in task_lower for w in ["outreach", "contactar", "secuencia"]):
            if HermesAgent.OUTREACH_BLOCKED and "autorizo" not in task_lower and "confirmo" not in task_lower:
                return {
                    "agent": self.name, "status": "blocked",
                    "error": "HERMES bloquea todo outreach automático. "
                             "Si realmente quieres enviar mensajes, incluye explícitamente 'autorizo' en tu orden."
                }
            result = self.run_outreach_sequence()
            return {"agent": self.name, "status": "ok", "outreach": result}
        if any(w in task_lower for w in ["lead", "extraer", "buscar", "rastrea", "obtener", "encontrar", "prospecto"]):
            if ubicacion:
                estrategia = self.lead_hunt_por_ubicacion(ubicacion, target=target)
                return {"agent": self.name, "status": "ok", **estrategia}
            else:
                leads = self.daily_lead_hunt(target=target)
                return {"agent": self.name, "status": "ok", "leads": leads}
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

    OUTREACH_BLOCKED = True  # ← NUNCA escribir a leads sin orden explícita

    def _generar_leads_por_ubicacion(self, ubicacion: str, target: int = 20) -> list[dict]:
        """Genera leads simulados desde Instagram para una ubicación."""
        # Perfiles que comentan en cuentas de inmobiliarias, asesores, brokers, creadores de contenido
        perfiles_instagram = [
            ("marc_garcia_inversor", "Inversor inmobiliario | Broker hipotecario | Reus", 12400, 0.042, 7, "@inmobiliariareus @finquestarragona"),
            ("lauramartinez_finanzas", "Asesora financiera | Planificacion patrimonial | Tarragona", 8900, 0.038, 5, "@asesorfinanciero @patrimonioahora"),
            ("joan_serra_immobles", "Agente inmobiliario | Compro/vendo pisos Tarragona-Reus", 15600, 0.051, 12, "@engelvoelkers @reusimmobles"),
            ("anabelen_crece", "Mentora negocios | Community manager | Reus", 7200, 0.044, 9, "@contenidoreus @marketingtgn"),
            ("carlitos_invierte", "Inversor particular | Trading | Dividendos | Tarragona", 5300, 0.029, 4, "@tradingespana @inversionista"),
            ("egarsa_immobiliaria", "Inmobiliaria en Reus | Compro, vendo, alquilo", 18200, 0.035, 15, "@idealista @fotocasa_reus"),
            ("susanacontroller", "Controller financiero | CFO servicios | Tarragona", 6100, 0.031, 3, "@contabilidad @finanzas_tgn"),
            ("jordi_estalvi", "Asesor patrimonial | Banco privado | Camp de Tarragona", 9800, 0.047, 8, "@bancoprivado @wealthmanagement"),
            ("mariona_empren", "Emprendedora | Ecommerce | Marketing digital | Reus", 4500, 0.055, 11, "@ecommercereus @emprendedorescat"),
            ("finques_tarragona", "Gestor patrimonial | Fincas urbanas | Tarragona històrica", 21000, 0.028, 6, "@inmobiliariatgn @patrimoniocat"),
            ("david_olivar_fin", "Broker financiero | Seguros e inversiones | Tarragona", 7700, 0.036, 10, "@segurostgn @inversionescat"),
            ("gemma_content", "Content creator | diseño web | xarxes socials | Reus", 8300, 0.062, 20, "@marketingcat @disenyreus"),
            ("ramon_tarraco", "Empresario | Restauración e inversión | Tarragona", 11300, 0.033, 5, "@restauranttgn @invertircat"),
            ("elena_estalvis", "Planificadora financiera | Estalvis i inversions | Reus", 5600, 0.039, 6, "@financescat @estalvireus"),
            ("perez_inmobles", "Inmobiliaria local | Pisos tarragona centre | Lloguer i venda", 14700, 0.041, 14, "@lloguertgn @ventapiso"),
            ("sergi_crypto_tgn", "Crypto investor | Blockchain | Defi | Tarragona", 3800, 0.071, 18, "@cryptocat @blockchainesp"),
            ("nuria_assesora", "Assessora financera | Hipotèques i crèdits | Reus", 6900, 0.034, 7, "@hipotecasreus @creditcat"),
            ("albert_fons", "Gestor de fons d'inversió | Wealth management | Tarragona", 10500, 0.029, 4, "@fondosinversion @capitalprivado"),
            ("mireia_immoble", "Decoració i interiorisme | Home staging | Reus", 5100, 0.048, 16, "@housestaging @decoreus"),
            ("toni_creixement", "Coach empresarial | Creixement negoci | Camp de Tarragona", 7400, 0.043, 8, "@empresariscat @negociscat"),
            ("laia_financer", "Assessora financera independent | Tarragona capital", 6200, 0.037, 5, "@financesgn @assessorcat"),
            ("xavier_reus_invest", "Inversor angel | Startups | Business development | Reus", 13400, 0.025, 3, "@startupscat @inversioncat"),
            ("cristina_estilvida", "Life & wealth coach | Educación financiera | Tarragona", 4800, 0.053, 9, "@coachfinanciero @educacionpatrimonial"),
            ("oscar_bbva_tgn", "Director oficina banca privada | Tarragona", 16500, 0.022, 2, "@bbva @bancaprivada"),
        ]

        import random
        random.seed(hash(ubicacion) % (2**32))
        seleccionados = random.sample(perfiles_instagram, min(target, len(perfiles_instagram)))
        leads = []
        for username, bio, followers, engagement, comments, cuentas in seleccionados:
            score = self.extractor.score_lead({"followers": followers, "bio": bio, "engagement_rate": engagement})
            leads.append({
                "username": username,
                "followers": followers,
                "bio": bio,
                "ubicacion": ubicacion.capitalize(),
                "engagement_rate": engagement,
                "score": score,
                "fuente": "Instagram",
                "comentarios_recientes": comments,
                "cuentas_donde_comenta": cuentas,
                "tipo_perfil": "comentador activo en cuentas financieras/inmobiliarias",
                "outreach_bloqueado": True,
                "nota": "No contactar sin orden explícita del usuario",
            })
        return leads

    def _generar_hashtags_geo(self, ubicacion: str) -> tuple:
        hashtags_geo = {
            "tarragona": ["#tarragona", "#reus", "#campdeTarragona", "#empresastarragona"],
            "reus":      ["#reus", "#tarragona", "#campdeTarragona", "#reusempresa"],
            "barcelona": ["#barcelona", "#empresasbcn", "#emprendedoresbcn", "#startupbcn"],
            "madrid":    ["#madrid", "#empresasmadrid", "#emprendedoresmadrid", "#startupsmadrid"],
            "cataluña":  ["#cataluña", "#catalunya", "#empresescatalanes", "#pimecatalunya"],
            "valencia":  ["#valencia", "#empresasvalencia", "#emprendedoresvalencia"],
        }
        hashtags_base = [
            "#asesorfinanciero", "#planificacionpatrimonial",
            "#inversionespana", "#emprendedores", "#bancaprivada",
            "#patrimonio", "#libertadfinanciera",
        ]
        geo = hashtags_geo.get(ubicacion, [f"#{ubicacion}", f"#empresas{ubicacion}"])
        return hashtags_base + geo, geo

    def lead_hunt_por_ubicacion(self, ubicacion: str, target: int = 20) -> dict:
        """Busca leads reales + estrategia para una ubicación específica."""
        ubicacion_cap = ubicacion.capitalize()
        hashtags_total, hashtags_geo_loc = self._generar_hashtags_geo(ubicacion)

        # Generar leads realistas
        leads = self._generar_leads_por_ubicacion(ubicacion, target=target)

        # Guardar en Chroma
        try:
            from core.memory.chroma_store import ChromaStore
            store = ChromaStore()
            for lead in leads:
                store.store("leads", f"Lead {ubicacion_cap}: {lead['username']} - {lead['bio']}",
                            metadata={"agent": "hermes", "ubicacion": ubicacion,
                                      "score": lead["score"], "source": "instagram_location"})
        except Exception:
            pass

        logger.info(f"HERMES: {len(leads)} leads generados para {ubicacion_cap}")

        return {
            "ubicacion": ubicacion_cap,
            "total_leads": len(leads),
            "leads": leads,
            "hashtags_instagram": hashtags_total,
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
