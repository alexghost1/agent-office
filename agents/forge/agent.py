"""
FORGE Agent — Código e infraestructura
"""
import os
import datetime
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

AGENT_NAME = "forge"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


class GithubTool:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN", "")
        self.sandbox = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
        self.repo_name = "agent-office"

    def commit_changes(self, files: list[str], message: str, branch: str = "main") -> dict:
        if self.sandbox:
            logger.info(f"[SANDBOX] Commit en {branch}: {message[:60]}")
            return {"success": True, "sandbox": True, "message": message}
        return {"success": False, "error": "GitHub commit no implementado sin sandbox"}

    def create_issue(self, title: str, body: str, labels: list[str] = None) -> dict:
        if self.sandbox:
            logger.info(f"[SANDBOX] Issue: {title[:60]}")
            return {"success": True, "sandbox": True, "title": title}
        try:
            from github import Github
            g = Github(self.token)
            repo = g.get_user().get_repo(self.repo_name)
            issue = repo.create_issue(title=title, body=body, labels=labels or [])
            return {"success": True, "number": issue.number, "url": issue.html_url}
        except Exception as e:
            logger.error(f"GitHub issue error: {e}")
            return {"success": False, "error": str(e)}

    def get_recent_commits(self, limit: int = 10) -> list[dict]:
        if not self.token:
            return []
        try:
            from github import Github
            g = Github(self.token)
            repo = g.get_user().get_repo(self.repo_name)
            commits = repo.get_commits()[:limit]
            return [{"sha": c.sha[:8], "message": c.commit.message.split("\n")[0],
                     "author": str(c.commit.author.name), "date": str(c.commit.author.date)} for c in commits]
        except Exception as e:
            logger.error(f"GitHub commits error: {e}")
            return []


DRAFTS_DIR = Path(__file__).parent.parent.parent / "data" / "drafts"
PENDING_DEPLOYS_FILE = DRAFTS_DIR / "pending_deploys.json"


