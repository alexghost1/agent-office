#!/bin/bash
# setup_tablet.sh — Deja un tablet/móvil Android (Termux) listo para trabajar
# en agent-office con Claude Code, conectado al servidor Xeon vía Tailscale.
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/alexghost1/agent-office/main/setup_tablet.sh -o setup_tablet.sh
#   bash setup_tablet.sh
#
# También funciona como one-liner (sin prompt interactivo de API key):
#   curl -fsSL https://raw.githubusercontent.com/alexghost1/agent-office/main/setup_tablet.sh | bash
#
# Variables opcionales — expórtalas antes de ejecutar para no editar el script:
#   XEON_HOST          nombre/IP Tailscale del Xeon            (default: xeon)
#   XEON_USER          usuario SSH en el Xeon                  (default: $(whoami))
#   XEON_SSH_PORT      puerto SSH del Xeon                      (default: 22)
#   REPO_URL           URL del repo a clonar                    (default: agent-office en GitHub)
#   REPO_DIR           carpeta destino                          (default: ~/agent-office)
#   TS_SOCKS_PORT      puerto local del proxy SOCKS5 de Tailscale (default: 1055)
#   TAILSCALE_AUTHKEY  auth key para "tailscale up" sin navegador (opcional)
#   ANTHROPIC_API_KEY  si ya la tienes en el entorno, se reutiliza sin pedirla
set -e

XEON_HOST="${XEON_HOST:-xeon}"
XEON_USER="${XEON_USER:-$(whoami)}"
XEON_SSH_PORT="${XEON_SSH_PORT:-22}"
REPO_URL="${REPO_URL:-https://github.com/alexghost1/agent-office.git}"
REPO_DIR="${REPO_DIR:-$HOME/agent-office}"
TS_SOCKS_PORT="${TS_SOCKS_PORT:-1055}"
TS_STATE_DIR="$HOME/.tailscale"
TS_SOCK="$TS_STATE_DIR/tailscaled.sock"
TS_PID_FILE="$TS_STATE_DIR/tailscaled.pid"

ok()   { echo "✅ $1"; }
warn() { echo "⚠️  $1"; }
step() { echo ""; echo "── $1 ──"; }

step "1/7 Bootstrap de Termux"
pkg update -y
pkg upgrade -y
# tailscale + netcat-openbsd son necesarios para el paso 3/4 (ver docs/tablet-setup.md)
pkg install -y nodejs git python openssh tailscale netcat-openbsd
ok "paquetes base instalados"

step "2/7 Claude Code CLI"
npm install -g @anthropic-ai/claude-code
ok "Claude Code instalado: $(claude --version 2>/dev/null || echo 'revisa el PATH de npm -g')"

step "3/7 Tailscale (modo userspace, sin root)"
mkdir -p "$TS_STATE_DIR"
TS="tailscale --socket=$TS_SOCK"

if [ -f "$TS_PID_FILE" ] && kill -0 "$(cat "$TS_PID_FILE")" 2>/dev/null; then
  ok "tailscaled ya estaba corriendo (pid $(cat "$TS_PID_FILE"))"
else
  nohup tailscaled \
    --tun=userspace-networking \
    --socks5-server="localhost:${TS_SOCKS_PORT}" \
    --outbound-http-proxy-listen="localhost:${TS_SOCKS_PORT}" \
    --state="$TS_STATE_DIR/tailscaled.state" \
    --socket="$TS_SOCK" \
    > "$TS_STATE_DIR/tailscaled.log" 2>&1 &
  echo $! > "$TS_PID_FILE"
  disown
  sleep 2
  ok "tailscaled arrancado en modo userspace-networking (proxy SOCKS5 en :$TS_SOCKS_PORT)"
fi

command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

TS_HOSTNAME="$(getprop ro.product.model 2>/dev/null || echo termux-tablet)"
if [ -n "$TAILSCALE_AUTHKEY" ]; then
  $TS up --authkey="$TAILSCALE_AUTHKEY" --hostname="$TS_HOSTNAME"
  ok "tailscale up con authkey"
else
  echo "Sin TAILSCALE_AUTHKEY: abre la URL de login que aparezca abajo en cualquier navegador."
  $TS up --hostname="$TS_HOSTNAME" || warn "autentícate luego con: $TS up"
fi

step "4/7 Configuración SSH hacia el Xeon"
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

if [ ! -f "$HOME/.ssh/id_ed25519" ]; then
  ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519" -C "termux-tablet"
  ok "clave SSH generada"
else
  ok "clave SSH ya existía, reutilizando"
