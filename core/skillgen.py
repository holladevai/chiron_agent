"""Dogrulanmis dersten OTOMATIK skill uretimi (deterministik, ~0 token).

Kullanicinin istegi: yapilan/dogrulanan/ogrenilen bilgiler ve web'den edinip
dogrulanan bilgiler otomatik skill'e donussun ve ihtiyac olunca otomatik kullanilsin.

Token verimliligi:
  - Uretim SABLON tabanlidir; LLM cagrisi YOK, ders alanlarindan (kural/tetikleyici/
    gerekce/alan) dogrudan gecerli bir SKILL.md yazilir.
  - Uretim NADIREN tetiklenir: yalnizca bir ders tekrar edip (uses >= esik) net
    pozitif oldugunda (kanitlanmis desen). Boylece her gorevde degil, ispat sonrasi.
  - "Otomatik kullanim" ek maliyet getirmez: skill .claude/skills/ altina kurulunca
    Claude Code onu ACIKLAMASINA gore progressive disclosure ile kendisi cagirir.

Guvenlik: uretilen skill de normal kapilardan gecer (statik tarama + eval + politika).
Zehirli bir ders skill'e donusemez; tarayici kritik bulguda reddeder.
"""
from __future__ import annotations

import re
from pathlib import Path

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, fallback: str = "learned-skill") -> str:
    s = _SLUG_RE.sub("-", (text or "").lower()).strip("-")
    s = "-".join([w for w in s.split("-") if w])[:48].strip("-")
    return s or fallback


def skill_name_from_lesson(lesson: dict) -> str:
    base = lesson.get("trigger") or lesson.get("rule") or "learned"
    slug = slugify(base)
    return f"learned-{slug}" if not slug.startswith("learned") else slug


def _description(lesson: dict) -> str:
    trigger = (lesson.get("trigger") or "").strip()
    rule = (lesson.get("rule") or "").strip()
    domain = (lesson.get("domain") or "").strip()
    parts = []
    if trigger:
        parts.append(f"{trigger} durumunda")
    parts.append(rule)
    if domain:
        parts.append(f"({domain})")
    desc = " ".join(parts)
    # frontmatter guvenligi: tek satir, tirnak/iki nokta sadelestir
    return desc.replace("\n", " ").replace('"', "'").strip()[:300]


def generate_skill_dir(lesson: dict, staging_root: Path) -> tuple[Path, str]:
    """Dersten staging altina bir skill dizini yazar. (dizin, skill_id) doner."""
    name = skill_name_from_lesson(lesson)
    domain = (lesson.get("domain") or "genel").strip()
    rule = (lesson.get("rule") or "").strip()
    trigger = (lesson.get("trigger") or "").strip()
    rationale = (lesson.get("rationale") or "").strip()
    uses = lesson.get("uses", 0)
    source = (lesson.get("source") or "learned").strip()

    skill_dir = Path(staging_root) / name
    skill_dir.mkdir(parents=True, exist_ok=True)

    md = f"""---
name: {name}
version: 0.1.0
status: experimental
description: {_description(lesson)}
domains: [{domain}]
risk_level: low
source: {source}
generated_from_lesson: true
lesson_uses: {uses}
---

# Amac

{rule}

# Ne zaman kullanilir

{trigger or "Bu prosedurun alaninda (" + domain + ") benzer bir gorevle karsilasildiginda."}

# Gerekce

{rationale or "Bu kural, tekrar eden gorevlerde " + str(uses) + " kez dogrulandi."}

# Prosedur

1. Gorevin bu kuralin kapsamina girip girmedigini dogrula.
2. Kurali uygula: {rule}
3. Sonucu dogrula; ise yaradiysa `python -m core learn reinforce` ile pekistir,
   yaramadiysa loss ver (skill gozden gecirilir).

# Guvenlik / sinirlar

- Bu skill tekrar eden bir dersten OTOMATIK uretildi; experimental seviyededir.
- Yalnizca dusuk riskli, salt-prosedur rehberligidir; genis yetki veya
  geri donussuz eylem talep etmez.
- Kapsam disinda kullanilmamalidir.

# Kaynak

Bu skill, dogrulanmis ve {uses} kez tekrar eden bir dersten uretildi (kaynak: {source}).
Yeterli olgunlukta [[skill-creator-safe]] ile zenginlestirilebilir.
"""
    (skill_dir / "SKILL.md").write_text(md, encoding="utf-8")
    return skill_dir, name
