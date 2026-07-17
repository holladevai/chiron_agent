"""providers.py + council.py — coklu-saglayici katmani (network MOCK'lu).

Gercek API cagrisi yapilmaz; `providers._post` monkeypatch'lenir. Dogrulananlar:
env'den kesif, anahtar maskeleme, istek/yanit sekilleri (anthropic/openai/gemini),
council fan-out toplama, ZARIF BOZULMA (0 ek saglayici) ve bir saglayici hata
verince digerlerinin etkilenmemesi.
"""
from __future__ import annotations

from core import council, providers

# --- kesif + maskeleme -------------------------------------------------------

def test_mask():
    assert providers.mask("sk-1234567890abcd") == "sk-1...abcd"
    assert providers.mask("short") == "***"
    assert providers.mask("") == ""


def test_discovery_from_env():
    env = {"OPENAI_API_KEY": "sk-openai-xxxx1234", "GEMINI_API_KEY": "g-yyyy5678zzzz"}
    provs = providers.available_providers(env)
    names = {p.name for p in provs}
    assert names == {"openai", "google"}
    for p in provs:
        assert "..." in p.key_masked or p.key_masked == "***"


def test_discovery_empty_env():
    assert providers.available_providers({}) == []


def test_nvidia_and_kimi_discovery():
    env = {"NVIDIA_API_KEY": "nvapi-xxxx1234yyyy", "MOONSHOT_API_KEY": "sk-kimi-5678abcd"}
    provs = {p.name: p for p in providers.available_providers(env)}
    assert "nvidia" in provs and "moonshot" in provs
    # NVIDIA NIM OpenAI-uyumlu ve kodlama-guclu varsayilan
    assert provs["nvidia"].kind == "openai"
    assert "integrate.api.nvidia.com" in provs["nvidia"].base
    assert "coder" in provs["nvidia"].model.lower()
    assert "kimi" in provs["moonshot"].model.lower()


def test_model_override(monkeypatch):
    monkeypatch.setenv("CHIRON_OPENAI_MODEL", "gpt-özel")
    provs = providers.available_providers({"OPENAI_API_KEY": "sk-aaaa1111bbbb"})
    assert provs[0].model == "gpt-özel"


def test_ollama_local_no_key():
    env = {"CHIRON_OLLAMA_BASE": "http://localhost:11434/v1"}
    provs = providers.available_providers(env)
    assert len(provs) == 1 and provs[0].name == "ollama"
    assert provs[0].key_masked == ""


# --- istek/yanit sekilleri (mock _post) --------------------------------------

def _provider(name):
    return next(p for p in providers.available_providers(_env_for(name)))


def _env_for(name):
    keymap = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
              "google": "GEMINI_API_KEY"}
    return {keymap[name]: "sk-test-key-abcd1234"}


def test_anthropic_shape(monkeypatch):
    captured = {}

    def fake_post(url, headers, payload, timeout):
        captured.update(url=url, headers=headers, payload=payload)
        return {"content": [{"type": "text", "text": "anthropic cevap"}]}
    monkeypatch.setattr(providers, "_post", fake_post)
    out = providers.complete(_provider("anthropic"), "soru", system="sis")
    assert out == "anthropic cevap"
    assert "api.anthropic.com" in captured["url"]
    assert captured["headers"]["x-api-key"] == "sk-test-key-abcd1234"
    assert captured["payload"]["system"] == "sis"


def test_openai_shape(monkeypatch):
    captured = {}

    def fake_post(url, headers, payload, timeout):
        captured.update(url=url, headers=headers, payload=payload)
        return {"choices": [{"message": {"content": "openai cevap"}}]}
    monkeypatch.setattr(providers, "_post", fake_post)
    out = providers.complete(_provider("openai"), "soru", system="sis")
    assert out == "openai cevap"
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"].startswith("Bearer ")
    assert captured["payload"]["messages"][0]["role"] == "system"


