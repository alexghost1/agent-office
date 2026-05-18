"""
HERALD Agent — Gestión de email y comunicaciones
"""
import os
import datetime
import base64
from pathlib import Path
from email.mime.text import MIMEText
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

AGENT_NAME = "herald"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


class GmailTool:
    def __init__(self):
        self.service = None
        self.sandbox = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"

    def _auth(self):
        if self.service:
            return self.service
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            creds = Credentials(
                token=None,
                refresh_token=os.getenv("GMAIL_REFRESH_TOKEN", ""),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GMAIL_CLIENT_ID", ""),
                client_secret=os.getenv("GMAIL_CLIENT_SECRET", ""),
            )
            self.service = build("gmail", "v1", credentials=creds)
            logger.info("GmailTool autenticado")
        except Exception as e:
            logger.warning(f"GmailTool auth falló: {e}")
            self.service = None
        return self.service

    def list_emails(self, max_results: int = 20, query: str = "is:unread") -> list[dict]:
        svc = self._auth()
        if not svc:
            return []
        try:
            resp = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
            messages = []
            for msg in resp.get("messages", []):
                detail = svc.users().messages().get(userId="me", id=msg["id"], format="metadata").execute()
                headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
                messages.append({
                    "id": msg["id"],
                    "from": headers.get("From", ""),
                    "subject": headers.get("Subject", ""),
                    "snippet": detail.get("snippet", ""),
                    "date": headers.get("Date", ""),
                })
            return messages
        except Exception as e:
            logger.error(f"Gmail list error: {e}")
            return []

    def get_email(self, email_id: str) -> dict:
        svc = self._auth()
        if not svc:
            return {}
        try:
            detail = svc.users().messages().get(userId="me", id=email_id, format="full").execute()
            headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            body = ""
            parts = detail.get("payload", {}).get("parts", [])
            if parts:
                for p in parts:
                    if p.get("mimeType") == "text/plain" and p.get("body", {}).get("data"):
                        body = base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="ignore")
                        break
            elif detail.get("payload", {}).get("body", {}).get("data"):
                body = base64.urlsafe_b64decode(detail["payload"]["body"]["data"]).decode("utf-8", errors="ignore")
            return {
                "id": email_id,
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "body": body,
                "date": headers.get("Date", ""),
            }
        except Exception as e:
            logger.error(f"Gmail get error: {e}")
            return {}

    def send_email(self, to: str, subject: str, body: str, draft: bool = True) -> dict:
        if self.sandbox:
            logger.info(f"[SANDBOX] Email a {to}: {subject[:60]}")
            return {"success": True, "sandbox": True, "to": to, "subject": subject}
        if draft:
            return self.create_draft(to, subject, body)
        svc = self._auth()
        if not svc:
            return {"success": False, "error": "Gmail no autenticado"}
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["To"] = to
            msg["Subject"] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            svc.users().messages().send(userId="me", body={"raw": raw}).execute()
            logger.info(f"Email enviado a {to}: {subject[:60]}")
            return {"success": True, "to": to, "subject": subject}
        except Exception as e:
            logger.error(f"Gmail send error: {e}")
            return {"success": False, "error": str(e)}

    def create_draft(self, to: str, subject: str, body: str) -> dict:
        svc = self._auth()
        if not svc:
            logger.info(f"[SIN AUTH] Draft: {subject[:60]}")
            return {"success": True, "draft": True, "to": to, "subject": subject}
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["To"] = to
            msg["Subject"] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            svc.users().messages().send(userId="me", body={"raw": raw}).execute()
            logger.info(f"Draft creado: {subject[:60]}")
            return {"success": True, "draft": True, "to": to, "subject": subject}
        except Exception as e:
            logger.error(f"Draft error: {e}")
            return {"success": False, "error": str(e)}


