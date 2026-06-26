# Claude Code en tablet (Termux)

Guía para dejar un tablet/móvil Android listo para trabajar en `agent-office`
con Claude Code, conectado al **Xeon** (servidor de casa) por Tailscale.

## Qué hace `setup_tablet.sh`

1. Bootstrap de Termux: `pkg upgrade` + instala `nodejs`, `git`, `python`, `openssh`
2. Instala el CLI de Claude Code (`npm install -g @anthropic-ai/claude-code`)
3. Instala y arranca Tailscale dentro de Termux, en modo `userspace-networking`
4. Configura `~/.ssh/config` para conectar al Xeon automáticamente vía Tailscale
5. Clona o sincroniza `agent-office`
6. Guarda `ANTHROPIC_API_KEY` en `~/.bashrc`
7. Verifica que todo responde (Node, Claude Code, Tailscale, SSH, repo)

## Antes de ejecutar

Por defecto asume que el Xeon se llama `xeon` en tu tailnet y que el usuario
SSH es el mismo que el de Termux. Si no, exporta antes de lanzar el script:

```bash
export XEON_HOST="100.x.y.z"      # o el nombre Tailscale/MagicDNS real del Xeon
export XEON_USER="alexandre"      # usuario SSH en el Xeon
export TAILSCALE_AUTHKEY="tskey-..."   # opcional, evita el login por navegador
export ANTHROPIC_API_KEY="sk-ant-..."  # opcional, evita que el script la pida
```

## Ejecutar

```bash
curl -fsSL https://raw.githubusercontent.com/alexghost1/agent-office/main/setup_tablet.sh -o setup_tablet.sh
bash setup_tablet.sh
```

También sirve como one-liner (`curl ... | bash`), pero en ese modo no hay
terminal interactiva: si no exportaste `ANTHROPIC_API_KEY` antes, el script
omite el prompt y avisa para configurarla después.

## Por qué Tailscale necesita un proxy SOCKS5

Termux corre sin root, así que no puede crear una interfaz de red real
(`/dev/net/tun`). Por eso `tailscaled` arranca en modo `--tun=userspace-networking`:
solo Termux se une al tailnet, a través de un proxy SOCKS5 local
(`127.0.0.1:1055` por defecto). El `Host xeon` que el script añade a
`~/.ssh/config` usa ese proxy vía `ProxyCommand nc -X 5 -x ...`, así que
`ssh xeon` funciona sin tener que pensar en ello.

> Alternativa más simple si quieres que **todo** el tablet (no solo Termux)
> tenga acceso al tailnet: instala la app oficial de Tailscale desde Play
> Store/F-Droid, inicia sesión ahí, y conéctate al Xeon por su IP/MagicDNS
> directamente — sin proxy, sin pasos 3-4 de este script.

## Primera conexión al Xeon

El script genera `~/.ssh/id_ed25519` si no existe. La primera vez hay que
autorizar esa clave en el Xeon:

```bash
ssh-copy-id -o ProxyCommand="nc -X 5 -x 127.0.0.1:1055 %h %p" alexandre@xeon
```

(o pega el contenido de `~/.ssh/id_ed25519.pub` en `~/.ssh/authorized_keys`
del Xeon a mano).

## Verificación

El propio script termina con un resumen ✅/⚠️ de Node, npm, Claude Code,
git, `tailscaled`, el repo clonado, `ANTHROPIC_API_KEY` y una prueba de
`ssh xeon`. Para repetir solo la comprobación:

```bash
node -v && npm -v && claude --version
tailscale --socket=$HOME/.tailscale/tailscaled.sock status
ssh xeon 'echo ok'
```

## Uso diario

```bash
cd ~/agent-office && claude   # trabajar en el repo con Claude Code
ssh xeon                      # entrar al servidor de casa
```

## Notas de seguridad

- `ANTHROPIC_API_KEY` queda en texto plano en `~/.bashrc` — aceptable en un
  dispositivo personal, pero no lo compartas ni lo subas a ningún repo.
- Termux mata procesos en segundo plano si Android cierra la app; si
  `tailscaled` se cae, vuelve a correr `bash setup_tablet.sh` (es idempotente).
  Instalar `Termux:API` (`pkg install termux-api`) permite usar
  `termux-wake-lock`, que el script ya activa si está disponible.
- Si usas `TAILSCALE_AUTHKEY`, genera una key de un solo uso desde el admin
  console de Tailscale en vez de reutilizar una key de larga duración.

Esto es independiente de la **JARVIS PWA** (`docs/index.html`), que es la
interfaz de voz instalable para hablar con JARVIS desde el tablet — aquí
lo que se instala es el CLI de desarrollo (Claude Code) y el acceso SSH al
Xeon para trabajar directamente sobre el código y la infraestructura.
