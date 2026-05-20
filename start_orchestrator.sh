#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
source .venv/bin/activate
echo "🤖 Iniciando orquestador de la Oficina..."
python -m infra.orchestrator
