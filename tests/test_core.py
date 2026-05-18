"""
Tests básicos — Oficina de Agentes IA
Ejecutar: python -m pytest tests/test_core.py -v
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_config_validation():
    from core.config.settings import config
    missing = config.validate()
    assert isinstance(missing, list)
    assert "ANTHROPIC_KEY" in config.__class__.__dict__ or hasattr(config, "ANTHROPIC_KEY")
    print(f"  Config OK. Missing keys: {missing}")


def test_llm_router_imports():
    from core.tools.llm_router import LLMRouter
    router = LLMRouter()
    assert router.route is not None
    assert router.call is not None
    assert router.track_cost is not None
    tests = [
        ("Clasifica estos leads", "low", "ollama"),
        ("Redacta un email importante", "medium", "claude"),
        ("Analiza esta imagen", "medium", "gemini"),
        ("Tarea compleja de razonamiento", "high", "claude"),
    ]
    for task, complexity, expected in tests:
        result = router.route(task, complexity)
        assert result == expected, f"Expected {expected}, got {result} for '{task}'"
    print(f"  LLM Router routing: 4/4 OK")


def test_chroma_store():
    from core.memory.chroma_store import ChromaStore
    store = ChromaStore()
    keys = list(store.collections.keys())
    expected = ["leads", "clients", "errors", "strategies", "social_content", "market_intel"]
    for name in expected:
        assert name in keys, f"Missing collection: {name}"
    doc_id = store.store("leads", "Test lead",
                         metadata={"agent": "pytest", "score": 80})
    assert doc_id is not None
    assert len(doc_id) > 0
    results = store.search("leads", "test lead", n_results=5, min_relevance=0.0)
    assert len(results) >= 1
    count = store.count("leads")
    assert count >= 1
    print(f"  ChromaStore: {len(keys)} collections, {count} docs in leads")


def test_notifier():
    from core.tools.notifier import Notifier
    n = Notifier()
    result = n.send("Test notification", priority="low", agent="pytest")
    assert result is None
    print(f"  Notifier: basic send OK")


def test_agents_initialization():
    agent_names = ["cortex", "hermes", "iris", "atlas", "herald", "forge", "nexus"]
    for name in agent_names:
        module = __import__(f"agents.{name}.agent", fromlist=["*"])
        cls_name = f"{name.capitalize()}Agent"
        agent_cls = getattr(module, cls_name)
        agent = agent_cls()
        report = agent.report()
        assert report.get("status") == "operational", f"{name} status: {report}"
        assert report.get("agent") == name
        print(f"  {name.upper()}: operativo (sandbox={report.get('sandbox')})")


def test_agents_run_methods():
    from agents.cortex.agent import CortexAgent
    c = CortexAgent()
    result = c.run("almacenar evento de prueba", {"agent": "test", "event_type": "test", "data": {"key": "val"}})
    assert result["status"] == "ok"

    from agents.hermes.agent import HermesAgent
    h = HermesAgent()
    result = h.run("buscar leads", {"target": 3})
    assert result["status"] == "ok"

    from agents.iris.agent import IrisAgent
    i = IrisAgent()
    result = i.run("generar ideas de contenido")
    assert result["status"] == "ok"

    from agents.atlas.agent import AtlasAgent
    a = AtlasAgent()
    result = a.run("generar briefing matutino")
    assert result["status"] == "ok"

    from agents.herald.agent import HeraldAgent
    h2 = HeraldAgent()
    result = h2.run("clasificar inbox")
    assert result["status"] == "ok"

    from agents.forge.agent import ForgeAgent
    f = ForgeAgent()
    result = f.run("monitorizar logs")
    assert result["status"] == "ok"

    from agents.nexus.agent import NexusAgent
    n = NexusAgent()
    result = n.run("analizar mercado financiero")
    assert "status" in result

    print(f"  Todos los agentes ejecutan run() sin errores")


def test_nexus_orchestrate():
    from agents.nexus.agent import NexusAgent
    n = NexusAgent()
    result = n.orchestrate("Clasifica estos leads", priority=3)
    assert result is not None
    assert "status" in result
    print(f"  NEXUS orchestrate: {result.get('status')}")


def test_daily_cost_tracking():
    from core.tools.llm_router import LLMRouter
    router = LLMRouter()
    cost = router.daily_cost()
    assert isinstance(cost, (int, float))
    assert cost >= 0
    router.track_cost("ollama", 100, 50)
    new_cost = router.daily_cost()
    assert new_cost >= cost
    print(f"  Cost tracking: ${new_cost}")


if __name__ == "__main__":
    test_config_validation()
    test_llm_router_imports()
    test_chroma_store()
    test_notifier()
    test_agents_initialization()
    test_agents_run_methods()
    test_nexus_orchestrate()
    test_daily_cost_tracking()
    print("\n✅ TODOS LOS TESTS PASARON")
