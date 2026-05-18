"""
News Aggregator — Oficina de Agentes IA
Multi-source RSS reader con aprendizaje de preferencias del usuario.
"""
import os
import datetime
import hashlib
from loguru import logger

# ── Fuentes RSS por categoría ──────────────────────────────────────────────
RSS_SOURCES = {
    # Economía y mercados globales
    "BBC Business":        "http://feeds.bbci.co.uk/news/business/rss.xml",
    "CNN Business":        "http://rss.cnn.com/rss/money_news_international.rss",
    "Reuters Business":    "https://feeds.reuters.com/reuters/businessNews",
    "The Economist":       "https://www.economist.com/finance-and-economics/rss.xml",
    "Washington Post Biz": "https://feeds.washingtonpost.com/rss/business",
    "Financial Times":     "https://www.ft.com/rss/home/uk",
    "Bloomberg":           "https://feeds.bloomberg.com/markets/news.rss",
    "Investing.com":       "https://www.investing.com/rss/news.rss",
    "MarketWatch":         "https://feeds.marketwatch.com/marketwatch/topstories/",

    # España y LATAM
    "Expansión":           "https://e00-expansion.uecdn.es/rss/portada.xml",
    "El Economista ES":    "https://www.eleconomista.es/rss/rss-seleccion-ee.php",
    "Cinco Días":          "https://cincodias.elpais.com/rss/section/cincodias_portada/",
    "El País Economía":    "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada",

    # Crypto y tecnología financiera
    "CoinDesk":            "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "CryptoSlate":         "https://cryptoslate.com/feed/",
    "The Block":           "https://www.theblock.co/rss.xml",

    # Macro y geopolítica
    "AP Business":         "https://rsshub.app/apnews/topics/business",
    "Al Jazeera Economy":  "https://www.aljazeera.com/xml/rss/all.xml",

    # Añadidas segunda ronda
    "Reuters España":      "https://feeds.reuters.com/reuters/topNews",
    "CNBC":                "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    "CNBC Markets":        "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "Barron's":            "https://feeds.content.dowjones.io/public/rss/mw_bulletins",
    "El Confidencial":     "https://www.elconfidencial.com/rss/mercados.xml",
    "Seeking Alpha":       "https://seekingalpha.com/market_currents.xml",
    "CNBC World Economy":  "https://www.cnbc.com/id/100003241/device/rss/rss.html",
    "El Confidencial Eco": "https://www.elconfidencial.com/rss/economia.xml",
}

# Categorías por fuente para filtrado inteligente
SOURCE_CATEGORIES = {
    "BBC Business": ["macro", "global", "europa"],
    "CNN Business": ["usa", "macro", "mercados"],
    "Reuters Business": ["macro", "mercados", "global"],
    "The Economist": ["macro", "análisis", "global"],
    "Washington Post Biz": ["usa", "política", "macro"],
    "Financial Times": ["mercados", "global", "análisis"],
    "Bloomberg": ["mercados", "macro", "inversión"],
    "Investing.com": ["mercados", "forex", "commodities"],
    "MarketWatch": ["mercados", "usa", "inversión"],
    "Expansión": ["españa", "empresas", "mercados"],
    "El Economista ES": ["españa", "macro", "empresas"],
    "Cinco Días": ["españa", "empresas", "mercados"],
    "El País Economía": ["españa", "macro", "social"],
    "CoinDesk": ["crypto", "bitcoin", "blockchain"],
    "CryptoSlate": ["crypto", "defi", "nfts"],
    "The Block": ["crypto", "institucional", "regulación"],
    "AP Business":         ["global", "macro", "empresas"],
    "Al Jazeera Economy":  ["global", "geopolítica", "macro"],
    "Reuters España":      ["españa", "macro", "global"],
    "CNBC":                ["usa", "mercados", "macro"],
    "CNBC Markets":        ["mercados", "usa", "inversión"],
    "CNBC World Economy":  ["global", "macro", "usa"],
    "Barron's":            ["inversión", "mercados", "análisis"],
    "El Confidencial":     ["españa", "mercados", "empresas"],
    "El Confidencial Eco": ["españa", "macro", "empresas"],
    "Seeking Alpha":       ["inversión", "análisis", "acciones"],
}


