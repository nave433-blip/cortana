"""Track 1 tests: hive mind consensus, shared cache, capability registry.

No network, no LLMs — provider asks, synthesis, and peer calls are mocked.
"""
import json
import time

import pytest

import core.config as config_mod
import core.hive as hive


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    fake_file = tmp_path / "config.json"
    monkeypatch.setattr(config_mod, "CONFIG_FILE", fake_file)
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(hive, "CACHE_FILE", tmp_path / "hive_cache.json")
    return tmp_path


# ---------------------------------------------------------------- hashing

def test_prompt_hash_normalizes(isolated):
    assert hive.prompt_hash("Hello   World") == hive.prompt_hash("hello world")
    assert hive.prompt_hash("  Hi? ") == hive.prompt_hash("hi?")
    assert hive.prompt_hash("a") != hive.prompt_hash("b")


# ---------------------------------------------------------------- local cache

def test_cache_store_and_lookup(isolated):
    hive.cache_store_local("What is 2+2?", "m1", "4")
    hits = hive.cache_lookup_local("what is 2+2?")
    assert len(hits) == 1
    assert hits[0]["answer"] == "4"
    assert hits[0]["model"] == "m1"
    assert hits[0]["origin"] == "local"


def test_cache_miss(isolated):
    assert hive.cache_lookup_local("never asked") == []


def test_cache_ttl_expiry(isolated, monkeypatch):
    hive.cache_store_local("q", "m", "a")
    assert hive.cache_lookup_local("q", ttl=3600)
    # ttl=0 -> everything stale
    assert hive.cache_lookup_local("q", ttl=0) == []


def test_cache_file_is_private(isolated):
    import os, stat
    hive.cache_store_local("q", "m", "a")
    mode = stat.S_IMODE(os.stat(hive.CACHE_FILE).st_mode)
    assert mode == 0o600


def test_cache_prunes_at_cap(isolated, monkeypatch):
    monkeypatch.setattr(hive, "MAX_CACHE_ENTRIES", 3)
    for i in range(5):
        hive.cache_store_local(f"question {i}", "m", f"answer {i}")
    total = sum(len(v) for v in hive._load_cache().values())
    assert total <= 3


# ---------------------------------------------------------------- sharing gate

def test_peer_lookup_disabled_by_default(isolated):
    assert hive.sharing_enabled() is False
    assert hive.cache_lookup_peers("anything") == []
    assert hive.cache_share_peers("q", "m", "a") == 0


# ---------------------------------------------------------------- model resolution

def test_resolve_hive_model_unknown_provider_skipped(isolated):
    assert hive.resolve_hive_model("definitely_not_a_provider") is None


def test_resolve_hive_model_prefers_user_default(isolated, monkeypatch):
    import core.services as services
    monkeypatch.setattr(services, "get_default_model", lambda p: "custom/model-x")
    assert hive.resolve_hive_model("openai") == "custom/model-x"


def test_resolve_hive_model_fallback(isolated, monkeypatch):
    import core.services as services
    monkeypatch.setattr(services, "get_default_model", lambda p: None)
    assert hive.resolve_hive_model("groq") == "groq/llama-3.3-70b-versatile"


def test_hive_candidates_marks_unresolvable(isolated, monkeypatch):
    monkeypatch.setattr(hive, "resolve_hive_model", lambda p: None)
    cands = hive.hive_candidates(["openai"])
    assert cands[0].get("skipped") is True


# ---------------------------------------------------------------- hive_ask

def _fake_answers(*answers):
    def _ask(provider, model, question, timeout):
        return {"provider": provider, "model": model, "ok": True,
                "text": answers[0] if len(answers) == 1 else f"{provider} says {answers[0]}",
                "latency_ms": 5}
    return _ask


