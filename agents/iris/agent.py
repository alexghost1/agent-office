"""
IRIS Agent — Directora del Departamento de Redes
Supervisión · Estrategia · Creación de contenido · Growth
"""
import os
import datetime
import json
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from core.tools.llm_router import LLMRouter

AGENT_NAME = "iris"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"

INSTAGRAM_API = "https://graph.facebook.com/v19.0"
CONTENT_PLANS_DIR = Path(__file__).parent.parent.parent / "data" / "campaigns"
REVIEWS_DIR = Path(__file__).parent.parent.parent / "data" / "reviews"


class InstagramTool:
    def __init__(self):
        self.access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
        self.account_id = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
        self.sandbox = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"

    def _headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    def get_media(self, limit: int = 20) -> list[dict]:
        if not self.access_token:
            logger.warning("INSTAGRAM_ACCESS_TOKEN no configurado")
            return []
        import requests
        url = f"{INSTAGRAM_API}/{self.account_id}/media?fields=id,caption,media_type,media_url,like_count,comments_count,timestamp&limit={limit}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=30)
            return resp.json().get("data", [])
        except Exception as e:
            logger.error(f"Instagram get_media error: {e}")
            return []

    def get_insights(self, media_id: str) -> dict:
        if not self.access_token:
            return {}
        import requests
        url = f"{INSTAGRAM_API}/{media_id}/insights?metric=engagement,impressions,reach,saved"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=30)
            return resp.json()
        except Exception as e:
            logger.error(f"Instagram insights error: {e}")
            return {}

    def create_post(self, image_url: str, caption: str, scheduled_time: str = None) -> dict:
        if self.sandbox:
            logger.info(f"[SANDBOX] Post creado: {caption[:40]}...")
            return {"success": True, "sandbox": True, "caption": caption[:40]}
        if not self.access_token:
            return {"success": False, "error": "Token no configurado"}
        import requests
        payload = {"image_url": image_url, "caption": caption, "access_token": self.access_token}
        if scheduled_time:
            payload["published"] = "false"
            payload["scheduled_publish_time"] = scheduled_time
        try:
            resp = requests.post(f"{INSTAGRAM_API}/{self.account_id}/media", json=payload, timeout=30)
            return resp.json()
        except Exception as e:
            logger.error(f"Instagram create_post error: {e}")
            return {"success": False, "error": str(e)}

    def get_audience_insights(self) -> dict:
        if not self.access_token:
            return {}
        import requests
        url = f"{INSTAGRAM_API}/{self.account_id}/insights?metric=audience_city,audience_country,audience_gender,audience_age"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=30)
            return resp.json()
        except Exception as e:
            logger.error(f"Instagram audience error: {e}")
            return {}

    def send_dm(self, user_id: str, message: str) -> dict:
        if self.sandbox:
            logger.info(f"[SANDBOX] DM a {user_id}: {message[:40]}...")
            return {"success": True, "sandbox": True}
        return {"success": False, "error": "DM no implementado sin sandbox"}