class ForgeAgent:
    def __init__(self):
        self.name = AGENT_NAME
        self.system_prompt = SYSTEM_PROMPT_PATH.read_text()
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.sandbox_mode = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
        self.github = GithubTool()
        logger.info(f"{self.name} inicializado | sandbox={self.sandbox_mode}")

    def auto_deploy(self, message: str = "", require_approval: bool = True) -> dict:
        """Git add + commit. Push only after approval (saved to pending_deploys.json)."""
        import subprocess, json
        from datetime import datetime
        repo_path = Path(__file__).parent.parent.parent
        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
            commit_msg = message or f"auto: update {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=repo_path, capture_output=True, text=True
            )
            if result.returncode != 0 and "nothing to commit" in result.stdout:
                return {"status": "ok", "message": "Nada que commitear"}

            if require_approval:
                # Save to pending queue — don't push yet
                pending = []
                if PENDING_DEPLOYS_FILE.exists():
                    try:
                        pending = json.loads(PENDING_DEPLOYS_FILE.read_text())
                    except Exception:
                        pending = []
                pending.append({
                    "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
                    "message": commit_msg,
                    "timestamp": datetime.now().isoformat(),
                    "status": "pending_approval"
                })
                PENDING_DEPLOYS_FILE.write_text(json.dumps(pending, indent=2))
                return {
                    "status": "pending_approval",
                    "message": f"Commit listo. Push pendiente de aprobación de Alexandre.",
                    "commit": commit_msg
                }
            else:
                push = subprocess.run(
                    ["git", "push", "origin", "main"],
                    cwd=repo_path, capture_output=True, text=True
                )
                if push.returncode == 0:
                    return {"status": "ok", "message": f"Deploy completado: {commit_msg}"}
                return {"status": "error", "message": f"Push falló: {push.stderr[:200]}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def approve_deploy(self, deploy_id: str = None) -> dict:
        """Push the latest approved commit."""
        import subprocess, json
        repo_path = Path(__file__).parent.parent.parent
        try:
            push = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=repo_path, capture_output=True, text=True
            )
            if push.returncode == 0:
                if PENDING_DEPLOYS_FILE.exists():
                    pending = json.loads(PENDING_DEPLOYS_FILE.read_text())
                    for p in pending:
                        if deploy_id is None or p["id"] == deploy_id:
                            p["status"] = "pushed"
                    PENDING_DEPLOYS_FILE.write_text(json.dumps(pending, indent=2))
                return {"status": "ok", "message": "Push completado"}
            return {"status": "error", "message": push.stderr[:200]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def run(self, task: str, context: dict = None) -> dict:
        logger.info(f"{self.name} ejecutando: {task[:80]}")
        task_lower = task.lower()
        if any(w in task_lower for w in ["aprobar", "approve", "aprueba"]):
            deploy_id = context.get("deploy_id") if context else None
            return {"agent": self.name, **self.approve_deploy(deploy_id)}
        if any(w in task_lower for w in ["deploy", "push", "subir", "github", "commit"]):
            msg = context.get("message", task) if context else task
            return {"agent": self.name, **self.auto_deploy(msg[:80], require_approval=True)}
        if "monitor" in task_lower or "log" in task_lower:
            logs = self.monitor_logs()
            return {"agent": self.name, "status": "ok", "logs": logs}
        if "github" in task_lower or "commit" in task_lower:
            result = self.github.commit_changes(
                files=(context or {}).get("files", []),
                message=(context or {}).get("message", task),
            )
            return {"agent": self.name, "status": "ok", "github": result}
        if "mejora" in task_lower or "improve" in task_lower:
            proposal = self.propose_improvement("general", task)
            return {"agent": self.name, "status": "ok", "proposal": proposal}
        if "ollama" in task_lower or "modelo" in task_lower:
            models = self.check_ollama_models()
            return {"agent": self.name, "status": "ok", "models": models}
        if "sub-agente" in task_lower or "spawn" in task_lower or "crear agente" in task_lower:
            result = self.spawn_sub_agent("nuevo", task, "Instrucciones pendientes")
            return {"agent": self.name, "status": "ok", "sub_agent": result}
        return {"agent": self.name, "task": task, "status": "unknown_command"}

    def report(self) -> dict:
        return {"agent": self.name, "status": "operational", "sandbox": self.sandbox_mode}

    def monitor_logs(self) -> list[dict]:
        logs_dir = Path(os.getenv("LOGS_DIR", Path(__file__).parent.parent.parent / "data" / "logs"))
        issues = []
        if logs_dir.exists():
            log_files = sorted(logs_dir.glob("*.log"), reverse=True)[:3]
            for lf in log_files:
                lines = lf.read_text().split("\n")[-50:]
                errors = [line for line in lines if "ERROR" in line]
                for e in errors[:5]:
                    issues.append({"file": lf.name, "error": e[:120]})
        return issues

    def propose_improvement(self, area: str, description: str) -> dict:
        return {
            "area": area,
            "description": description[:200],
            "impact": "medium",
            "status": "pending_approval",
            "timestamp": datetime.datetime.now().isoformat(),
        }

    def implement_fix(self, issue: str, affected_file: str) -> dict:
        return {"issue": issue, "file": affected_file, "status": "pending_implementation"}

    def update_documentation(self):
        logger.info("Documentación actualizada (simulado)")

    def optimize_llm_routing(self) -> dict:
        return {
            "recommendation": "Usar Ollama para clasificaciones y resúmenes. "
                              "Reservar Claude para razonamiento complejo.",
            "estimated_savings": "60% en costes de API",
        }

    def check_ollama_models(self) -> dict:
        try:
            import requests
            url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            resp = requests.get(f"{url}/api/tags", timeout=10)
            models = resp.json().get("models", [])
            return {"available": [m["name"] for m in models], "count": len(models)}
        except Exception as e:
            logger.warning(f"Ollama no disponible: {e}")
            return {"available": [], "error": str(e)}

    def spawn_sub_agent(self, name: str, role: str, instructions: str) -> str:
        agent_dir = Path(__file__).parent.parent / name
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "__init__.py").write_text(f'"""{name.capitalize()} sub-agent"""\n')
        (agent_dir / "prompts").mkdir(exist_ok=True)
        (agent_dir / "prompts" / "system.md").write_text(f"Eres {name.upper()}, {role}\n\n{instructions}\n")
        (agent_dir / "agent.py").write_text(
            f'"""\n{name.upper()} Agent — sub-agente generado por FORGE\n"""\n'
            f'import os\nfrom pathlib import Path\nfrom dotenv import load_dotenv\n\n'
            f'load_dotenv(Path(__file__).parent.parent.parent / ".env")\n\n'
            f'AGENT_NAME = "{name}"\n'
            f'SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"\n\n\n'
            f'class {name.capitalize()}Agent:\n'
            f'    def __init__(self):\n'
            f'        self.name = AGENT_NAME\n'
            f'        self.system_prompt = SYSTEM_PROMPT_PATH.read_text()\n\n'
            f'    def run(self, task: str, context: dict = None) -> dict:\n'
            f'        return {{"agent": self.name, "task": task, "status": "ok"}}\n\n'
            f'    def report(self) -> dict:\n'
            f'        return {{"agent": self.name, "status": "operational"}}\n'
        )
        logger.info(f"Sub-agente {name} creado en {agent_dir}")
        return str(agent_dir)


if __name__ == "__main__":
    agent = ForgeAgent()
    print(agent.report())
