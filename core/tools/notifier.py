"""
Notifier — Sistema de notificaciones al propietario
Telegram (primario) | Email (fallback)
"""
import os
import smtplib
import datetime
from email.mime.text import MIMEText
from pathlib import Path
from loguru import logger

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "")
OWNER_NAME = os.getenv("OWNER_NAME", "Alexandre")


class Notifier:
    def send(self, message: str, priority: str = "normal", agent: str = "sistema"):
        log = logger.bind(agent=agent)
        log.info(f"[{priority.upper()}] {message[:80]}")

        if priority in ("critical", "high"):
            sent = self._telegram(message)
            if not sent and OWNER_EMAIL:
                self._email_alert(f"[{priority.upper()}] {agent}: notificación importante", message)
        elif priority == "normal":
            if TELEGRAM_TOKEN:
                self._telegram(f"[{agent}] {message}")
        else:
            log.debug(f"Notificación low ignorada: {message[:60]}")

    def _telegram(self, message: str) -> bool:
        if not TELEGRAM_TOKEN:
            logger.debug("TELEGRAM_BOT_TOKEN no configurado")
            return False
        try:
            import requests
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
            if not chat_id:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
                resp = requests.get(url, timeout=10)
                data = resp.json()
                if data.get("ok") and data.get("result"):
                    chat_id = data["result"][0]["message"]["chat"]["id"]
                    logger.info(f"Telegram chat ID detectado: {chat_id}")
                else:
                    logger.warning("No se pudo detectar Telegram chat ID")
                    return False
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Telegram enviado a {chat_id}")
                return True
            logger.error(f"Telegram error: {resp.status_code} {resp.text[:100]}")
            return False
        except Exception as e:
            logger.error(f"Telegram exception: {e}")
            return False

    def _email_alert(self, subject: str, body: str) -> bool:
        if not OWNER_EMAIL:
            logger.debug("OWNER_EMAIL no configurado")
            return False
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["To"] = OWNER_EMAIL
            msg["From"] = OWNER_EMAIL
            with smtplib.SMTP("localhost", 25) as server:
                server.sendmail(OWNER_EMAIL, [OWNER_EMAIL], msg.as_string())
            logger.info(f"Email alerta enviado a {OWNER_EMAIL}")
            return True
        except Exception as e:
            logger.error(f"Email alerta falló: {e}")
            return False

    def daily_summary(self, summary_text: str):
        if OWNER_EMAIL:
            self._email_alert(f"Resumen diario — {datetime.date.today().isoformat()}", summary_text)
        if TELEGRAM_TOKEN:
            lines = summary_text.split("\n")[:5]
            self._telegram("📋 Resumen diario:\n" + "\n".join(lines))
