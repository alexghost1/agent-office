# Oficina de Agentes IA

Sistema multi-agente autónomo para gestión de leads, Instagram, email y mercados financieros.

## Agentes

| Agente | Rol | Estado |
|--------|-----|--------|
| NEXUS  | CEO Orquestador | ⚡ Core |
| CORTEX | Memoria vectorial | ⚡ Core |
| HERMES | Leads & Outreach | 🔧 En desarrollo |
| IRIS   | Instagram Manager | 🔧 En desarrollo |
| ATLAS  | Research & Markets | 🔧 En desarrollo |
| HERALD | Email & Comms | 🔧 En desarrollo |
| FORGE  | Código & Infra | 🔧 En desarrollo |

## JARVIS — asistente personal

JARVIS es el asistente personal de Alexandre dentro de este dispositivo: tiene su
propio cerebro (memoria, ciclos de pensamiento, tareas autónomas), un puente directo
con los 7 agentes de la Oficina y control remoto vía Telegram.

- **Agente**: `agents/jarvis/agent.py` (`JarvisAgent`) — chat, delegación, memoria, kill switch
- **HUD web**: `http://localhost:8080/jarvis` (parte de Mission Control, ver abajo)
- **PWA de voz**: `docs/index.html` — app instalable (GitHub Pages), habla directo con la API de Claude
- **Telegram**: `python -m agents.jarvis.telegram_bot` — `/status /pause /resume /killswitch /oficina /tareas`
- **Memoria**: `data/jarvis/` — `control.json`, `mind_log.json`, `autonomous_tasks.json`, `chat_history.jsonl`

Variables de entorno relevantes: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OWNER_NAME`.

### Baúl de Obsidian

`agents/jarvis/obsidian_export.py` exporta todas las conversaciones (con JARVIS
y con Claude Code) a notas markdown organizadas por día/sesión, listas para
abrir como vault de Obsidian:

```bash
python -m agents.jarvis.obsidian_export --vault ~/Documents/JARVIS-Vault
```

- `JARVIS/Conversaciones/YYYY-MM-DD.md` — una nota por día con `data/jarvis/chat_history.jsonl`
- `Claude Code/<proyecto>/YYYY-MM-DD-<sesión>.md` — una nota por sesión de `~/.claude/projects/`

Es idempotente — relánzalo cuando quieras para refrescar el vault con las
conversaciones nuevas. Abre la carpeta del vault directamente desde la app de Obsidian.

## Mission Control (HUD web)

```bash
python -m infra.mission_control.app
# → http://localhost:8080            Panel de la Oficina
# → http://localhost:8080/jarvis     HUD de JARVIS (chat + control remoto)
# → http://localhost:8080/sessions   Historial de sesiones
```

## Inicio rápido

```bash
# 1. Activar entorno virtual
source .venv/bin/activate

# 2. Verificar configuración
python -c "from core.config.settings import config; print(config.validate())"

# 3. Arrancar oficina
python main.py
```

## Estructura

```
agent-office/
├── agents/          # 7 agentes especializados
├── core/            # Config, tools, skills compartidos
├── data/            # Leads, logs, vectores
├── infra/           # Docker, Harness, scripts
└── main.py          # Punto de entrada
```

## Variables de entorno

Ver `.env` — generado por bootstrap.py. NUNCA commitear.

## Claude Code

Abre esta carpeta en VSCode con Claude Code activado y usa el archivo
`CLAUDE_CODE_MASTER_PROMPT.md` para que complete la implementación automáticamente.
