# CLAUDE CODE — PROMPT MAESTRO
# Oficina de Agentes IA — Implementación Autónoma Completa

---

## TU MISIÓN

Eres el implementador autónomo de la Oficina de Agentes IA.
El bootstrap.py ya ha creado la estructura base. Tu trabajo es completar
**100% de la implementación** de forma autónoma, agente por agente,
sin dejar ningún `pending_implementation` en el código.

**Lee este archivo completo antes de tocar ningún archivo.**

---

## CONTEXTO DEL PROYECTO

**Propietario**: Alexandre — asesor financiero y private banker.
**Objetivo**: Una oficina de 7 agentes IA autónomos que gestionen leads,
Instagram, email, mercados financieros e infraestructura técnica.

**Directorio raíz**: `~/agent-office/`
**Entorno Python**: `~/agent-office/.venv/`
**Config**: `~/agent-office/.env` (ya existe con las API keys)
**Prompts**: `~/agent-office/agents/{nombre}/prompts/system.md` (ya existen)

---

## ORDEN DE IMPLEMENTACIÓN

Implementa en este orden exacto. No saltes pasos.

### FASE 1 — Core compartido (empezar aquí)

#### 1.1 — LLM Router (`core/tools/llm_router.py`)

Crea un router inteligente que decide qué LLM usar según la tarea:

```python
class LLMRouter:
    """
    Reglas de routing:
    - Tarea con "razonamiento", "análisis complejo", "redactar" → Claude claude-sonnet-4-20250514
    - Tarea con "clasificar", "resumir", "extraer" → Ollama (local, gratuito)
    - Tarea con "imagen", "visión" → Gemini
    - Claude no disponible → GPT-4o como fallback
    - Presupuesto diario >80% → forzar Ollama para todo
    """
    def route(self, task: str, complexity: str = "medium") -> str:
        # Retorna: "claude", "ollama", "gemini", "openai"
        pass

    def call(self, prompt: str, task_description: str = "",
             system: str = "", max_tokens: int = 2000) -> str:
        # Llama al LLM correcto y retorna el texto de respuesta
        # Implementar con anthropic, openai, google.generativeai
        # Incluir retry con tenacity (3 intentos, backoff exponencial)
        pass

    def track_cost(self, model: str, input_tokens: int, output_tokens: int):
        # Registrar coste en data/logs/api_costs.jsonl
        # Alertar si supera AGENT_DAILY_API_BUDGET
        pass
```

#### 1.2 — Memoria CORTEX (`core/memory/chroma_store.py`)

```python
class ChromaStore:
    """
    Wrapper sobre ChromaDB con colecciones predefinidas.
    Colecciones: leads, clients, errors, strategies, social_content, market_intel
    """
    def __init__(self):
        # Conectar a ChromaDB (persistente en CHROMA_PERSIST_DIR)
        # Crear las 6 colecciones si no existen
        pass

    def store(self, collection: str, text: str, metadata: dict = None,
              doc_id: str = None) -> str:
        # Generar embedding (sentence-transformers o ollama embeddings)
        # Almacenar con metadata enriquecida (timestamp, agent_source, etc.)
        # Retornar doc_id
        pass

    def search(self, collection: str, query: str,
               n_results: int = 5, min_relevance: float = 0.75) -> list[dict]:
        # Búsqueda semántica
        # Filtrar por relevancia mínima
        # Retornar lista de {text, metadata, relevance_score}
        pass

    def get_agent_context(self, agent_name: str, current_task: str) -> str:
        # Recuperar contexto relevante para un agente dado su tarea actual
        # Busca en errors (para no repetir fallos) y strategies (para reusar éxitos)
        # Retornar string formateado para incluir en el prompt del agente
        pass
```

#### 1.3 — Sistema de logging (`core/tools/logger.py`)

