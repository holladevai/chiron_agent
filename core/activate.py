"""Ajan aktivasyonu: otomatik devreye girme + komutla ac/kapa.

Uc davranis:
  1) OTOMATIK: her Claude Code oturumunda SessionStart hook'u calisir; durum
     'active' ise kompakt calisma protokolunu context'e enjekte eder.
  2) KOMUTLA AC: kullanici "ajan devreye gir" derse UserPromptSubmit hook'u
     durumu active yapar ve protokolu enjekte eder.
  3) KOMUTLA KAPA: kullanici "is bitti" (veya "ajan dur/kapan") derse durum
     inactive olur; artik protokol enjekte edilmez.

Durum kalicidir (.ajan_state.json, gitignore'da). Varsayilan: active (otomatik).

Token verimliligi: protokol kisadir ve oturumda bir kez (SessionStart) ya da
yalnizca tetikleyici cumlede (UserPromptSubmit) enjekte edilir; her promptta DEGIL.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

STATE_FILENAME = ".ajan_state.json"

# Kompakt standing directive (~150 token). Detay CLAUDE.md ve .claude/skills'te.
PROTOCOL = """[AJAN AKTIF] Bu projede otonom yetenek platformu devrede. Calisma kurallari:
1) Riskli/belirsiz veya "en iyi/guncel/dogrula" istenen gorevde ONCE yetkinlik acigini olc:
   `python -m core gap --domain <alan> --skills <id,..> --risk <seviye>`. Dusuk guven ->
   capability-manager subagent ile yetenek edin.
2) Yetenek edinme: guvenilir kaynak (resmi org / yuksek yildizli repo) -> otomatik serit
   (auto-capability-acquisition: guven katmani + tarama + auto-security-reviewer/Sonnet).
   Bilinmeyen kaynak/yuksek risk/tehlikeli izin -> secure-capability-acquisition (insan onayi).
3) Sonuc: yuksek risk veya dusuk guvende evaluator subagent ile bagimsiz dogrula.
   "Bitti" demeden kanit uret.
4) Ogrenme (token-verimli): gorev sonu genel+tekrar eden ders varsa `learn add`;
   olgunlasinca `learn promote` ile otomatik skill olur. Once `learn recall` ile hatirla.
5) Sinirlar: policies/immutable-core mutlak; guard hook zorunlu. Kalici kurulum, production,
   e-posta, canli trade -> insan onayli (deny-by-default). Ponytail: gereksiz kod/bagimlilik ekleme.
Detay: CLAUDE.md ve .claude/skills/."""

DISENGAGED_NOTE = ("[AJAN DEVREDEN CIKTI] Otonom platform protokolu bu oturumda pasif. "
                   "Tekrar acmak icin: \"ajan devreye gir\".")

ENGAGE_RE = re.compile(
    r"(^|\s)/?ajan[ıi]?\b.{0,20}(devreye|aktif|ba[şs]la|[çc]al[ıi][şs]|a[çc]|gir)"
    r"|(^|\s)/ajan\b",
    re.IGNORECASE)

DISENGAGE_RE = re.compile(
    r"\bi[şs]\s*bitti\b"
    r"|\bajan[ıi]?\b.{0,15}(dur|kapan|kapat|[çc]ık|cik|devreden|pasif|bitir)"
    r"|(^|\s)/ajan[- ]?(dur|kapat|off|stop)\b",
    re.IGNORECASE)


def _state_path(paths) -> Path:
    return Path(paths.root) / STATE_FILENAME


def is_active(paths) -> bool:
    p = _state_path(paths)
    if not p.exists():
        return True  # varsayilan: otomatik aktif
    try:
        return bool(json.loads(p.read_text(encoding="utf-8")).get("active", True))
    except Exception:
        return True


def set_active(paths, active: bool) -> None:
    _state_path(paths).write_text(
        json.dumps({"active": active}, ensure_ascii=True), encoding="utf-8")


def classify(prompt: str) -> str | None:
    """'engage' | 'disengage' | None. Disengage onceliklidir."""
    text = prompt or ""
    if DISENGAGE_RE.search(text):
        return "disengage"
    if ENGAGE_RE.search(text):
        return "engage"
    return None
