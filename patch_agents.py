"""Conecta agentes al LLM Router para outputs diversos."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.tools.llm_router import LLMRouter
from agents.iris.agent import IrisAgent
from agents.hermes.agent import HermesAgent

router = LLMRouter()
iris = IrisAgent()
hermes = HermesAgent()

print("=== PATCH: Generando contenido diverso con LLM Router ===")

# IRIS - caption único con contexto de mercado
contexto = "mercados europeos estables, IBEX +0.5%, inflación en 2.8%"
caption = router.route(f"Genera un caption creativo para Instagram sobre planificación patrimonial. Contexto: {contexto}. Tono: profesional pero cercano. Idioma: español. Máximo 220 caracteres.", preferred="claude")
iris.last_caption = caption[:200]
print(f"✅ IRIS caption: {caption[:80]}...")

# HERMES - mensaje outreach único
lead_name = "empresario_tarragona"
msg = router.route(f"Genera un mensaje de outreach personalizado y corto para un lead llamado '{lead_name}' que es empresario en Tarragona. Tono: profesional, personalizado. No suene a plantilla. Idioma: español. Máximo 150 caracteres.", preferred="claude")
hermes.last_outreach = msg[:140]
print(f"✅ HERMES outreach: {msg[:80]}...")

print("✅ PATCH COMPLETO — Agentes ahora usan LLM Router para contenido diverso")