```python
# Configurar loguru para:
# - Logs en consola (nivel INFO)
# - Logs en archivo data/logs/agent_office_{fecha}.log (nivel DEBUG)
# - Rotación diaria, retener 30 días
# - Formato: timestamp | agente | nivel | mensaje
# - Función log_event(agent, event_type, data) que además guarda en ChromaDB
```

#### 1.4 — Notificador (`core/tools/notifier.py`)

```python
class Notifier:
    """Envía alertas al propietario via Telegram (primario) o email (fallback)"""

    def send(self, message: str, priority: str = "normal",
             agent: str = "sistema"):
        # priority: "critical", "high", "normal", "low"
        # critical/high → Telegram inmediato
        # normal → email resumen diario
        # low → log solo
        pass

    def _telegram(self, message: str) -> bool:
        # Usar TELEGRAM_BOT_TOKEN si disponible
        # requests.post a api.telegram.org
        pass

    def _email_alert(self, subject: str, body: str) -> bool:
        # Usar Gmail API (HERALD) como fallback
        pass
```

---

### FASE 2 — Agente CORTEX (memoria)

Archivo: `agents/cortex/agent.py`

Implementar el CortexAgent completo:

```python
class CortexAgent:
    def store_event(self, agent: str, event_type: str, data: dict):
        """Almacena cualquier evento en ChromaDB con metadata completa."""

    def get_context(self, agent: str, task: str) -> str:
        """Recupera contexto relevante para que un agente no repita errores."""

    def detect_patterns(self) -> list[dict]:
        """Analiza logs recientes y detecta patrones de error o éxito."""

    def daily_report(self) -> str:
        """Genera resumen de actividad de las últimas 24h para NEXUS."""

    def store_lead(self, lead_data: dict) -> str:
        """Almacena un lead cualificado con todos sus datos."""

    def search_leads(self, query: str, min_score: int = 65) -> list[dict]:
        """Busca leads por criterios semánticos."""
```

---

### FASE 3 — Agente NEXUS (orquestador)

Archivo: `agents/nexus/agent.py`

```python
class NexusAgent:
    def __init__(self):
        # Cargar todos los demás agentes
        # Inicializar scheduler (APScheduler)
        # Configurar ciclos de trabajo

    def orchestrate(self, task: str, priority: int = 5) -> dict:
        """Decide qué agente ejecuta la tarea y la delega."""

    def hourly_cycle(self):
        """Ejecutar cada hora: revisar estado de agentes, rebalancear tareas."""

    def daily_briefing(self) -> str:
        """Generar resumen ejecutivo diario para el propietario."""

    def weekly_improvements(self) -> list[str]:
        """Proponer 3 mejoras concretas basadas en datos de la semana."""

    def handle_agent_failure(self, agent: str, task: str, error: str):
        """Manejar fallo de un agente: reintentar, escalar o reasignar."""

    def start(self):
        """Iniciar el scheduler y el loop principal de la oficina."""
```

Configurar APScheduler:
- Cada hora: `hourly_cycle()`
- 07:00 diario: pedir a ATLAS briefing de mercados
- 09:00 diario: pedir a IRIS publicar post del día
- 18:00 diario: generar `daily_briefing()` y enviarlo al propietario
- Viernes 16:00: `weekly_improvements()`

---

### FASE 4 — Agente HERALD (email)

Archivo: `agents/herald/agent.py`
Tool: `agents/herald/tools/gmail_tool.py`

Implementar la integración con Gmail API:

