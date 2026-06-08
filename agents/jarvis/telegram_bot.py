#!/usr/bin/env python3
"""
JARVIS Telegram Bot — control remoto desde el móvil
Comandos: /start /status /pause /resume /killswitch /oficina /tareas /help
Cualquier otro mensaje se trata como chat directo con JARVIS.

Ejecutar:  python -m agents.jarvis.telegram_bot
"""
from __future__ import annotations
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from agents.jarvis.agent import JarvisAgent

TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID", "")
API_BASE = f"https://api.telegram.org/bot{TOKEN}"
POLL_TIMEOUT = 30

HELP_TEXT = (
    "🤖 *JARVIS — control remoto*\n\n"
    "/status — estado de JARVIS y de la Oficina\n"
    "/pause [motivo] — pausar la actividad autónoma de JARVIS\n"
    "/resume — reanudar la actividad de JARVIS\n"
    "/killswitch on|off — interruptor de emergencia (detiene todo)\n"
    "/oficina — estado de los 7 agentes de la Oficina\n"
    "/tareas — lista de tareas autónomas pendientes\n"
    "/help — esta ayuda\n\n"
    "Cualquier otro mensaje se trata como una conversación directa con JARVIS."
)


def _send(chat_id: str, text: str):
    if not TOKEN or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN o chat_id ausente — no se envía mensaje")
        return
    try:
        requests.post(f"{API_BASE}/sendMessage",
                      json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                      timeout=15)
    except Exception as e:
        logger.error(f"Error enviando mensaje Telegram: {e}")


def _authorized(chat_id: str) -> bool:
    """Sólo el chat del propietario puede operar el bot, si está configurado."""
    if not CHAT_ID:
        return True
    return str(chat_id) == str(CHAT_ID)


class JarvisTelegramBot:
    def __init__(self):
        if not TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN no configurado — el bot no puede arrancar")
        self.jarvis = JarvisAgent()
        self._offset = None

    def _handle_command(self, chat_id: str, text: str):
        parts = text.strip().split(maxsplit=1)
        cmd = parts[0].lower().lstrip("/").split("@")[0]
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("start", "help"):
            _send(chat_id, HELP_TEXT)

        elif cmd == "status":
            r = self.jarvis.report()
            c = r["control"]
            estado = "⛔ KILLSWITCH" if c.get("killswitch") else ("⏸ PAUSADO" if c.get("paused") else "✅ Activo")
            msg = (f"*JARVIS* — {estado}\n"
                   f"Modo: {'🛡 Sandbox' if r['sandbox'] else '🚀 Producción'}\n"
                   f"Tareas: {r['tasks_pending']} pendientes / {r['tasks_done']} completadas / {r['tasks_total']} total")
            if c.get("pause_reason"):
                msg += f"\nMotivo de pausa: {c['pause_reason']}"
            _send(chat_id, msg)

        elif cmd == "pause":
            self.jarvis.pause(reason=arg or "pausado vía Telegram")
            _send(chat_id, f"⏸ JARVIS pausado.{f' Motivo: {arg}' if arg else ''}")

        elif cmd == "resume":
            self.jarvis.resume()
            _send(chat_id, "▶ JARVIS reanudado — actividad autónoma activa de nuevo.")

        elif cmd == "killswitch":
            on = arg.lower() in ("on", "activar", "1", "true")
            off = arg.lower() in ("off", "desactivar", "0", "false")
            if not (on or off):
                _send(chat_id, "Uso: /killswitch on  |  /killswitch off")
            else:
                self.jarvis.set_killswitch(on)
                _send(chat_id, f"⛔ Kill switch {'ACTIVADO — JARVIS detenido por completo' if on else 'desactivado — JARVIS operativo de nuevo'}.")

        elif cmd == "oficina":
            status = self.jarvis.office_status()
            lines = [f"• {name.upper()}: {'✅ operativo' if v == 'operativo' else '❌ no disponible'}" for name, v in status.items()]
            _send(chat_id, "*Estado de la Oficina:*\n" + "\n".join(lines))

        elif cmd == "tareas":
            tasks = self.jarvis.get_tasks(status="pending")
            if not tasks:
                _send(chat_id, "No hay tareas autónomas pendientes ahora mismo.")
            else:
                lines = [f"• [{t['id']}] {t['description']}" for t in tasks[:10]]
                _send(chat_id, "*Tareas pendientes:*\n" + "\n".join(lines))

        else:
            _send(chat_id, f"No reconozco el comando /{cmd}. Usa /help para ver la lista.")

    def _handle_message(self, message: dict):
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")
        if not text or not chat_id:
            return
        if not _authorized(chat_id):
            logger.warning(f"Mensaje de chat no autorizado: {chat_id}")
            return

        if text.startswith("/"):
            self._handle_command(chat_id, text)
        else:
            result = self.jarvis.chat(text, channel="telegram")
            _send(chat_id, result.get("reply", "..."))

    def _poll_once(self) -> bool:
        params = {"timeout": POLL_TIMEOUT}
        if self._offset is not None:
            params["offset"] = self._offset
        try:
            resp = requests.get(f"{API_BASE}/getUpdates", params=params, timeout=POLL_TIMEOUT + 10)
            data = resp.json()
        except Exception as e:
            logger.error(f"Error consultando Telegram: {e}")
            time.sleep(5)
            return False

        if not data.get("ok"):
            logger.warning(f"Telegram getUpdates no-ok: {data}")
            time.sleep(5)
            return False

        for update in data.get("result", []):
            self._offset = update["update_id"] + 1
            message = update.get("message") or update.get("edited_message")
            if message:
                try:
                    self._handle_message(message)
                except Exception as e:
                    logger.error(f"Error procesando mensaje: {e}")
        return True

    def run_forever(self):
        logger.info("[jarvis-telegram] Bot iniciado — escuchando mensajes")
        while True:
            self._poll_once()


def main():
    bot = JarvisTelegramBot()
    bot.run_forever()


if __name__ == "__main__":
    main()
