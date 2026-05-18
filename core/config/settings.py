"""
Configuración global de la Oficina de Agentes IA
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(os.getenv("PROJECT_ROOT", Path(__file__).parent.parent))

class Config:
    # LLMs
    ANTHROPIC_KEY      = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_KEY         = os.getenv("OPENAI_API_KEY", "")
    GEMINI_KEY         = os.getenv("GEMINI_API_KEY", "")
    OLLAMA_URL         = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL       = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

    # APIs externas
    INSTAGRAM_TOKEN    = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    INSTAGRAM_ID       = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
    GITHUB_TOKEN       = os.getenv("GITHUB_TOKEN", "")
    GMAIL_CLIENT_ID    = os.getenv("GMAIL_CLIENT_ID", "")
    GMAIL_SECRET       = os.getenv("GMAIL_CLIENT_SECRET", "")
    GMAIL_REFRESH      = os.getenv("GMAIL_REFRESH_TOKEN", "")
    OPENCODE_KEY       = os.getenv("OPENCODE_API_KEY", "")

    # Sistema
    SANDBOX_MODE       = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
    MAX_RETRIES        = int(os.getenv("AGENT_MAX_RETRIES", "3"))
    DAILY_BUDGET       = float(os.getenv("AGENT_DAILY_API_BUDGET", "5.00"))
    OWNER_EMAIL        = os.getenv("OWNER_EMAIL", "")
    OWNER_NAME         = os.getenv("OWNER_NAME", "")
    TELEGRAM_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Paths
    CHROMA_DIR         = Path(os.getenv("CHROMA_PERSIST_DIR", ROOT / "data" / "vectors"))
    LOGS_DIR           = Path(os.getenv("LOGS_DIR", ROOT / "data" / "logs"))

    @classmethod
    def validate(cls) -> list[str]:
        """Retorna lista de keys críticas faltantes."""
        missing = []
        critical = ["ANTHROPIC_KEY", "OWNER_EMAIL", "OWNER_NAME"]
        for key in critical:
            if not getattr(cls, key):
                missing.append(key)
        return missing

config = Config()
