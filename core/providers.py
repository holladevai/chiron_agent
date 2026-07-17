"""Coklu-saglayici LLM soyutlamasi — "kac API varsa o kadar model, tek varsa tekiyle".

Ana beyin Claude'dur (Claude Code). Bu katman, ANAHTARLARI env'de MEVCUT olan
diger saglayicilari kesfeder ve ortak bir arayuze koyar; boylece Claude takildigi
zor islerde onlara fikir/ikinci gorus sorabilir (bkz. core/council.py).

Ilkeler:
  - Zarif bozulma: hic ek anahtar yoksa katman bos doner, sistem Claude ile calisir.
  - Minimal bagimlilik (ponytail): yalnizca stdlib urllib; SDK yok.
  - Guvenlik: anahtarlar YALNIZCA env'den okunur; audit'e MASKELI yazilir
    (sk-... abcd), asla koda/log'a acik girmez.
  - Genisletilebilir: yeni saglayici = PROVIDERS tablosuna bir satir.

Model kimlikleri env ile override edilebilir (CHIRON_<PROV>_MODEL); varsayilanlar
zamanla eskiyebilecegi icin override desteklenir.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

# --- saglayici tanimlari ------------------------------------------------------
# kind: "anthropic" | "openai" | "gemini"  -> istek/yanit sekli
# env_key: API anahtarinin okunacagi ortam degiskeni
# base: OpenAI-uyumlu taban URL (kind=openai) — chat/completions eklenir
# default_model: CHIRON_<PROV>_MODEL yoksa kullanilacak model

@dataclass(frozen=True)
class ProviderSpec:
    name: str
    kind: str
    env_key: str
    default_model: str
    base: str = ""


PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec("anthropic", "anthropic", "ANTHROPIC_API_KEY", "claude-sonnet-5"),
    ProviderSpec("openai", "openai", "OPENAI_API_KEY", "gpt-4o", "https://api.openai.com/v1"),
    ProviderSpec("google", "gemini", "GEMINI_API_KEY", "gemini-2.5-pro"),
    # NVIDIA NIM — OpenAI-uyumlu; en iyi ACIK KODLAMA modellerini barindirir
    # (Qwen3-Coder, DeepSeek, Kimi K2...). Anahtar: nvapi-... Varsayilan: en guclu
    # kodlama modeli. Model listesi hizli degisir -> CHIRON_NVIDIA_MODEL ile override.
    ProviderSpec("nvidia", "openai", "NVIDIA_API_KEY",
                 "qwen/qwen3-coder-480b-a35b-instruct", "https://integrate.api.nvidia.com/v1"),
    # Moonshot / Kimi — 2026-07 dogrulandi: Kimi K2 ailesi (2025) EMEKLI (25 May 2026).
    # Guncel: kimi-k3 (amiral), kimi-k2.7-code (kodlama uzmani) — varsayilan kodlama.
    # UCRETSIZ Kimi icin: OpenRouter + model "moonshotai/kimi-k2.6:free".
    ProviderSpec("moonshot", "openai", "MOONSHOT_API_KEY",
                 "kimi-k2.7-code", "https://api.moonshot.ai/v1"),
    ProviderSpec("mistral", "openai", "MISTRAL_API_KEY", "mistral-large-latest", "https://api.mistral.ai/v1"),
    # DeepSeek — deepseek-chat (V3) genel+kodlama; deepseek-reasoner muhakeme icin
    ProviderSpec("deepseek", "openai", "DEEPSEEK_API_KEY", "deepseek-chat", "https://api.deepseek.com/v1"),
    ProviderSpec("groq", "openai", "GROQ_API_KEY", "llama-3.3-70b-versatile", "https://api.groq.com/openai/v1"),
    ProviderSpec("xai", "openai", "XAI_API_KEY", "grok-2-latest", "https://api.x.ai/v1"),
    # OpenRouter — tek anahtarla 400+ model (kodlama modeli de secilebilir)
    ProviderSpec("openrouter", "openai", "OPENROUTER_API_KEY", "openai/gpt-4o", "https://openrouter.ai/api/v1"),
    # Fireworks — acik kodlama modelleri (Qwen/DeepSeek/Kimi) hizli servis
    ProviderSpec("fireworks", "openai", "FIREWORKS_API_KEY",
                 "accounts/fireworks/models/qwen3-coder-480b-a35b-instruct",
                 "https://api.fireworks.ai/inference/v1"),
    ProviderSpec("together", "openai", "TOGETHER_API_KEY",
                 "Qwen/Qwen3-Coder-480B-A35B-Instruct", "https://api.together.xyz/v1"),
)

# Ollama (yerel) — anahtar gerektirmez; CHIRON_OLLAMA_BASE ayarliysa etkinlesir.
OLLAMA_ENV = "CHIRON_OLLAMA_BASE"
OLLAMA_MODEL_ENV = "CHIRON_OLLAMA_MODEL"


def mask(secret: str) -> str:
    """Anahtari audit/log icin maskeler: ilk 4 + son 4 karakter."""
    if not secret:
        return ""
    if len(secret) <= 10:
        return "***"
    return f"{secret[:4]}...{secret[-4:]}"


def _model_for(spec: ProviderSpec) -> str:
    return os.environ.get(f"CHIRON_{spec.name.upper()}_MODEL", spec.default_model)


@dataclass
class Provider:
    name: str
    kind: str
    model: str
    _key: str = ""
    base: str = ""

    @property
    def key_masked(self) -> str:
        return mask(self._key)


def available_providers(env: dict | None = None) -> list[Provider]:
    """env'de anahtari MEVCUT olan saglayicilari dondurur (kesif)."""
    env = env if env is not None else dict(os.environ)
    out: list[Provider] = []
    for spec in PROVIDERS:
        key = env.get(spec.env_key, "").strip()
        if key:
            out.append(Provider(spec.name, spec.kind, _model_for(spec), key, spec.base))
    # yerel Ollama (anahtarsiz)
    ollama_base = env.get(OLLAMA_ENV, "").strip()
    if ollama_base:
        model = env.get(OLLAMA_MODEL_ENV, "llama3.1")
        out.append(Provider("ollama", "openai", model, "", ollama_base.rstrip("/")))
    return out