class NewsAggregator:
    def __init__(self, max_per_source: int = 5, timeout: int = 10):
        self.max_per_source = max_per_source
        self.timeout = timeout

    def fetch_source(self, name: str, url: str) -> list[dict]:
        try:
            import feedparser
            feed = feedparser.parse(url)
            articles = []
            for entry in feed.entries[:self.max_per_source]:
                pub = entry.get("published", entry.get("updated", ""))
                articles.append({
                    "title":     entry.get("title", "").strip(),
                    "summary":   entry.get("summary", entry.get("description", ""))[:300],
                    "url":       entry.get("link", ""),
                    "published": pub[:25] if pub else datetime.datetime.now().isoformat(),
                    "source":    name,
                    "categories": SOURCE_CATEGORIES.get(name, ["general"]),
                    "id":        hashlib.md5(entry.get("link", name).encode()).hexdigest()[:12],
                })
            return articles
        except Exception as e:
            logger.debug(f"RSS error [{name}]: {e}")
            return []

    def fetch_all(self, sources: list[str] = None, max_total: int = 60) -> list[dict]:
        """Obtiene noticias de todas las fuentes (o las seleccionadas)."""
        import concurrent.futures
        target = {k: v for k, v in RSS_SOURCES.items()
                  if sources is None or k in sources}

        all_articles = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(self.fetch_source, name, url): name
                       for name, url in target.items()}
            for future in concurrent.futures.as_completed(futures, timeout=30):
                try:
                    articles = future.result()
                    all_articles.extend(articles)
                except Exception:
                    pass

        # Ordenar por fecha más reciente
        all_articles.sort(key=lambda x: x.get("published", ""), reverse=True)
        logger.info(f"NewsAggregator: {len(all_articles)} artículos de {len(target)} fuentes")
        return all_articles[:max_total]

    def fetch_by_category(self, categories: list[str], max_total: int = 30) -> list[dict]:
        """Obtiene noticias filtradas por categoría (crypto, españa, macro, etc.)."""
        sources = [name for name, cats in SOURCE_CATEGORIES.items()
                   if any(c in cats for c in categories)]
        return self.fetch_all(sources=sources, max_total=max_total)

    def available_sources(self) -> list[str]:
        return list(RSS_SOURCES.keys())


class UserPreferenceLearner:
    """
    Aprende qué noticias y temas importan al usuario.
    Almacena preferencias en CORTEX para personalizar resultados futuros.
    """

    def __init__(self, cortex=None):
        self.cortex = cortex
        self.prefs_file = os.path.join(
            os.getenv("PROJECT_ROOT", os.path.expanduser("~/agent-office")),
            "data", "logs", "user_preferences.json"
        )
        self._prefs = self._load()

    def _load(self) -> dict:
        import json
        try:
            with open(self.prefs_file) as f:
                return json.load(f)
        except Exception:
            return {
                "liked_topics": [],
                "disliked_topics": [],
                "liked_sources": [],
                "disliked_sources": [],
                "keyword_scores": {},
                "interactions": [],
            }

    def _save(self):
        import json
        import pathlib
        pathlib.Path(self.prefs_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.prefs_file, "w") as f:
            json.dump(self._prefs, f, ensure_ascii=False, indent=2)

    def mark_relevant(self, article: dict, feedback: str = "like"):
        """Registra que una noticia fue relevante para el usuario."""
        title = article.get("title", "")
        source = article.get("source", "")
        categories = article.get("categories", [])

        entry = {
            "title": title,
            "source": source,
            "feedback": feedback,
            "date": datetime.datetime.now().isoformat(),
        }
        self._prefs["interactions"].append(entry)

        if feedback == "like":
            if source not in self._prefs["liked_sources"]:
                self._prefs["liked_sources"].append(source)
            for cat in categories:
                score = self._prefs["keyword_scores"].get(cat, 0)
                self._prefs["keyword_scores"][cat] = score + 1
        elif feedback == "dislike":
            for cat in categories:
                score = self._prefs["keyword_scores"].get(cat, 0)
                self._prefs["keyword_scores"][cat] = score - 1

        # Guardar en CORTEX si está disponible
        if self.cortex and feedback == "like":
            try:
                self.cortex.store_news([{
                    "title": f"[RELEVANTE para usuario] {title}",
                    "source": source,
                    "topic": "user_preference",
                    "relevance": "high",
                }])
            except Exception:
                pass

        self._save()
        logger.info(f"Preferencia registrada: {feedback} → {title[:50]}")

    def score_article(self, article: dict) -> float:
        """Puntúa una noticia según las preferencias aprendidas (0.0 - 1.0)."""
        score = 0.5
        source = article.get("source", "")
        categories = article.get("categories", [])

        if source in self._prefs["liked_sources"]:
            score += 0.2
        if source in self._prefs["disliked_sources"]:
            score -= 0.3

        for cat in categories:
            cat_score = self._prefs["keyword_scores"].get(cat, 0)
            score += cat_score * 0.05

        return max(0.0, min(1.0, score))

    def rank_articles(self, articles: list[dict]) -> list[dict]:
        """Ordena noticias por relevancia personalizada."""
        for a in articles:
            a["user_score"] = self.score_article(a)
        return sorted(articles, key=lambda x: x["user_score"], reverse=True)

    def get_profile(self) -> dict:
        """Resumen del perfil de preferencias aprendido."""
        top_cats = sorted(
            self._prefs["keyword_scores"].items(),
            key=lambda x: x[1], reverse=True
        )[:5]
        return {
            "fuentes_favoritas": self._prefs["liked_sources"][:5],
            "temas_top": [k for k, v in top_cats if v > 0],
            "total_interacciones": len(self._prefs["interactions"]),
        }
