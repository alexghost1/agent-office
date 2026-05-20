"""
ATLAS Agent — Research e inteligencia de mercados
"""
import os
import datetime
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent.parent / ".env")

AGENT_NAME = "atlas"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


class MarketTool:
    def __init__(self):
        self.sandbox = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"

    def get_market_summary(self) -> dict:
        try:
            import yfinance as yf
            tickers = {
                "IBEX 35": "^IBEX",
                "S&P 500": "^GSPC",
                "Nasdaq": "^IXIC",
                "Eurostoxx 50": "^STOXX50E",
                "EUR/USD": "EURUSD=X",
                "Oro": "GC=F",
                "Petróleo": "CL=F",
            }
            data = {}
            for name, ticker in tickers.items():
                try:
                    tk = yf.Ticker(ticker)
                    hist = tk.history(period="5d")
                    if not hist.empty:
                        last = hist["Close"].iloc[-1]
                        prev = hist["Close"].iloc[0]
                        change = ((last - prev) / prev) * 100
                        data[name] = {"last": round(last, 2), "change_5d": round(change, 2)}
                except Exception:
                    data[name] = {"error": "no_data"}
            return data
        except ImportError:
            logger.warning("yfinance no instalado — datos simulados")
            return {
                "IBEX 35": {"last": 11500, "change_5d": 1.2},
                "S&P 500": {"last": 5200, "change_5d": 0.8},
                "EUR/USD": {"last": 1.09, "change_5d": -0.3},
            }
        except Exception as e:
            logger.error(f"Market data error: {e}")
            return {}

    def get_financial_news(self, topics: list[str] = None, max_items: int = 20,
                           categories: list[str] = None) -> list[dict]:
        try:
            from core.tools.news_aggregator import NewsAggregator
            agg = NewsAggregator(max_per_source=4)
            if categories:
                articles = agg.fetch_by_category(categories, max_total=max_items)
            else:
                articles = agg.fetch_all(max_total=max_items)
            if articles:
                logger.info(f"NewsAggregator: {len(articles)} noticias reales obtenidas")
                return articles
        except Exception as e:
            logger.warning(f"NewsAggregator falló: {e}")
        return [
            {"title": "El Ibex 35 sube impulsado por la banca", "source": "Expansión",
             "published": datetime.datetime.now().isoformat(), "categories": ["españa", "mercados"]},
            {"title": "El BCE mantiene tipos en 3.25%", "source": "El Economista",
             "published": datetime.datetime.now().isoformat(), "categories": ["españa", "macro"]},
        ]

    def get_crypto_data(self) -> dict:
        try:
            from core.tools.cache import cache
            cached = cache.get(key="crypto_data")
            if cached:
                return cached
        except Exception:
            pass
        result = self._crypto_coingecko()
        if result and any(v.get("usd") for v in result.values() if v):
            try:
                cache.set("crypto_data", result, ttl=120)
            except Exception:
                pass
            return result
        logger.info("CoinGecko sin datos, probando CoinMarketCap")
        result = self._crypto_cmc()
        if result and any(v.get("usd") for v in result.values() if v):
            try:
                cache.set("crypto_data", result, ttl=120)
            except Exception:
                pass
            return result
        logger.warning("Ambas APIs crypto fallaron, datos simulados")
        fallback = {
            "BTC": {"usd": 67500, "change_24h": 2.3, "change_7d": 5.1},
            "ETH": {"usd": 3450, "change_24h": 1.8, "change_7d": -2.4},
            "SOL": {"usd": 148, "change_24h": -0.5, "change_7d": 12.3},
            "total_market_cap": {"usd": 2.45e12, "change_24h": 1.5, "change_7d": 3.8},
        }
        try:
            cache.set("crypto_data", fallback, ttl=60)
        except Exception:
            pass
        return fallback

    def _crypto_coingecko(self) -> dict:
        import requests
        try:
            ids = "bitcoin,ethereum,solana"
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true&include_7d_change=true"
            resp = requests.get(url, timeout=15, headers={"Accept": "application/json"})
            if resp.status_code != 200:
                logger.warning(f"CoinGecko HTTP {resp.status_code}")
                return {}
            data = resp.json()
            g = requests.get("https://api.coingecko.com/api/v3/global", timeout=15).json()
            mcap = g.get("data", {}).get("total_market_cap", {}).get("usd", 0)
            mcap_change_24h = g.get("data", {}).get("market_cap_change_percentage_24h_usd", 0)
            return {
                "BTC": {"usd": data.get("bitcoin", {}).get("usd"),
                        "change_24h": data.get("bitcoin", {}).get("usd_24h_change"),
                        "change_7d": data.get("bitcoin", {}).get("usd_7d_change")},
                "ETH": {"usd": data.get("ethereum", {}).get("usd"),
                        "change_24h": data.get("ethereum", {}).get("usd_24h_change"),
                        "change_7d": data.get("ethereum", {}).get("usd_7d_change")},
                "SOL": {"usd": data.get("solana", {}).get("usd"),
                        "change_24h": data.get("solana", {}).get("usd_24h_change"),
                        "change_7d": data.get("solana", {}).get("usd_7d_change")},
                "total_market_cap": {"usd": mcap, "change_24h": mcap_change_24h},
            }
        except Exception as e:
            logger.error(f"CoinGecko error: {e}")
            return {}

    def _crypto_cmc(self) -> dict:
        api_key = os.getenv("COINMARKETCAP_API_KEY", "")
        if not api_key:
            return {}
        import requests
        try:
            url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
            params = {"symbol": "BTC,ETH,SOL", "convert": "USD"}
            headers = {"X-CMC_PRO_API_KEY": api_key, "Accept": "application/json"}
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code != 200:
                return {}
            data = resp.json().get("data", {})
            g = requests.get("https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest",
                             headers=headers, timeout=15).json()
            mcap = g.get("data", {}).get("quote", {}).get("USD", {}).get("total_market_cap", 0)
            return {
                "BTC": {"usd": data.get("BTC", {}).get("quote", {}).get("USD", {}).get("price"),
                        "change_24h": data.get("BTC", {}).get("quote", {}).get("USD", {}).get("percent_change_24h"),
                        "change_7d": data.get("BTC", {}).get("quote", {}).get("USD", {}).get("percent_change_7d")},
                "ETH": {"usd": data.get("ETH", {}).get("quote", {}).get("USD", {}).get("price"),
                        "change_24h": data.get("ETH", {}).get("quote", {}).get("USD", {}).get("percent_change_24h"),
                        "change_7d": data.get("ETH", {}).get("quote", {}).get("USD", {}).get("percent_change_7d")},
                "SOL": {"usd": data.get("SOL", {}).get("quote", {}).get("USD", {}).get("price"),
                        "change_24h": data.get("SOL", {}).get("quote", {}).get("USD", {}).get("percent_change_24h"),
                        "change_7d": data.get("SOL", {}).get("quote", {}).get("USD", {}).get("percent_change_7d")},
                "total_market_cap": {"usd": mcap},
            }
        except Exception as e:
            logger.error(f"CoinMarketCap error: {e}")
            return {}

    def analyze_document(self, pdf_path: str) -> dict:
        return {"status": "pending", "note": "Análisis de PDF no implementado"}