class IrisAgent:
    def __init__(self):
        self.name = AGENT_NAME
        self.system_prompt = SYSTEM_PROMPT_PATH.read_text()
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.sandbox_mode = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
        self.instagram = InstagramTool()
        self.cortex = self._load_cortex()
        self.router = LLMRouter()
        CONTENT_PLANS_DIR.mkdir(parents=True, exist_ok=True)
        REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"{self.name} — Directora Redes | sandbox={self.sandbox_mode}")

    def _load_cortex(self):
        try:
            from agents.cortex.agent import CortexAgent
            return CortexAgent()
        except Exception:
            logger.warning("IRIS no pudo conectar con CORTEX")
            return None

    def _get_noticias_relevantes(self, topic: str = "") -> list[dict]:
        ctx = self.cortex
        if not ctx:
            return []
        try:
            return ctx.get_news(topic=topic, n=5)
        except Exception:
            return []

    def _consultar_atlas(self, query: str = "mercados tendencias contenido") -> list[dict]:
        try:
            from agents.atlas.agent import AtlasAgent
            a = AtlasAgent()
            r = a.run(query)
            return r.get("ideas", r.get("noticias", []))
        except Exception:
            return []

    def run(self, task: str, context: dict = None) -> dict:
        logger.info(f"{self.name} ejecutando: {task[:80]}")
        task_lower = task.lower()
        ctx = context or {}

        if "plan mensual" in task_lower or "plan del mes" in task_lower or "sidecar" in task_lower:
            plan = self.crear_plan_mensual()
            return {"agent": self.name, "status": "ok", "plan_mensual": plan}
        if "revisión quincenal" in task_lower or "revisar contenido" in task_lower or "dia 15" in task_lower:
            revision = self.revision_quincenal()
            return {"agent": self.name, "status": "ok", "revision": revision}
        if "post" in task_lower or "publicar" in task_lower:
            caption = self.create_caption(task, "profesional")
            result = self.instagram.create_post(image_url=ctx.get("image_url", ""), caption=caption)
            return {"agent": self.name, "status": "ok", "result": result, "caption": caption}
        if "idea" in task_lower or "content" in task_lower:
            ideas = self.generate_content_ideas(ctx.get("n", 5), ctx.get("topic", ""))
            return {"agent": self.name, "status": "ok", "ideas": ideas}
        if "caption" in task_lower:
            caption = self.create_caption(task, ctx.get("tone", "profesional"))
            return {"agent": self.name, "status": "ok", "caption": caption}
        if "analiza" in task_lower or "perfil" in task_lower or "análisis" in task_lower or "métrica" in task_lower or "insight" in task_lower:
            if "perfil" in task_lower or "analiza" in task_lower:
                analisis = self.analyze_instagram_profile()
                return {"agent": self.name, "status": "ok", "analisis": analisis}
            media = self.instagram.get_media(limit=10)
            return {"agent": self.name, "status": "ok", "media": media}
        if "crecimiento" in task_lower or "estrategia" in task_lower or "growth" in task_lower:
            estrategia = self.growth_strategy()
            return {"agent": self.name, "status": "ok", "estrategia": estrategia}
        if "programar" in task_lower or "schedule" in task_lower:
            caption = self.create_caption(task)
            return {"agent": self.name, "status": "ok", "scheduled": True, "caption": caption}
        return {"agent": self.name, "task": task, "status": "unknown_command"}

    def report(self) -> dict:
        return {"agent": self.name, "status": "operational", "sandbox": self.sandbox_mode}

    # ─── PLAN MENSUAL (DÍA 1) ────────────────────────────────────────────

    def crear_plan_mensual(self) -> dict:
        hoy = datetime.date.today()
        mes = hoy.month
        año = hoy.year
        nombre_mes = hoy.strftime("%B").capitalize()
        logger.info(f"📅 Creando plan mensual de contenido — {nombre_mes} {año}")

        ideas = self.generate_content_ideas(12, topic="planificación patrimonial mercados 2026")
        noticias = self._get_noticias_relevantes("finanzas mercados economía")
        efemerides = self._obtener_efemerides(mes)

        semanas = []
        num_semana = 1
        for bloque_inicio in range(0, len(ideas), 3):
            bloque = ideas[bloque_inicio:bloque_inicio + 3]
            semana = {
                "semana": num_semana,
                "titulo": f"Semana {num_semana} — {self._tema_semana(num_semana)}",
                "posts": [],
            }
            for i, idea in enumerate(bloque):
                dia_semana = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado"][i % 6] if i < 6 else "domingo"
                hora = ["12:00", "18:00", "20:00"][i % 3]
                semana["posts"].append({
                    "dia": dia_semana,
                    "hora": hora,
                    "topic": idea["topic"],
                    "category": idea.get("category", "educación"),
                    "format": idea.get("format", "post"),
                    "caption_preview": self.create_caption(idea["topic"])[:120],
                })
            semanas.append(semana)
            num_semana += 1

        plan = {
            "mes": nombre_mes,
            "año": año,
            "creado": hoy.isoformat(),
            "total_posts": sum(len(s["posts"]) for s in semanas),
            "distribucion": self._calcular_distribucion(semanas),
            "semanas": semanas,
            "noticias_referencia": [{"titulo": n.get("title", ""), "fuente": n.get("source", "")} for n in noticias[:5]],
            "efemerides": efemerides,
            "recomendaciones": self._recomendaciones_mensuales(mes),
            "alineacion_marca": self._check_alineacion_marca(semanas),
        }

        self._guardar_plan(plan)
        logger.info(f"✅ Plan mensual guardado: {plan['total_posts']} posts en {len(semanas)} semanas")
        try:
            from core.memory.chroma_store import ChromaStore
            store = ChromaStore()
            store.store("strategies", f"Plan mensual {nombre_mes} {año}: {plan['total_posts']} posts",
                        metadata={"agent": "iris", "type": "plan_mensual", "mes": nombre_mes})
        except Exception:
            pass

        from core.tools.notifier import Notifier
        Notifier().send(
            f"📅 Plan mensual {nombre_mes} listo: {plan['total_posts']} posts en {len(semanas)} semanas",
            priority="normal", agent=self.name,
        )

        return plan

    def _obtener_efemerides(self, mes: int) -> list[dict]:
        efemerides = {
            1: [{"dia": 1, "evento": "Año Nuevo — propósitos financieros"}],
            2: [{"dia": 14, "evento": "San Valentín — finanzas en pareja"}],
            3: [{"dia": 8, "evento": "Día de la Mujer — mujeres inversoras"}],
            4: [{"dia": 22, "evento": "Día de la Tierra — inversión sostenible"}],
            5: [{"dia": 1, "evento": "Día del Trabajo — estabilidad laboral y financiera"}],
            6: [{"dia": 21, "evento": "Verano — planificación vacacional"}],
            7: [{"dia": 11, "evento": "Mitad de año — revisión de cartera"}],
            8: [{"dia": 15, "evento": "Vacaciones — finanzas personales en verano"}],
            9: [{"dia": 23, "evento": "Otoño — nueva temporada, nueva estrategia"}],
            10: [{"dia": 12, "evento": "Día de la Hispanidad — mercados LATAM"}],
            11: [{"dia": 28, "evento": "Black Friday — consumo inteligente"}],
            12: [{"dia": 31, "evento": "Fin de año — balance patrimonial"}],
        }
        return efemerides.get(mes, [])

    def _tema_semana(self, num: int) -> str:
        temas = [
            "Planificación patrimonial",
            "Mercados financieros",
            "Educación financiera",
            "Detrás del asesor",
        ]
        return temas[(num - 1) % len(temas)]

    def _calcular_distribucion(self, semanas: list) -> dict:
        cats = {}
        for s in semanas:
            for p in s["posts"]:
                cat = p.get("category", "otro")
                cats[cat] = cats.get(cat, 0) + 1
        total = sum(cats.values()) or 1
        return {k: {"cantidad": v, "porcentaje": round(v / total * 100)} for k, v in sorted(cats.items())}

    def _recomendaciones_mensuales(self, mes: int) -> list[str]:
        base = [
            "Incluir casos de éxito (anonimizados) para generar confianza",
            "Publicar en horario de máxima audiencia (18-21h)",
            "Responder comentarios en las primeras 4 horas",
        ]
        if mes in (3, 4):
            base.append("Contenido sobre declaración de la renta")
        if mes in (11, 12):
            base.append("Contenido sobre planificación fiscal de fin de año")
        if mes == 1:
            base.append("Propósitos financieros de año nuevo — contenido viral")
        return base

    def _check_alineacion_marca(self, semanas: list) -> dict:
        cats = self._calcular_distribucion(semanas)
        warnings = []
        educ = cats.get("educación", {}).get("porcentaje", 0)
        merc = cats.get("mercados", {}).get("porcentaje", 0)
        if educ < 20:
            warnings.append("Contenido educativo por debajo del 20% recomendado")
        if merc < 10:
            warnings.append("Contenido de mercados escaso")
        return {"status": "ok" if not warnings else "revisar", "warnings": warnings}

    def _guardar_plan(self, plan: dict):
        try:
            mes = plan["mes"].lower()
            año = plan["año"]
            path = CONTENT_PLANS_DIR / f"plan_{mes}_{año}.json"
            path.write_text(json.dumps(plan, indent=2, default=str))
            logger.info(f"Plan guardado en {path}")
        except Exception as e:
            logger.error(f"Error guardando plan: {e}")

    # ─── REVISIÓN QUINCENAL (DÍA 15) ──────────────────────────────────────

    def revision_quincenal(self) -> dict:
        hoy = datetime.date.today()
        logger.info(f"🔍 Revisión quincenal de contenido — {hoy.isoformat()}")

        # 1. Cargar el plan del mes actual
        plan = self._cargar_plan_actual()
        plan_status = self._evaluar_cumplimiento_plan(plan) if plan else {"status": "sin_plan"}

        # 2. Consultar noticias recientes para ver si hay que actualizar algo
        noticias_recientes = self._get_noticias_relevantes("finanzas mercados economía actualidad")
        noticias_impacto = self._filtrar_noticias_impacto(noticias_recientes)

        # 3. Revisar si el contenido publicado hasta ahora está alineado
        media_reciente = self.instagram.get_media(limit=10)
        alineacion = self._revisar_alineacion(media_reciente)

        # 4. Sugerencias de actualización
        sugerencias = self._generar_sugerencias(plan, noticias_impacto, alineacion)

        # 5. Verificar tendencias y temas candentes
        tendencias = self._detectar_tendencias()

        revision = {
            "fecha": hoy.isoformat(),
            "mes": hoy.strftime("%B").capitalize(),
            "cumplimiento_plan": plan_status,
            "noticias_impacto": noticias_impacto[:3],
            "alineacion_contenido": alineacion,
            "tendencias_detectadas": tendencias,
            "sugerencias": sugerencias,
            "acciones_recomendadas": self._generar_acciones(sugerencias),
        }

        self._guardar_revision(revision)
        logger.info(f"✅ Revisión quincenal completada: {len(sugerencias)} sugerencias")

        try:
            from core.memory.chroma_store import ChromaStore
            store = ChromaStore()
            store.store("strategies", f"Revisión quincenal {hoy.isoformat()}: {len(sugerencias)} sugerencias",
                        metadata={"agent": "iris", "type": "revision_quincenal"})
        except Exception:
            pass

        from core.tools.notifier import Notifier
        Notifier().send(
            f"🔍 Revisión quincenal completa: {len(sugerencias)} sugerencias, "
            f"{len(noticias_impacto)} noticias de impacto detectadas",
            priority="normal", agent=self.name,
        )
        return revision

    def _cargar_plan_actual(self) -> dict:
        try:
            hoy = datetime.date.today()
            mes = hoy.strftime("%B").lower()
            año = hoy.year
            path = CONTENT_PLANS_DIR / f"plan_{mes}_{año}.json"
            if path.exists():
                return json.loads(path.read_text())
            # Fallback: mes anterior
            for p in sorted(CONTENT_PLANS_DIR.glob("plan_*.json"), reverse=True):
                return json.loads(p.read_text())
            return None
        except Exception:
            return None

    def _evaluar_cumplimiento_plan(self, plan: dict) -> dict:
        semanas = plan.get("semanas", [])
        total_planificado = sum(len(s["posts"]) for s in semanas)
        media = self.instagram.get_media(limit=50)
        total_publicado = len(media)
        # Calcular cuántos días del mes han pasado
        hoy = datetime.date.today()
        dias_transcurridos = hoy.day
        dias_totales = 28  # aproximado
        ratio_esperado = dias_transcurridos / dias_totales
        publicaciones_esperadas = round(total_planificado * ratio_esperado)
        cumplimiento = round(min(total_publicado / max(publicaciones_esperadas, 1), 1) * 100)
        return {
            "planificado": total_planificado,
            "publicado": total_publicado,
            "esperado_hasta_hoy": publicaciones_esperadas,
            "cumplimiento_pct": cumplimiento,
            "status": "al_dia" if cumplimiento >= 80 else "retraso" if cumplimiento >= 50 else "critico",
        }

    def _filtrar_noticias_impacto(self, noticias: list) -> list[dict]:
        palabras_clave = ["ibex", "bce", "fed", "tipos", "inflación", "mercado", "bolsa",
                          "financiero", "banco", "inversión", "fiscal", "impuesto",
                          "cripto", "bitcoin", "ethereum", "regulación"]
        impacto = []
        for n in noticias:
            titulo = (n.get("title", "") + " " + n.get("description", "")).lower()
            coincidencias = [p for p in palabras_clave if p in titulo]
            if coincidencias:
                impacto.append({
                    "titulo": n.get("title", ""),
                    "fuente": n.get("source", ""),
                    "coincidencias": coincidencias,
                    "sugerencia": f"Crear contenido sobre: {n.get('title', '')[:80]}",
                })
        return impacto

    def _revisar_alineacion(self, media: list[dict]) -> dict:
        if not media:
            return {"status": "sin_datos", "message": "No hay publicaciones para revisar"}
        warnings = []
        for m in media:
            caption = (m.get("caption") or "").lower()
            likes = m.get("like_count", 0)
            comments = m.get("comments_count", 0)
            engagement = (likes + comments) / max(likes + comments + 100, 1) * 100
            if engagement < 1:
                warnings.append(f"Bajo engagement en post {m.get('id', '')[:8]}: {engagement:.1f}%")
        return {
            "total_revisados": len(media),
            "warnings": warnings[:3],
            "status": "ok" if len(warnings) < 2 else "revisar",
        }

    def _detectar_tendencias(self) -> list[dict]:
        return [
            {"tema": "Planificación fiscal 2026", "fuerza": "alta", "formato": "carousel"},
            {"tema": "Inversión en inteligencia artificial", "fuerza": "media", "formato": "reel"},
            {"tema": "Carteras diversificadas en tiempos de incertidumbre", "fuerza": "alta", "formato": "post"},
        ]

    def _generar_sugerencias(self, plan: dict, noticias: list, alineacion: dict) -> list[str]:
        sugerencias = []
        if noticias:
            for n in noticias[:2]:
                sugerencias.append(f"📰 Crear contenido sobre: {n['titulo'][:80]}")
        if alineacion.get("warnings"):
            for w in alineacion["warnings"]:
                sugerencias.append(f"⚠️ {w}")
        sugerencias.append("🔄 Revisar hashtags y optimizar según engagement reciente")
        sugerencias.append("📊 Analizar competidores y detectar nuevos ángulos")
        return sugerencias

    def _generar_acciones(self, sugerencias: list) -> list[dict]:
        acciones = []
        for s in sugerencias:
            if "Crear contenido" in s:
                acciones.append({"accion": s, "prioridad": "alta", "plazo": "48h"})
            elif "Bajo engagement" in s:
                acciones.append({"accion": s, "prioridad": "media", "plazo": "1 semana"})
            else:
                acciones.append({"accion": s, "prioridad": "baja", "plazo": "2 semanas"})
        return acciones

    def _guardar_revision(self, revision: dict):
        try:
            hoy = datetime.date.today().isoformat()
            path = REVIEWS_DIR / f"revision_{hoy}.json"
            path.write_text(json.dumps(revision, indent=2, default=str))
        except Exception:
            pass

    # ─── ESTRATEGIA DE CRECIMIENTO ────────────────────────────────────────

    def estrategia_crecimiento(self) -> dict:
        logger.info("📈 Generando estrategia de crecimiento en redes")
        return {
            "pilares": [
                {"pilar": "Contenido educativo semanal", "frecuencia": "3x semana", "formato": "carousel"},
                {"pilar": "Behind the scenes del asesor", "frecuencia": "2x semana", "formato": "stories"},
                {"pilar": "Análisis de mercado en tiempo real", "frecuencia": "1x semana", "formato": "reel"},
            ],
            "metricas_objetivo": {
                "engagement_rate": ">4%",
                "crecimiento_semanal": "+2%",
                "leads_mensuales": ">10",
            },
            "acciones_inmediatas": [
                "Optimizar Bio con CTA clara",
                "Crear highlights destacados por categoría",
                "Programar contenido en horas pico (18-21h)",
                "Responder DMs en <4h",
            ],
            "calendario_crecimiento": self.weekly_strategy(),
        }

    # ─── MÉTODOS EXISTENTES (MEJORADOS) ───────────────────────────────────

    def generate_content_ideas(self, n: int = 5, topic: str = "") -> list[dict]:
        ideas_base = [
            {"topic": "Planificación patrimonial para emprendedores", "category": "educación", "format": "carousel"},
            {"topic": "Claves del IBEX 35 esta semana", "category": "mercados", "format": "reel"},
            {"topic": "Día a día de un asesor financiero", "category": "behind_scenes", "format": "stories"},
            {"topic": "Errores comunes al invertir", "category": "educación", "format": "carousel"},
            {"topic": "Novedades fiscales 2026", "category": "educación", "format": "post"},
            {"topic": "Cómo diversificar tu cartera en 2026", "category": "educación", "format": "carousel"},
            {"topic": "¿Qué hace un private banker?", "category": "behind_scenes", "format": "reel"},
            {"topic": "Mitos y verdades sobre la bolsa", "category": "educación", "format": "carousel"},
            {"topic": "Finanzas para autónomos", "category": "educación", "format": "post"},
            {"topic": "El poder del interés compuesto", "category": "educación", "format": "reel"},
            {"topic": "Planificación fiscal antes de fin de año", "category": "educación", "format": "carousel"},
            {"topic": "Cómo afecta la inflación a tu patrimonio", "category": "educación", "format": "post"},
        ]

        noticias = self._get_noticias_relevantes(topic or "finanzas mercados")
        ideas_noticias = []
        for noticia in noticias:
            titulo = noticia.get("title", "")
            if titulo:
                ideas_noticias.append({
                    "topic": f"Análisis: {titulo[:60]}",
                    "category": "actualidad",
                    "format": "carousel",
                    "source": "noticia",
                })

        todas = ideas_noticias + ideas_base
        if ideas_noticias:
            logger.info(f"{len(ideas_noticias)} ideas desde noticias")
        return todas[:n]

    def create_caption(self, topic: str, tone: str = "profesional") -> str:
        fallback_hashtags = [
            "#asesorfinanciero", "#planificacionpatrimonial", "#inversionesinteligentes",
            "#bancaprivada", "#educacionfinanciera", "#ahorroeinversion",
            "#emprendedores", "#patrimonio", "#mercadofinanciero",
        ]
        fallback = (
            f"¿Sabías que...? {topic}\n\n"
            f"En un entorno donde los tipos de interés y la inflación marcan el ritmo, "
            f"tener una estrategia clara marca la diferencia.\n\n"
            f"En Alexandre trabajamos para ayudarte a tomar las mejores decisiones "
            f"financieras, adaptadas a tu perfil y objetivos.\n\n"
            f"¿Hablamos?\n\n"
            + " ".join(fallback_hashtags[:6])
        )
        try:
            # Enriquecer con datos de mercado si están disponibles
            market_context = ""
            noticias = self._get_noticias_relevantes(topic)
            if noticias:
                titulos = "; ".join(n.get("title", "") for n in noticias[:2])
                market_context = f"\nContexto de mercado actual: {titulos}"

            tone_instructions = {
                "profesional": "tono profesional y de autoridad financiera",
                "cercano": "tono cálido, cercano y accesible para el público general",
                "educativo": "tono educativo, con una pregunta inicial que genera curiosidad",
                "urgencia": "tono que transmite oportunidad y cierta urgencia sin ser alarmista",
            }.get(tone, "tono profesional y de autoridad financiera")

            prompt = f"""Eres el asesor financiero Alexandre, basado en Tarragona (España).
Creas contenido para Instagram dirigido a empresarios, autónomos y profesionales con patrimonio en España.

Escribe un caption de Instagram sobre: {topic}
Tono: {tone_instructions}{market_context}

Instrucciones:
- Máximo 2200 caracteres en total
- Empieza con un gancho potente (pregunta, dato impactante o afirmación controversial)
- 2-3 párrafos cortos con valor real
- Cierra con CTA claro (¿Hablamos? / Escríbeme / Link en bio)
- Incluye 6-8 hashtags relevantes del nicho financiero español al final
- Hashtags obligatorios: #asesorfinanciero #planificacionpatrimonial #tarragona
- Usa emojis con moderación (máx 3-4 en todo el texto)
- El texto debe sonar auténtico, no corporativo

Devuelve SOLO el caption listo para publicar, sin explicaciones adicionales."""

            caption = self.router.call(
                prompt,
                task_description=f"crear caption Instagram financiero sobre {topic[:50]}",
                max_tokens=800,
            )
            # Validar longitud máxima Instagram
            if caption and len(caption.strip()) > 50:
                return caption.strip()[:2200]
            return fallback
        except Exception as e:
            logger.error(f"IRIS create_caption LLM error: {e} — usando fallback")
            return fallback

    def analyze_instagram_profile(self) -> dict:
        """Analiza el perfil de Instagram. Si hay token usa la API real, si no genera análisis con LLM."""
        token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
        real_data = {}

        if token:
            try:
                media = self.instagram.get_media(limit=20)
                audience = self.instagram.get_audience_insights()
                real_data = {"media_count": len(media), "audience": audience, "recent_posts": media[:5]}
                logger.info("IRIS: Analizando perfil con datos reales de Instagram API")
            except Exception as e:
                logger.warning(f"IRIS: Error leyendo API Instagram: {e} — usando análisis LLM")

        try:
            if real_data:
                data_context = f"Datos reales del perfil: {json.dumps(real_data, default=str)[:800]}"
            else:
                data_context = (
                    "Perfil sin datos API todavía. Perfil conocido: asesor financiero independiente llamado Alexandre, "
                    "ubicado en Tarragona, España. Nicho: planificación patrimonial, inversiones, banca privada. "
                    "Audiencia objetivo: empresarios, autónomos y profesionales con patrimonio en España. "
                    "Fase actual: cuenta nueva o con 0-500 seguidores, publicando contenido educativo y de mercado."
                )

            prompt = f"""Eres un experto en marketing digital para el sector financiero en España, especializado en Instagram.

{data_context}

Genera un análisis estratégico completo del perfil de Instagram para este asesor financiero. El análisis debe incluir:

1. PUNTOS FUERTES (3 puntos): qué tiene a favor este nicho y perfil para crecer en Instagram
2. PUNTOS DÉBILES / RIESGOS (3 puntos): obstáculos típicos del sector financiero en redes
3. 5 RECOMENDACIONES CONCRETAS DE CRECIMIENTO: acciones específicas y medibles para los próximos 30 días
4. MEJORES HORAS PARA PUBLICAR: basado en audiencia financiera española (con horarios exactos y días)
5. TIPOS DE CONTENIDO QUE MEJOR FUNCIONAN: en el nicho financiero español en Instagram (con ejemplos)

Sé específico, práctico y directo. Usa datos del sector si los conoces.
Devuelve el análisis en formato estructurado con los 5 apartados claramente diferenciados."""

            analisis_texto = self.router.call(
                prompt,
                task_description="análisis estratégico perfil Instagram asesor financiero España",
                max_tokens=1200,
            )

            return {
                "fuente": "instagram_api" if real_data else "analisis_llm",
                "fecha": datetime.date.today().isoformat(),
                "analisis": analisis_texto.strip() if analisis_texto else "No se pudo generar el análisis",
                "datos_raw": real_data if real_data else {},
            }
        except Exception as e:
            logger.error(f"IRIS analyze_instagram_profile error: {e}")
            return {
                "fuente": "fallback",
                "fecha": datetime.date.today().isoformat(),
                "analisis": (
                    "Análisis no disponible. Puntos fuertes: nicho financiero con alta capacidad adquisitiva, "
                    "contenido evergreen con alto valor. Recomendaciones: publicar 4-5 veces/semana, "
                    "usar carruseles educativos, historias diarias, reels de análisis de mercado."
                ),
                "datos_raw": {},
            }

    def growth_strategy(self) -> dict:
        """Genera con LLM una estrategia de crecimiento de 30 días para Instagram."""
        try:
            prompt = """Eres un experto en growth marketing para Instagram en el sector financiero español.

El cliente es Alexandre, asesor financiero independiente en Tarragona (España).
Perfil: cuenta nueva/pequeña (0-500 seguidores), nicho planificación patrimonial, audiencia objetivo empresarios y autónomos con patrimonio en España.
Objetivo: conseguir 500+ seguidores orgánicos en 30 días y generar 5-10 leads cualificados.

Diseña una ESTRATEGIA DE CRECIMIENTO DETALLADA para 30 días con:

SEMANA 1 — FUNDAMENTOS (días 1-7):
- Optimización de perfil (bio, foto, highlights)
- Frecuencia y tipos de contenido
- 3 acciones específicas de engagement

SEMANA 2 — ACELERACIÓN (días 8-14):
- Tácticas de colaboración o menciones
- Hashtag strategy específica para finanzas España
- Tipo de contenido viral del nicho

SEMANA 3 — CONVERSIÓN (días 15-21):
- Lead magnets para Instagram
- CTA en contenidos
- Estrategia de Stories para captar leads

SEMANA 4 — CONSOLIDACIÓN (días 22-30):
- Analítica y ajuste
- Primeras colaboraciones
- Plan de sostenibilidad

MÉTRICAS OBJETIVO SEMANALES: seguidores nuevos, engagement rate, DMs recibidos

Sé muy específico con ejemplos de posts, hashtags y horarios. Adapta todo al mercado financiero español."""

            estrategia_texto = self.router.call(
                prompt,
                task_description="estrategia crecimiento 30 días Instagram asesor financiero España",
                max_tokens=1500,
            )

            return {
                "tipo": "estrategia_30_dias",
                "generado": datetime.date.today().isoformat(),
                "objetivo": "500 seguidores + 5-10 leads en 30 días",
                "estrategia": estrategia_texto.strip() if estrategia_texto else "No disponible",
            }
        except Exception as e:
            logger.error(f"IRIS growth_strategy error: {e}")
            return self.estrategia_crecimiento()

    def schedule_post(self, caption: str, image_prompt: str, publish_at: str) -> dict:
        logger.info(f"Programando post para {publish_at}")
        return {"caption": caption, "image_prompt": image_prompt,
                "scheduled_at": publish_at, "status": "scheduled", "sandbox": self.sandbox_mode}

    def analyze_best_times(self) -> dict:
        return {"best_days": ["martes", "jueves", "sábado"],
                "best_hours": ["12:00", "18:00", "20:00"],
                "note": "Basado en métricas del sector financiero"}

    def ab_test(self, caption_a: str, caption_b: str) -> dict:
        return {"test_id": datetime.datetime.now().isoformat(),
                "caption_a": caption_a[:60], "caption_b": caption_b[:60], "status": "registered"}

    def weekly_strategy(self) -> list[dict]:
        days = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]
        plan = []
        for i, day in enumerate(days):
            ideas = self.generate_content_ideas(1)
            plan.append({
                "day": day,
                "content": ideas[0] if ideas else {"topic": "Tema pendiente"},
                "best_time": self.analyze_best_times()["best_hours"][i % 3],
            })
        return plan


if __name__ == "__main__":
    agent = IrisAgent()
    print(agent.report())