fi

SSH_CONFIG="$HOME/.ssh/config"
touch "$SSH_CONFIG"
if ! grep -q "^Host xeon$" "$SSH_CONFIG" 2>/dev/null; then
  cat >> "$SSH_CONFIG" <<EOF

Host xeon
    HostName ${XEON_HOST}
    User ${XEON_USER}
    Port ${XEON_SSH_PORT}
    IdentityFile ~/.ssh/id_ed25519
    ProxyCommand nc -X 5 -x 127.0.0.1:${TS_SOCKS_PORT} %h %p
    ServerAliveInterval 30
    ServerAliveCountMax 3
EOF
  ok "host 'xeon' añadido a ~/.ssh/config (vía proxy SOCKS5 de Tailscale)"
else
  ok "host 'xeon' ya estaba configurado en ~/.ssh/config"
fi
chmod 600 "$SSH_CONFIG"

step "5/7 Repo agent-office"
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" pull --ff-only
  ok "repo actualizado en $REPO_DIR"
else
  git clone "$REPO_URL" "$REPO_DIR"
  ok "repo clonado en $REPO_DIR"
fi

step "6/7 ANTHROPIC_API_KEY"
RC_FILE="$HOME/.bashrc"
KEY_TO_SAVE="$ANTHROPIC_API_KEY"
if [ -z "$KEY_TO_SAVE" ] && [ -t 0 ]; then
  read -rsp "Pega tu ANTHROPIC_API_KEY (Enter para omitir): " KEY_TO_SAVE
  echo ""
fi

if [ -n "$KEY_TO_SAVE" ]; then
  touch "$RC_FILE"
  if grep -q "^export ANTHROPIC_API_KEY=" "$RC_FILE" 2>/dev/null; then
    sed -i "s|^export ANTHROPIC_API_KEY=.*|export ANTHROPIC_API_KEY=\"${KEY_TO_SAVE}\"|" "$RC_FILE"
  else
    echo "export ANTHROPIC_API_KEY=\"${KEY_TO_SAVE}\"" >> "$RC_FILE"
  fi
  export ANTHROPIC_API_KEY="$KEY_TO_SAVE"
  ok "ANTHROPIC_API_KEY guardada en $RC_FILE"
else
  warn "ANTHROPIC_API_KEY no configurada — expórtala a mano o haz login interactivo con 'claude'"
fi

step "7/7 Verificación"
command -v node   >/dev/null 2>&1 && ok "Node $(node -v)"            || warn "Node no encontrado"
command -v npm    >/dev/null 2>&1 && ok "npm $(npm -v)"               || warn "npm no encontrado"
command -v claude >/dev/null 2>&1 && ok "Claude Code en PATH"         || warn "Claude Code no encontrado en PATH"
command -v git    >/dev/null 2>&1 && ok "git $(git --version | awk '{print $3}')" || warn "git no encontrado"

if [ -f "$TS_PID_FILE" ] && kill -0 "$(cat "$TS_PID_FILE")" 2>/dev/null; then
  ok "tailscaled corriendo (pid $(cat "$TS_PID_FILE"))"
else
  warn "tailscaled no responde — revisa $TS_STATE_DIR/tailscaled.log"
fi

[ -d "$REPO_DIR/.git" ] && ok "repo en $REPO_DIR" || warn "repo no encontrado en $REPO_DIR"

[ -n "$ANTHROPIC_API_KEY" ] && ok "ANTHROPIC_API_KEY presente en esta sesión" \
  || warn "ANTHROPIC_API_KEY no está en el entorno actual (abre Termux otra vez o 'source ~/.bashrc')"

echo ""
echo "Probando SSH hacia el Xeon (falla si aún no copiaste la clave pública)..."
if ssh -o BatchMode=yes -o ConnectTimeout=8 xeon 'echo conexion-ok' 2>/dev/null | grep -q conexion-ok; then
  ok "SSH al Xeon funciona — usa 'ssh xeon'"
else
  warn "SSH al Xeon no respondió. Autoriza la clave con:"
  echo "   ssh-copy-id -o ProxyCommand=\"nc -X 5 -x 127.0.0.1:${TS_SOCKS_PORT} %h %p\" ${XEON_USER}@${XEON_HOST}"
fi

echo ""
echo "═══════════════════════════════════"
echo " Listo. Próximos pasos:"
echo "  1. cd ${REPO_DIR} && claude"
echo "  2. ssh xeon   (cuando la clave esté autorizada en el Xeon)"
echo "═══════════════════════════════════"
