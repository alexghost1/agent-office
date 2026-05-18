"""
LLM Router — Enrutador inteligente de modelos de lenguaje
"""
import os
import json
import datetime
from pathlib import Path
from typing import Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-5")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

COST_FILE = Path(os.getenv("LOGS_DIR", Path(__file__).parent.parent.parent / "data" / "logs")) / "api_costs.jsonl"
DAILY_BUDGET = float(os.getenv("AGENT_DAILY_API_BUDGET", "5.00"))


class LLMRouter:
    def _ollama_available(self) -> bool:
        try:
            import requests
            url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            resp = requests.get(f"{url}/api/tags", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def route(self, task: str, complexity: str = "medium") -> str:
        # Si Ollama no está disponible, todo va a Claude
        ollama_ok = self._ollama_available()

        keywords_gemini = ["imagen", "visión", "foto", "gráfico", "análisis visual"]
        keywords_ollama = ["clasif", "resum", "extra", "traduc", "categoriz",
                           "etiquet", "puntu", "list", "etiqueta"]

        task_lower = task.lower()

        if complexity == "high":
            return "claude"

        for kw in keywords_gemini:
            if kw in task_lower:
                return "gemini"

        if ollama_ok:
            for kw in keywords_ollama:
                if kw in task_lower:
                    return "ollama"
            if complexity == "low":
                return "ollama"

        return "claude"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception)),
        reraise=True
    )
    def call(self, prompt: str, task_description: str = "",
             system: str = "", max_tokens: int = 2000) -> str:
        if self._budget_exceeded():
            logger.warning("Presupuesto diario excedido — forzando Ollama")
        model = self.route(task_description or prompt)
        if self._budget_exceeded() and model != "ollama":
            logger.info("Presupuesto >80% — redirigiendo a Ollama")
            model = "ollama"

        logger.info(f"LLM Router → {model} | task={task_description[:60]}")
        result = self._call_model(model, prompt, system, max_tokens)
        return result

    def _budget_exceeded(self) -> bool:
        today = datetime.date.today().isoformat()
        if not COST_FILE.exists():
            return False
        total = 0.0
        with open(COST_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("date") == today:
                        total += entry.get("cost", 0)
                except json.JSONDecodeError:
                    continue
        ratio = total / DAILY_BUDGET if DAILY_BUDGET > 0 else 0
        return ratio >= 0.8

    def _call_model(self, model: str, prompt: str,
                    system: str = "", max_tokens: int = 2000) -> str:
        if model == "ollama":
            return self._call_ollama(prompt, max_tokens)
        elif model == "claude":
            return self._call_claude(prompt, system, max_tokens)
        elif model == "gemini":
            return self._call_gemini(prompt, max_tokens)
        elif model == "openai":
            return self._call_openai(prompt, system, max_tokens)
        logger.warning(f"Modelo desconocido: {model}, usando Ollama")
        return self._call_ollama(prompt, max_tokens)

    def _call_ollama(self, prompt: str, max_tokens: int = 2000) -> str:
        import requests
        url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", OLLAMA_MODEL)
        payload = {"model": model, "prompt": prompt, "stream": False,
                   "options": {"num_predict": max_tokens}}
        resp = requests.post(f"{url}/api/generate", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response", "")
        self.track_cost("ollama", 0, 0)
        return text

    def _call_claude(self, prompt: str, system: str = "",
                     max_tokens: int = 2000) -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY no configurada")
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key)
            params = {"model": CLAUDE_MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
            if system:
                params["system"] = system
            msg = client.messages.create(**params)
            text = msg.content[0].text
            usage = getattr(msg, "usage", None)
            if usage:
                self.track_cost("claude", usage.input_tokens, usage.output_tokens)
            return text
        except Exception as e:
            logger.error(f"Claude API error: {e} — fallback a OpenAI")
            return self._call_openai(prompt, system, max_tokens)

    def _call_openai(self, prompt: str, system: str = "",
                     max_tokens: int = 2000) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY no configurada — fallback a Ollama")
            return self._call_ollama(prompt, max_tokens)
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            resp = client.chat.completions.create(
                model=OPENAI_MODEL, messages=messages, max_tokens=max_tokens)
            text = resp.choices[0].message.content or ""
            if hasattr(resp, "usage") and resp.usage:
                self.track_cost("openai", resp.usage.prompt_tokens, resp.usage.completion_tokens)
            return text
        except Exception as e:
            logger.error(f"OpenAI API error: {e} — fallback a Ollama")
            return self._call_ollama(prompt, max_tokens)

    def _call_gemini(self, prompt: str, max_tokens: int = 2000) -> str:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY no configurada — fallback a Claude")
            return self._call_claude(prompt, "", max_tokens)
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=max_tokens),
            )
            text = resp.text or ""
            usage = getattr(resp, "usage_metadata", None)
            if usage:
                self.track_cost("gemini",
                                getattr(usage, "prompt_token_count", 0) or 0,
                                getattr(usage, "candidates_token_count", 0) or 0)
            return text
        except Exception as e:
            logger.error(f"Gemini API error: {e} — fallback a Claude")
            return self._call_claude(prompt, "", max_tokens)

    def track_cost(self, model: str, input_tokens: int, output_tokens: int):
        rates = {
            "claude": {"input": 3e-6, "output": 15e-6},
            "openai": {"input": 2.5e-6, "output": 10e-6},
            "gemini": {"input": 0.1e-6, "output": 0.4e-6},
            "ollama": {"input": 0, "output": 0},
        }
        rate = rates.get(model, {"input": 0, "output": 0})
        cost = (input_tokens * rate["input"]) + (output_tokens * rate["output"])
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "date": datetime.date.today().isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": round(cost, 8),
        }
        COST_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COST_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
        logger.debug(f"Cost tracked: {model} ${cost:.6f}")

        if cost > 0:
            today_total = 0.0
            today = datetime.date.today().isoformat()
            try:
                with open(COST_FILE) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            e = json.loads(line)
                            if e.get("date") == today:
                                today_total += e.get("cost", 0)
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                pass
            if DAILY_BUDGET > 0 and today_total / DAILY_BUDGET >= 0.8:
                logger.warning(f"Presupuesto diario al {today_total/DAILY_BUDGET*100:.0f}%")

    def daily_cost(self) -> float:
        today = datetime.date.today().isoformat()
        if not COST_FILE.exists():
            return 0.0
        total = 0.0
        with open(COST_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("date") == today:
                        total += entry.get("cost", 0)
                except json.JSONDecodeError:
                    continue
        return round(total, 6)
