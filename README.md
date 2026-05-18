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
