#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 Iniciando Oficina de Agentes..."

# Liberar puertos
kill $(lsof -ti :8080) 2>/dev/null || true
kill $(lsof -ti :3333) 2>/dev/null || true
sleep 1

# 1. FastAPI (nuestros agentes Python)
echo "[1/2] Iniciando FastAPI (agentes Python) en :8080..."
cd "$DIR"
source .venv/bin/activate
python -m infra.mission_control.app &
sleep 3

# 2. Mission Control (OpenClaw UI)
echo "[2/2] Iniciando Mission Control en :3333..."
cd ~/.openclaw/openclaw-mission-control
npx next dev -H 127.0.0.1 -p 3333 &
sleep 8

echo ""
echo "✅ LISTO — Abre http://127.0.0.1:3333 en Safari"
echo "   API agentes: http://127.0.0.1:8080/api/agents"
echo "   Para detener: pkill -f 'infra.mission_control|next dev'"