def test_gemini_shape(monkeypatch):
    def fake_post(url, headers, payload, timeout):
        assert "generativelanguage.googleapis.com" in url
        assert "key=" in url
        return {"candidates": [{"content": {"parts": [{"text": "gemini cevap"}]}}]}
    monkeypatch.setattr(providers, "_post", fake_post)
    out = providers.complete(_provider("google"), "soru")
    assert out == "gemini cevap"


def test_extract_handles_empty():
    assert providers._extract("openai", {}) == ""
    assert providers._extract("gemini", {"candidates": []}) == ""
    assert providers._extract("anthropic", {"content": []}) == ""


# --- council fan-out ---------------------------------------------------------

def test_consult_no_providers_degrades():
    res = council.consult("zor soru", env={})
    assert res.skipped_no_providers
    assert res.opinions == []
    assert "tek basina" in res.note


def test_consult_excludes_anthropic_by_default(monkeypatch):
    # anthropic + openai var; soruyu soran Claude oldugu icin anthropic haric
    monkeypatch.setattr(providers, "_post",
                        lambda *a, **k: {"choices": [{"message": {"content": "fikir"}}]})
    env = {"ANTHROPIC_API_KEY": "sk-anthropic-1234", "OPENAI_API_KEY": "sk-openai-1234"}
    res = council.consult("zor soru", env=env)
    assert res.providers_used == ["openai"]
    assert not res.skipped_no_providers


def test_consult_aggregates_multiple(monkeypatch):
    monkeypatch.setattr(providers, "_post",
                        lambda *a, **k: {"choices": [{"message": {"content": "bir fikir"}}]})
    env = {"OPENAI_API_KEY": "sk-a-1234", "MISTRAL_API_KEY": "sk-b-5678",
           "DEEPSEEK_API_KEY": "sk-c-9012"}
    res = council.consult("zor soru", env=env)
    assert len(res.opinions) == 3
    assert all(o.ok for o in res.opinions)
    # deterministik siralama
    assert [o.provider for o in res.opinions] == sorted(o.provider for o in res.opinions)


def test_consult_one_provider_fails_others_survive(monkeypatch):
    def flaky(url, headers, payload, timeout):
        if "mistral" in url:
            raise TimeoutError("mistral zaman asimi")
        return {"choices": [{"message": {"content": "saglam fikir"}}]}
    monkeypatch.setattr(providers, "_post", flaky)
    env = {"OPENAI_API_KEY": "sk-a-1234", "MISTRAL_API_KEY": "sk-b-5678"}
    res = council.consult("zor soru", env=env)
    ok = [o for o in res.opinions if o.ok]
    bad = [o for o in res.opinions if not o.ok]
    assert len(ok) == 1 and len(bad) == 1
    assert "zaman asimi" in bad[0].error or "TimeoutError" in bad[0].error


def test_consult_provider_filter(monkeypatch):
    monkeypatch.setattr(providers, "_post",
                        lambda *a, **k: {"choices": [{"message": {"content": "x"}}]})
    env = {"OPENAI_API_KEY": "sk-a-1234", "MISTRAL_API_KEY": "sk-b-5678"}
    res = council.consult("q", env=env, providers=["mistral"])
    assert res.providers_used == ["mistral"]


def test_consult_empty_answer_marked_not_ok(monkeypatch):
    monkeypatch.setattr(providers, "_post",
                        lambda *a, **k: {"choices": [{"message": {"content": ""}}]})
    res = council.consult("q", env={"OPENAI_API_KEY": "sk-a-1234"})
    assert res.opinions[0].ok is False
    assert "bos" in res.opinions[0].error


def test_to_dict_shape(monkeypatch):
    monkeypatch.setattr(providers, "_post",
                        lambda *a, **k: {"choices": [{"message": {"content": "x"}}]})
    d = council.consult("q", env={"OPENAI_API_KEY": "sk-a-1234"}).to_dict()
    assert set(d) == {"question", "providers_used", "opinions", "skipped_no_providers", "note"}