class HeraldAgent:
    def __init__(self):
        self.name = AGENT_NAME
        self.system_prompt = SYSTEM_PROMPT_PATH.read_text()
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.sandbox_mode = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
        self.gmail = GmailTool()
        logger.info(f"{self.name} inicializado | sandbox={self.sandbox_mode}")

    def run(self, task: str, context: dict = None) -> dict:
        logger.info(f"{self.name} ejecutando: {task[:80]}")
        task_lower = task.lower()
        if "clasificar" in task_lower or "classify" in task_lower or "inbox" in task_lower or "leer" in task_lower:
            emails = self.gmail.list_emails(max_results=20)
            classified = self.classify_emails(emails)
            return {"agent": self.name, "status": "ok", "emails": classified}
        if "responder" in task_lower or "reply" in task_lower or "draft" in task_lower:
            email_data = context or {}
            draft = self.draft_reply(email_data)
            return {"agent": self.name, "status": "ok", "draft": draft}
        if "enviar" in task_lower:
            email_data = context or {}
            result = self.gmail.send_email(
                to=email_data.get("to", ""),
                subject=email_data.get("subject", ""),
                body=email_data.get("body", ""),
                draft=email_data.get("draft", True),
            )
            return {"agent": self.name, "status": "ok", "result": result}
        if "detectar" in task_lower or "lead" in task_lower:
            emails = context.get("emails", []) if context else []
            leads = self.detect_leads(emails)
            return {"agent": self.name, "status": "ok", "leads": leads}
        return {"agent": self.name, "task": task, "status": "unknown_command"}

    def report(self) -> dict:
        return {"agent": self.name, "status": "operational", "sandbox": self.sandbox_mode}

    def classify_emails(self, emails: list[dict]) -> list[dict]:
        for email in emails:
            subject = email.get("subject", "")
            sender = email.get("from", "").lower()
            if "urgent" in subject.lower():
                email["priority"] = "P0"
            elif any(w in sender for w in ["cliente", "partner", "@gmail.com"]) and "newsletter" not in subject.lower():
                email["priority"] = "P1"
            elif "newsletter" in subject.lower() or "marketing" in subject.lower():
                email["priority"] = "P3"
            else:
                email["priority"] = "P2"
        return sorted(emails, key=lambda e: e.get("priority", "P3"))

    def draft_reply(self, email: dict) -> str:
        subject = email.get("subject", "")
        sender = email.get("from", "")
        body = email.get("body", email.get("snippet", ""))
        template = (
            f"Estimado/a,\n\n"
            f"Gracias por tu mensaje respecto a: {subject}\n\n"
            f"He revisado tu consulta y te comento:\n\n"
            f"Quedo a tu disposición para cualquier aclaración.\n\n"
            f"Un cordial saludo,\nAlexandre"
        )
        if "reunión" in subject.lower() or "meeting" in subject.lower():
            template = (
                f"Hola,\n\n"
                f"Gracias por tu propuesta. Podemos agendar una reunión. "
                f"¿Qué tal el próximo [día] a las [hora]?\n\n"
                f"Saludos,\nAlexandre"
            )
        return template

    def detect_leads(self, emails: list[dict]) -> list[dict]:
        leads = []
        for email in emails:
            subject = email.get("subject", "").lower()
            snippet = email.get("snippet", "").lower()
            if any(w in subject + " " + snippet for w in ["inversión", "planificación", "patrimonio", "ahorro", "jubilación"]):
                leads.append({
                    "from": email.get("from", ""),
                    "subject": email.get("subject", ""),
                    "source": "email",
                    "score": 70,
                })
        return leads

    def daily_inbox_report(self) -> str:
        emails = self.gmail.list_emails(max_results=50, query="is:unread")
        classified = self.classify_emails(emails)
        p0 = [e for e in classified if e.get("priority") == "P0"]
        p1 = [e for e in classified if e.get("priority") == "P1"]
        p2 = [e for e in classified if e.get("priority") == "P2"]
        p3 = [e for e in classified if e.get("priority") == "P3"]
        return (
            f"=== Bandeja de Entrada ===\n"
            f"P0 (urgente): {len(p0)}\n"
            f"P1 (leads): {len(p1)}\n"
            f"P2 (normal): {len(p2)}\n"
            f"P3 (baja): {len(p3)}\n"
            f"Total no leídos: {len(emails)}"
        )

    def run_inbox_cycle(self):
        emails = self.gmail.list_emails(max_results=20)
        classified = self.classify_emails(emails)
        for email in classified:
            if email.get("priority") in ("P0", "P1"):
                draft = self.draft_reply(email)
                logger.info(f"Draft para {email.get('from', '')}: {draft[:50]}...")
        leads = self.detect_leads(classified)
        if leads:
            logger.info(f"Leads detectados en email: {len(leads)}")


if __name__ == "__main__":
    agent = HeraldAgent()
    print(agent.report())