```python
class GmailTool(BaseTool):
    def __init__(self):
        # OAuth2 con google-auth usando GMAIL_CLIENT_ID, SECRET, REFRESH_TOKEN
        # Construir servicio con google-api-python-client

    def list_emails(self, max_results: int = 20,
                    query: str = "is:unread") -> list[dict]:
        # Retornar lista de emails con: id, from, subject, snippet, date

    def get_email(self, email_id: str) -> dict:
        # Retornar email completo con body decodificado (base64)

    def send_email(self, to: str, subject: str,
                   body: str, draft: bool = True) -> dict:
        # Si draft=True → crear borrador (NUNCA enviar sin confirmación en sandbox)
        # Si draft=False y SANDBOX_MODE=False → enviar directamente

    def create_draft(self, to: str, subject: str, body: str) -> dict:
        # Crear borrador en Gmail

class HeraldAgent:
    def classify_emails(self, emails: list[dict]) -> list[dict]:
        """Clasificar emails por prioridad P0-P3 usando LLM."""

    def draft_reply(self, email: dict) -> str:
        """Generar borrador de respuesta en el tono del propietario."""

    def detect_leads(self, emails: list[dict]) -> list[dict]:
        """Detectar emails que pueden ser oportunidades de negocio."""

    def daily_inbox_report(self) -> str:
        """Resumen de bandeja de entrada para el propietario."""

    def run_inbox_cycle(self):
        """Ciclo completo: leer → clasificar → borradores → reportar."""
```

---

### FASE 5 — Agente IRIS (Instagram)

Archivo: `agents/iris/agent.py`
Tool: `agents/iris/tools/instagram_tool.py`

```python
class InstagramTool(BaseTool):
    BASE_URL = "https://graph.facebook.com/v19.0"

    def get_media(self, limit: int = 20) -> list[dict]:
        """Obtener posts recientes con métricas de engagement."""

    def get_insights(self, media_id: str) -> dict:
        """Obtener métricas detalladas de un post (reach, likes, comments, saves)."""

    def create_post(self, image_url: str, caption: str,
                    scheduled_time: str = None) -> dict:
        """Crear post. En sandbox: solo simular y loggear."""

    def get_audience_insights(self) -> dict:
        """Datos de audiencia: horarios activos, demografía, intereses."""

    def send_dm(self, user_id: str, message: str) -> dict:
        """Enviar DM. En sandbox: solo loggear, nunca enviar."""

class IrisAgent:
    def generate_content_ideas(self, n: int = 5) -> list[dict]:
        """Generar ideas de contenido basadas en tendencias actuales y ATLAS."""

    def create_caption(self, topic: str, tone: str = "profesional") -> str:
        """Generar caption optimizado con hashtags."""

    def schedule_post(self, caption: str, image_prompt: str,
                      publish_at: str) -> dict:
        """Programar un post completo."""

    def analyze_best_times(self) -> dict:
        """Analizar cuándo está más activa la audiencia."""

    def ab_test(self, caption_a: str, caption_b: str) -> dict:
        """Registrar un A/B test y hacer seguimiento de resultados."""

    def weekly_strategy(self) -> list[dict]:
        """Planificar contenido de la próxima semana."""
```

---

### FASE 6 — Agente HERMES (leads)

Archivo: `agents/hermes/agent.py`
Tool: `agents/hermes/tools/lead_extractor.py`

```python
class LeadExtractor(BaseTool):
    def search_instagram_leads(self, hashtags: list[str],
                                min_followers: int = 5000) -> list[dict]:
        """
        Buscar leads en Instagram por hashtags relevantes.
        Hashtags base: #asesorifinanciera #planificacionpatrimonial
        #inversiónespana #libertadfinanciera #emprendedores
        Retornar: [{username, followers, bio, engagement_rate, score}]
        """

    def score_lead(self, lead_data: dict) -> int:
        """
        Puntuar lead 0-100 basándose en:
        - Seguidores: 5k-50k = +20, 50k+ = +30
        - Bio menciona empresa/negocio = +20
        - Engagement >3% = +15
        - Ubicación España/LATAM = +10
        - Posts sobre dinero/inversión = +15
        - Ya contactado antes = -50
        """

    def generate_outreach_message(self, lead: dict,
                                   step: int = 1) -> str:
        """
        Generar mensaje de outreach personalizado.
        step 1: Primer contacto — presentación de valor, sin vender
        step 2: Seguimiento — contenido relevante
        step 3: Propuesta — llamada o reunión
        """

class HermesAgent:
    def daily_lead_hunt(self, target: int = 10) -> list[dict]:
        """Encontrar N leads cualificados nuevos."""

    def run_outreach_sequence(self):
        """Ejecutar secuencia de mensajes para leads pendientes."""

    def qualify_inbound(self, contact_data: dict) -> dict:
        """Cualificar un lead que llega por email o DM."""

    def update_crm(self, lead_id: str, event: str, notes: str):
        """Actualizar estado del lead en ChromaDB (CORTEX)."""

    def weekly_pipeline_report(self) -> dict:
        """Reporte: leads nuevos, contactados, respuestas, reuniones."""
```