class AtlasAgent:
    def __init__(self):
        self.name = AGENT_NAME
        self.system_prompt = SYSTEM_PROMPT_PATH.read_text()
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.sandbox_mode = os.getenv("AGENT_SANDBOX_MODE", "true").lower() == "true"
        self.market = MarketTool()
        self.cortex = self._load_cortex()
        self.learner = self._load_learner()
        logger.info(f"{self.name} inicializado | sandbox={self.sandbox_mode}")

    def _load_learner(self):
        try:
            from core.tools.news_aggregator import UserPreferenceLearner
            return UserPreferenceLearner(cortex=self.cortex)
        except Exception as e:
            logger.warning(f"ATLAS no pudo cargar learner: {e}")
            return None

    def _load_cortex(self):
        try:
            from agents.cortex.agent import CortexAgent
            from core.singleton import get_or_create
            return get_or_create("cortex", CortexAgent)
        except Exception as e:
            logger.warning(f"ATLAS no pudo conectar con CORTEX: {e}")
            return None

    def _guardar_en_cortex(self, news: list[dict], market_data: dict = None):
        if not self.cortex:
            return
        try:
            if news:
                self.cortex.store_news(news, source_agent="atlas")
            if market_data:
                self.cortex.store_market_data(market_data, source_agent="atlas")
        except Exception as e:
            logger.warning(f"ATLAS no pudo guardar en CORTEX: {e}")

    def run(self, task: str, context: dict = None) -> dict:
        logger.info(f"{self.name} ejecutando: {task[:80]}")
        task_lower = task.lower()
        has_crypto = any(w in task_lower for w in ["crypto", "bitcoin", "btc", "ethereum", "eth", "solana", "sol"])
        has_market = any(w in task_lower for w in ["mercado", "market", "ibex", "s&p", "nasdaq", "resumen"])
        if has_crypto and has_market:
            summary = self.market.get_market_summary()
            crypto = self.market.get_crypto_data()
            self._guardar_en_cortex([], market_data={"market": summary, "crypto": crypto})
            return {"agent": self.name, "status": "ok", "market": summary, "crypto": crypto}
        if has_crypto:
            crypto = self.market.get_crypto_data()
            self._guardar_en_cortex([], market_data={"crypto": crypto})
            return {"agent": self.name, "status": "ok", "crypto": crypto}
        if "briefing" in task_lower or "matutino" in task_lower:
            briefing = self.morning_briefing()
            return {"agent": self.name, "status": "ok", "briefing": briefing}
        if has_market:
            summary = self.market.get_market_summary()
            self._guardar_en_cortex([], market_data=summary)
            return {"agent": self.name, "status": "ok", "market": summary}
        if "noticia" in task_lower or "news" in task_lower or "fuente" in task_lower:
            # Detectar categoría pedida
            cats = []
            if any(w in task_lower for w in ["crypto", "bitcoin", "blockchain"]): cats.append("crypto")
            if any(w in task_lower for w in ["españa", "ibex", "español"]): cats.append("españa")
            if any(w in task_lower for w in ["macro", "banco central", "bce", "fed"]): cats.append("macro")
            if any(w in task_lower for w in ["usa", "estados unidos", "trump"]): cats.append("usa")
            if any(w in task_lower for w in ["global", "mundial", "geopolítica"]): cats.append("global")

            news = self.market.get_financial_news(categories=cats if cats else None, max_items=25)

            # Personalizar según preferencias aprendidas
            if self.learner and news:
                news = self.learner.rank_articles(news)

            self._guardar_en_cortex(news)
            return {
                "agent": self.name, "status": "ok",
                "noticias": len(news),
                "fuentes_consultadas": list({n.get("source") for n in news}),
                "news": news[:10],
                "guardado_en_cortex": len(news),
            }

        if "perfil" in task_lower or "preferencia" in task_lower or "aprend" in task_lower:
            if self.learner:
                perfil = self.learner.get_profile()
                return {"agent": self.name, "status": "ok", "perfil_usuario": perfil}

        if "fuentes" in task_lower or "qué fuentes" in task_lower:
            from core.tools.news_aggregator import NewsAggregator
            agg = NewsAggregator()
            return {"agent": self.name, "status": "ok", "fuentes_disponibles": agg.available_sources()}

        if "alert" in task_lower:
            alerts = self.market_alert(threshold=2.0)
            return {"agent": self.name, "status": "ok", "alerts": alerts}
        if "idea" in task_lower or "content" in task_lower:
            ideas = self.content_ideas_for_iris()
            return {"agent": self.name, "status": "ok", "ideas": ideas}
        if "informe" in task_lower or "report" in task_lower:
            report = self.weekly_market_report()
            return {"agent": self.name, "status": "ok", "report": report}
        return {"agent": self.name, "task": task, "status": "unknown_command"}

    def report(self) -> dict:
        return {"agent": self.name, "status": "operational", "sandbox": self.sandbox_mode}

    def morning_briefing(self) -> str:
        market = self.market.get_market_summary()
        crypto = self.market.get_crypto_data()
        news = self.market.get_financial_news(max_items=5)
        lines = [f"=== Briefing Matutino — {datetime.date.today().isoformat()} ===\n"]
        lines.append("MERCADOS TRADICIONALES:")
        for name, data in market.items():
            change = data.get("change_5d", 0)
            arrow = "📈" if change and change > 0 else "📉" if change and change < 0 else "➡️"
            lines.append(f"  {arrow} {name}: {data.get('last', 'N/A')} ({change}%)")
        lines.append("\nCRIPTOMONEDAS:")
        for sym in ["BTC", "ETH", "SOL"]:
            c = crypto.get(sym, {})
            price = c.get("usd")
            if price:
                ch24 = c.get("change_24h")
                ch7 = c.get("change_7d")
                ch24_str = f"{ch24:+.2f}%" if ch24 is not None else "N/A"
                ch7_str = f"{ch7:+.2f}%" if ch7 is not None else "N/A"
                arrow24 = "📈" if ch24 and ch24 > 0 else "📉" if ch24 and ch24 < 0 else "➡️"
                price_str = f"${price:,.0f}" if price > 1000 else f"${price:.2f}"
                lines.append(f"  {arrow24} {sym}: {price_str} | 24h: {ch24_str} | 7d: {ch7_str}")
        mcap = crypto.get("total_market_cap", {}).get("usd", 0)
        if mcap:
            lines.append(f"  🌐 Total Market Cap: ${mcap:.2e}")
        lines.append("\nNOTICIAS DESTACADAS:")
        for article in news[:3]:
            lines.append(f"  • {article.get('title', '')}")
        return "\n".join(lines)

    def market_alert(self, threshold: float = 2.0) -> list[dict]:
        market = self.market.get_market_summary()
        crypto = self.market.get_crypto_data()
        alerts = []
        for name, data in market.items():
            change = abs(data.get("change_5d", 0))
            if change > threshold:
                alerts.append({"asset": name, "change_pct": data.get("change_5d"),
                               "message": f"{name} movió {data.get('change_5d')}% en 5 días"})
        for sym in ["BTC", "ETH", "SOL"]:
            c = crypto.get(sym, {})
            ch24 = c.get("change_24h")
            if ch24 is not None and abs(ch24) > threshold:
                alerts.append({"asset": sym, "change_pct": ch24,
                               "message": f"{sym} movió {ch24:+.2f}% en 24h"})
        return alerts

    def content_ideas_for_iris(self) -> list[dict]:
        market = self.market.get_market_summary()
        crypto = self.market.get_crypto_data()
        ideas = []
        for name, data in market.items():
            change = data.get("change_5d", 0)
            if change and abs(change) > 1:
                ideas.append({
                    "topic": f"¿Por qué {name} {'sube' if change > 0 else 'baja'} esta semana?",
                    "reason": f"Movimiento del {change}% detectado",
                    "format": "carousel",
                })
        for sym in ["BTC", "ETH", "SOL"]:
            c = crypto.get(sym, {})
            ch7 = c.get("change_7d")
            if ch7 is not None and abs(ch7) > 3:
                direction = "sube" if ch7 > 0 else "cae"
                ideas.append({
                    "topic": f"{sym} {direction} con fuerza esta semana — claves a seguir",
                    "reason": f"Variación semanal del {ch7:+.2f}%",
                    "format": "reel",
                })
        ideas.append({
            "topic": "Guía básica de planificación patrimonial para 2026",
            "reason": "Contenido educativo evergreen",
            "format": "post",
        })
        return ideas

    def client_impact_analysis(self, event: str) -> str:
        return (
            f"Impacto potencial del evento: {event}\n\n"
            f"Recomendación: Revisar carteras con exposición a los activos afectados. "
            f"Mantener visión a largo plazo."
        )

    def weekly_market_report(self) -> str:
        market = self.market.get_market_summary()
        crypto = self.market.get_crypto_data()
        news = self.market.get_financial_news(max_items=10)
        lines = [f"=== Informe Semanal de Mercados — {datetime.date.today().isoformat()} ===\n"]
        lines.append("MERCADOS TRADICIONALES:")
        for name, data in market.items():
            lines.append(f"  {name}: {data}")
        lines.append("\nCRIPTOMONEDAS:")
        for sym in ["BTC", "ETH", "SOL"]:
            c = crypto.get(sym, {})
            price = c.get("usd")
            if price:
                ch24 = c.get("change_24h")
                ch7 = c.get("change_7d")
                ch24_str = f"{ch24:+.2f}%" if ch24 is not None else "N/A"
                ch7_str = f"{ch7:+.2f}%" if ch7 is not None else "N/A"
                price_str = f"${price:,.0f}" if price > 1000 else f"${price:.2f}"
                lines.append(f"  {sym}: {price_str} | 24h: {ch24_str} | 7d: {ch7_str}")
        mcap = crypto.get("total_market_cap", {}).get("usd", 0)
        if mcap:
            mcap_ch24 = crypto["total_market_cap"].get("change_24h")
            ch_str = f" ({mcap_ch24:+.2f}%)" if mcap_ch24 is not None else ""
            lines.append(f"  🌐 Total Crypto Market Cap: ${mcap:.2e}{ch_str}")
        lines.append(f"\nNOTICIAS DE LA SEMANA ({len(news)}):")
        for a in news[:5]:
            lines.append(f"  • {a.get('title', '')}")
        return "\n".join(lines)


if __name__ == "__main__":
    agent = AtlasAgent()
    print(agent.report())
