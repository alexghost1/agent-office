#!/bin/bash
# Health checker — verifica cada 5min que los servicios responden
while true; do
  clear
  echo "=== HEALTH CHECK: $(date '+%H:%M:%S') ==="
  echo ""

  # FastAPI (agentes Python)
  if curl -sf http://127.0.0.1:8080/api/agents > /dev/null 2>&1; then
    echo "✅ FastAPI :8080 — OK"
  else
    echo "❌ FastAPI :8080 — CAÍDO. Reiniciando..."
    cd /Users/usuario/agent-office
    source .venv/bin/activate
    python -m infra.mission_control.app &
    sleep 3
    echo "   → Intentando reinicio..."
  fi

  # Mission Control
  if curl -sf http://127.0.0.1:3333 > /dev/null 2>&1; then
    echo "✅ MC :3333 — OK"
  else
    echo "❌ MC :3333 — CAÍDO. Puede estar compilando aún..."
  fi

  # Probar un agente
  result=$(curl -sf -X POST http://127.0.0.1:8080/api/run -d "agent=atlas&task=status" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null)
  if [ "$result" = "ok" ]; then
    echo "✅ ATLAS responde — OK"
  else
    echo "⚠️  ATLAS: $result"
  fi

  echo ""
  echo "Próximo check en 5 minutos..."
  sleep 300
done
