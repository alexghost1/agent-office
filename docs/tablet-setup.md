# Claude Code en tablet (Termux)

Guía rápida para dejar Claude Code funcionando en un tablet/móvil Android,
vía [Termux](https://termux.dev/), para poder trabajar en `agent-office`
desde cualquier sitio.

## Pasos manuales

```bash
pkg install nodejs
npm install -g @anthropic-ai/claude-code
```

## Script

`setup_tablet.sh` (en la raíz del repo) automatiza lo anterior — actualiza
los paquetes de Termux, instala Node.js y Git, e instala el CLI de Claude
Code:

```bash
curl -O https://raw.githubusercontent.com/alexghost1/agent-office/main/setup_tablet.sh
bash setup_tablet.sh
```

## Uso

```bash
git clone https://github.com/alexghost1/agent-office.git
cd agent-office
claude
```

Para autenticarte la primera vez, `claude` te pedirá iniciar sesión con tu
cuenta de Anthropic (o una API key vía `ANTHROPIC_API_KEY`).

Esto es independiente de la **JARVIS PWA** (`docs/index.html`), que es la
interfaz de voz instalable para hablar con JARVIS desde el tablet — aquí
lo que se instala es el CLI de desarrollo para trabajar directamente sobre
el código del repo.