---

### FASE 7 — Agente ATLAS (mercados)

Archivo: `agents/atlas/agent.py`
Tool: `agents/atlas/tools/market_tool.py`

```python
class MarketTool(BaseTool):
    def get_market_summary(self) -> dict:
        """
        Datos de mercado usando yfinance o Yahoo Finance API:
        - IBEX 35, S&P 500, Nasdaq, Eurostoxx 50
        - EUR/USD, EUR/GBP
        - Oro, Petróleo
        - Tipos BCE y Fed
        Retornar variaciones diarias y semanales.
        """

    def get_financial_news(self, topics: list[str] = None,
                            max_items: int = 10) -> list[dict]:
        """
        Noticias financieras relevantes usando NewsAPI o RSS feeds:
        - Expansión, El Economista, Financial Times
        - Filtrar por relevancia para clientes españoles/latinoamericanos
        """

    def analyze_document(self, pdf_path: str) -> dict:
        """Analizar informe financiero PDF y extraer puntos clave."""

class AtlasAgent:
    def morning_briefing(self) -> str:
        """Briefing matutino completo: mercados + noticias + implicaciones."""

    def market_alert(self, threshold: float = 2.0) -> list[dict]:
        """Detectar movimientos de mercado >{threshold}% y alertar."""

    def content_ideas_for_iris(self) -> list[dict]:
        """3 ideas de contenido financiero basadas en noticias actuales."""

    def client_impact_analysis(self, event: str) -> str:
        """Analizar cómo afecta un evento a los clientes del propietario."""

    def weekly_market_report(self) -> str:
        """Informe semanal de mercados en formato para compartir."""
```

---

### FASE 8 — Agente FORGE (infraestructura)

Archivo: `agents/forge/agent.py`
Tool: `agents/forge/tools/github_tool.py`

```python
class GithubTool(BaseTool):
    def __init__(self):
        # PyGithub con GITHUB_TOKEN
        # Repositorio: agent-office (crear si no existe)

    def commit_changes(self, files: list[str],
                       message: str, branch: str = "main") -> dict:
        """Hacer commit de archivos modificados."""

    def create_issue(self, title: str, body: str,
                     labels: list[str] = None) -> dict:
        """Crear issue para trackear bugs o mejoras."""

    def get_recent_commits(self, limit: int = 10) -> list[dict]:
        """Ver historial reciente de cambios."""

class ForgeAgent:
    def monitor_logs(self) -> list[dict]:
        """Analizar logs de las últimas 24h buscando errores recurrentes."""

    def propose_improvement(self, area: str,
                             description: str) -> dict:
        """Proponer mejora a NEXUS con estimación de impacto."""

    def implement_fix(self, issue: str,
                      affected_file: str) -> dict:
        """Implementar corrección de bug (requiere aprobación NEXUS)."""

    def update_documentation(self):
        """Actualizar README y docs técnicos con cambios recientes."""

    def optimize_llm_routing(self) -> dict:
        """Analizar costes y proponer optimizaciones de routing de LLMs."""

    def check_ollama_models(self) -> dict:
        """Verificar qué modelos están disponibles y su estado."""

    def spawn_sub_agent(self, name: str,
                         role: str, instructions: str) -> str:
        """Crear un nuevo agente especializado (genera el código base)."""
```