def provider_names(env: dict | None = None) -> list[str]:
    return [p.name for p in available_providers(env)]


# --- HTTP (stdlib; testler bunu monkeypatch'ler) ------------------------------

def _post(url: str, headers: dict, payload: dict, timeout: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")  # nosec B310 - sabit https saglayici URL'leri
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        return json.loads(resp.read().decode("utf-8", "replace"))


def _payload_and_headers(p: Provider, system: str, prompt: str, max_tokens: int):
    if p.kind == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": p._key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": p.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        return url, headers, payload
    if p.kind == "gemini":
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{p.model}:generateContent?key={p._key}")
        headers = {"content-type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        return url, headers, payload
    # openai-uyumlu
    url = f"{p.base.rstrip('/')}/chat/completions"
    headers = {"content-type": "application/json"}
    if p._key:
        headers["Authorization"] = f"Bearer {p._key}"
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    payload = {"model": p.model, "messages": msgs, "max_tokens": max_tokens}
    return url, headers, payload


def _extract(kind: str, resp: dict) -> str:
    if kind == "anthropic":
        parts = resp.get("content") or []
        return "".join(b.get("text", "") for b in parts if isinstance(b, dict)).strip()
    if kind == "gemini":
        cands = resp.get("candidates") or []
        if not cands:
            return ""
        parts = (cands[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    # openai-uyumlu
    choices = resp.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("message") or {}).get("content", "").strip()


def complete(p: Provider, prompt: str, *, system: str = "",
             max_tokens: int = 1024, timeout: int = 60) -> str:
    """Tek saglayiciya soru sorar, metin doner. Hata yukselir (cagiran yakalar)."""
    url, headers, payload = _payload_and_headers(p, system, prompt, max_tokens)
    resp = _post(url, headers, payload, timeout)
    return _extract(p.kind, resp)
