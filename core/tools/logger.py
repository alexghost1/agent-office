"""
Logger — Sistema de logging centralizado para la Oficina de Agentes IA
"""
import os
import sys
import datetime
from pathlib import Path
from loguru import logger

LOGS_DIR = Path(os.getenv("LOGS_DIR", Path(__file__).parent.parent.parent / "data" / "logs"))


def _fmt(record):
    agent = record["extra"].get("agent", "system")
    record["extra"]["agent"] = agent
    color = "<green>" if agent == "system" else "<cyan>"
    fmt = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | " + color + "{extra[agent]: <8}</> | <level>{message}</level>\n"
    if record["exception"]:
        fmt += "{exception}"
    return fmt


def _file_fmt(record):
    agent = record["extra"].get("agent", "system")
    record["extra"]["agent"] = agent
    return "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[agent]: <8} | {message}\n{exception}"


def setup_logger():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"agent_office_{datetime.date.today().isoformat()}.log"

    logger.remove()

    logger.add(
        sys.stderr,
        level="INFO",
        format=_fmt,
        colorize=True,
    )

    logger.add(
        str(log_file),
        level="DEBUG",
        format=_file_fmt,
        rotation="1 day",
        retention="30 days",
        compression="gz",
    )

    logger.debug("Logger configurado correctamente")


def get_logger(agent_name: str = "system"):
    return logger.bind(agent=agent_name)


def log_event(agent: str, event_type: str, data: dict = None):
    log = get_logger(agent)
    msg = f"[{event_type}] {data if data else ''}"
    log.info(msg)
    try:
        from core.memory.chroma_store import ChromaStore
        store = ChromaStore()
        text = f"Evento {event_type} de {agent}: {data}"
        store.store("errors" if "error" in event_type.lower() else "strategies",
                     text, metadata={"agent": agent, "event_type": event_type})
    except Exception:
        pass


setup_logger()
