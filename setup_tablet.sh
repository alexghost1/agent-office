#!/bin/bash
# setup_tablet.sh — Prepara un tablet/móvil Android (Termux) para usar Claude Code
set -e

echo "📱 Configurando Termux para Claude Code..."

# 1. Paquetes base
pkg update -y
pkg install -y nodejs git

# 2. Claude Code CLI
npm install -g @anthropic-ai/claude-code

echo ""
echo "✅ LISTO — node $(node -v), npm $(npm -v)"
echo "   Claude Code instalado: $(command -v claude || echo 'revisa el PATH de npm -g')"
echo ""
echo "Siguiente paso: clona el repo y ejecuta 'claude' dentro de la carpeta:"
echo "   git clone https://github.com/alexghost1/agent-office.git"
echo "   cd agent-office && claude"