---

### FASE 9 — Integración y scheduler global

Archivo: `main.py` (reescribir completo)

```python
# El main.py final debe:
# 1. Inicializar todos los agentes en orden (CORTEX primero, NEXUS último)
# 2. Verificar conectividad de todas las APIs
# 3. Iniciar el scheduler de NEXUS
# 4. Mostrar dashboard de estado en terminal (usando rich)
# 5. Enviar notificación al propietario: "Oficina iniciada correctamente"
# 6. Mantener el proceso vivo con loop principal
# 7. Manejar Ctrl+C con graceful shutdown

# Dashboard en terminal debe mostrar:
# - Estado de cada agente (verde/rojo)
# - Último ciclo ejecutado
# - Coste de API del día
# - Próxima tarea programada
```

---

### FASE 10 — Tests básicos

Crear `tests/test_core.py`:

```python
# Tests que verifican:
# 1. Config carga correctamente desde .env
# 2. ChromaDB se puede conectar y almacenar
# 3. LLM Router puede llamar a Ollama local
# 4. Cada agente se puede inicializar sin errores
# 5. Gmail Tool puede conectarse (sin enviar)
# 6. Instagram Tool puede autenticarse (sin publicar)
# Usar pytest. Fixtures con datos de ejemplo.
```

---

## REGLAS QUE DEBES SEGUIR

### Seguridad (NO negociable)
- `SANDBOX_MODE=true` → NUNCA enviar emails, DMs ni publicar en Instagram
- En sandbox, loggear la acción pero no ejecutarla
- Nunca leer el .env en código — usar `os.getenv()` siempre
- Nunca hardcodear API keys en ningún archivo
- Cada acción destructiva (enviar, publicar, commit) → verificar sandbox primero

### Calidad de código
- Type hints en todas las funciones
- Docstrings en todas las clases y métodos públicos
- Manejo de errores con try/except en todas las llamadas externas
- Logging con loguru en cada operación importante
- Retries con tenacity para llamadas a APIs externas

### Estructura de retorno estándar
Todas las funciones de tools retornan:
```python
{
    "success": bool,
    "result": any,      # datos si success=True
    "error": str,       # mensaje si success=False
    "agent": str,       # qué agente ejecutó
    "timestamp": str,   # ISO format
    "sandbox": bool     # si fue simulado o real
}
```

### Costes
- Preferir Ollama para tareas repetitivas
- Solo usar Claude API para: razonamiento complejo, redacción importante, decisiones críticas
- Siempre llamar `llm_router.track_cost()` después de cada llamada de API

---

## CÓMO PROCEDER

1. Lee todos los archivos existentes primero (`ls -R ~/agent-office/`)
2. Lee el `.env` para conocer las keys disponibles
3. Lee cada `agents/{nombre}/prompts/system.md`
4. Implementa en el orden de las fases (1→10)
5. Después de cada fase, ejecuta `python main.py` para verificar que no hay errores
6. Si algo falla, corrígelo antes de avanzar a la siguiente fase
7. Al finalizar, ejecuta `python tests/test_core.py` y asegúrate de que todo pasa

**Empieza ahora por la Fase 1.1 — LLM Router.**

---

## PREGUNTA DE VERIFICACIÓN FINAL

Cuando termines, ejecuta este comando y pega el output:

```bash
cd ~/agent-office && python -c "
from agents.nexus.agent import NexusAgent
from agents.cortex.agent import CortexAgent
n = NexusAgent()
c = CortexAgent()
print('NEXUS:', n.report())
print('CORTEX:', c.report())
print('Todos los agentes operativos.')
"
```

Si sale sin errores, la oficina está lista.

---

*Prompt maestro generado por Claude — Oficina de Agentes IA v1.0*