def test_hive_ask_consensus_path(isolated, monkeypatch):
    monkeypatch.setattr(hive, "_ask_one", _fake_answers("42"))
    monkeypatch.setattr(hive, "synthesize_consensus",
                        lambda q, a: {"ok": True, "text": "CONSENSUS", "method": "synthesized"})
    monkeypatch.setattr(hive, "hive_candidates",
                        lambda providers=None: [{"provider": "a", "model": "a/m"},
                                                {"provider": "b", "model": "b/m"}])
    res = hive.hive_ask("what is the answer?", use_cache=False)
    assert res["ok"] is True
    assert res["text"] == "CONSENSUS"
    assert len(res["attributions"]) == 2
    assert all(a["ok"] for a in res["attributions"])


def test_hive_ask_cache_hit_skips_providers(isolated, monkeypatch):
    hive.cache_store_local("cached question", "m1", "CACHED ANSWER")
    def _boom(*a, **k):
        raise AssertionError("providers must not be asked on cache hit")
    monkeypatch.setattr(hive, "_ask_one", _boom)
    res = hive.hive_ask("CACHED QUESTION")
    assert res["ok"] is True
    assert res["text"] == "CACHED ANSWER"
    assert res["method"] == "cache"


def test_hive_ask_no_providers(isolated, monkeypatch):
    monkeypatch.setattr(hive, "hive_candidates", lambda providers=None: [])
    res = hive.hive_ask("q", use_cache=False)
    assert res["ok"] is False
    assert "next_steps" in res


def test_hive_ask_all_fail(isolated, monkeypatch):
    def _fail(provider, model, question, timeout):
        return {"provider": provider, "model": model, "ok": False,
                "error": "boom", "latency_ms": 1}
    monkeypatch.setattr(hive, "_ask_one", _fail)
    monkeypatch.setattr(hive, "hive_candidates",
                        lambda providers=None: [{"provider": "a", "model": "a/m"}])
    res = hive.hive_ask("q", use_cache=False)
    assert res["ok"] is False
    assert res["error"] == "all providers failed"


def test_synthesize_fallback_never_drops_answers(isolated, monkeypatch):
    import core.brain as brain
    def _raise(*a, **k):
        raise RuntimeError("synthesizer down")
    monkeypatch.setattr(brain, "think_structured", _raise)
    out = hive.synthesize_consensus("q", [
        {"provider": "a", "model": "a/m", "text": "answer A"},
        {"provider": "b", "model": "b/m", "text": "answer B"},
    ])
    assert out["method"] == "concatenated"
    assert "answer A" in out["text"] and "answer B" in out["text"]


# ---------------------------------------------------------------- capabilities

def test_local_capabilities_never_carry_key_material(isolated, monkeypatch):
    import core.connect as connect_mod
    monkeypatch.setattr(connect_mod, "is_configured", lambda p: p == "openai")
    caps = hive.local_capabilities()
    assert caps["providers"] == ["openai"]
    blob = json.dumps(caps).lower()
    # Action names like "list_tokens"/"get_token" legitimately contain
    # "token" — check for actual key-shaped material instead.
    assert "sk-" not in blob
    for needle in ("api_key", "apikey", "secret", "bearer", "private_key"):
        assert needle not in blob, f"key-like material leaked: {needle}"
    assert set(caps.keys()) == {"providers", "models", "features", "local_services"}
    # Every advertised value must be a known identifier, not a secret value.
    from core.connect import AuthManager
    assert all(p in AuthManager.PROVIDERS for p in caps["providers"])


def test_local_services_advertised_honestly(isolated):
    caps = hive.local_capabilities()
    services = caps["local_services"]
    assert set(services) == {"scheduler", "dashboard"}
    sched = services["scheduler"]
    assert sched["available"] is True
    assert isinstance(sched["running"], bool)
    assert isinstance(sched["jobs"], int)
    assert services["dashboard"] == {"available": True, "default_bind": "loopback"}
    # local_services must not affect P2P action gating.
    from core.p2p import is_p2p_compatible, CURRENT_VERSION
    assert not is_p2p_compatible(CURRENT_VERSION, "scheduler")
    assert not is_p2p_compatible(CURRENT_VERSION, "dashboard")
