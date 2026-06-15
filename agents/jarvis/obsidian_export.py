"""
Exporta el historial de conversaciones a un vault de Obsidian.

Genera notas markdown a partir de:
  - data/jarvis/chat_history.jsonl  (conversaciones con JARVIS: HUD, Telegram, etc.)
  - ~/.claude/projects/**/*.jsonl   (sesiones de Claude Code en este equipo)

Uso:
    python -m agents.jarvis.obsidian_export --vault ~/Documents/JARVIS-Vault
    python -m agents.jarvis.obsidian_export --vault ~/Documents/JARVIS-Vault --solo-jarvis
    python -m agents.jarvis.obsidian_export --vault ~/Documents/JARVIS-Vault --solo-claude

El script es idempotente: cada ejecución regenera las notas a partir de los
logs actuales, así que se puede relanzar periódicamente (cron, launchd, etc.)
para mantener el vault al día.
"""
import argparse
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "jarvis"
CHAT_HISTORY_PATH = DATA_DIR / "chat_history.jsonl"
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _sanitize(name: str) -> str:
    return "".join(c if c.isalnum() or c in " -_." else "_" for c in name).strip("_") or "proyecto"


def export_jarvis_history(vault: Path) -> int:
    """Agrupa data/jarvis/chat_history.jsonl por día en notas markdown."""
    if not CHAT_HISTORY_PATH.exists():
        return 0

    out_dir = vault / "JARVIS" / "Conversaciones"
    out_dir.mkdir(parents=True, exist_ok=True)

    by_day = {}
    for line in CHAT_HISTORY_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        day = entry["ts"][:10]
        by_day.setdefault(day, []).append(entry)

    for day, entries in by_day.items():
        lines = [f"# JARVIS — {day}", "", "tags: #jarvis #conversacion", ""]
        for e in entries:
            who = "**Alexandre**" if e["role"] == "owner" else "**JARVIS**"
            hora = e["ts"][11:16]
            lines.append(f"### {hora} — {who}")
            lines.append(e["content"])
            lines.append("")
        (out_dir / f"{day}.md").write_text("\n".join(lines), encoding="utf-8")

    return len(by_day)


def _extract_text(content) -> str:
    """Extrae solo texto legible (ignora thinking/tool_use/tool_result)."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n".join(p.strip() for p in parts if p.strip())
    return ""


def export_claude_sessions(vault: Path, claude_dir: Path = CLAUDE_PROJECTS_DIR) -> int:
    """Convierte las sesiones JSONL de Claude Code en notas markdown, una por sesión."""
    if not claude_dir.exists():
        return 0

    out_dir = vault / "Claude Code"
    count = 0

    for project_dir in claude_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for session_file in project_dir.glob("*.jsonl"):
            turns = []
            session_date = None
            for line in session_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("isSidechain"):
                    continue
                etype = entry.get("type")
                if etype not in ("user", "assistant"):
                    continue
                text = _extract_text(entry.get("message", {}).get("content"))
                if not text:
                    continue
                ts = entry.get("timestamp")
                if ts and session_date is None:
                    session_date = ts[:10]
                who = "Alexandre" if etype == "user" else "Claude"
                turns.append((who, text))

            if not turns:
                continue

            session_date = session_date or "sin-fecha"
            project_name = _sanitize(project_dir.name.lstrip("-"))
            session_short = session_file.stem[:8]
            note_dir = out_dir / project_name
            note_dir.mkdir(parents=True, exist_ok=True)

            lines = [f"# Claude Code — {project_name} — {session_date}", "", "tags: #claude-code #conversacion", ""]
            for who, text in turns:
                lines.append(f"### {who}")
                lines.append(text)
                lines.append("")
            (note_dir / f"{session_date}-{session_short}.md").write_text("\n".join(lines), encoding="utf-8")
            count += 1

    return count


def main():
    parser = argparse.ArgumentParser(description="Exporta conversaciones a un vault de Obsidian")
    parser.add_argument("--vault", required=True, help="Ruta al vault de Obsidian (se crea si no existe)")
    parser.add_argument("--solo-jarvis", action="store_true", help="Exporta solo el historial de JARVIS")
    parser.add_argument("--solo-claude", action="store_true", help="Exporta solo las sesiones de Claude Code")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser()
    vault.mkdir(parents=True, exist_ok=True)
    (vault / ".obsidian").mkdir(exist_ok=True)

    if not args.solo_claude:
        n = export_jarvis_history(vault)
        print(f"JARVIS: {n} día(s) exportado(s)")
    if not args.solo_jarvis:
        n = export_claude_sessions(vault)
        print(f"Claude Code: {n} sesión(es) exportada(s)")

    print(f"Vault listo en: {vault}")


if __name__ == "__main__":
    main()
