#!/bin/bash
# sync.sh — Guarda y sube todo a GitHub en un comando
cd "$(dirname "$0")"
git add .
git commit -m "update: $(date '+%Y-%m-%d %H:%M')" 2>&1 | head -2
git push origin main 2>&1 | tail -2
echo "✅ Sincronizado con GitHub"
