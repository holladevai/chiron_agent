"""Otomatik yetenek edinme icin GUVEN KATMANI (trust tiering).

Kullanicinin istegi: resmi kaynaklardan ve GitHub'da yuksek puanli (yildizli)
adaylar, INSAN ONAYI BEKLEMEDEN otomatik kurulabilsin; icerik okunarak guvenlik
denetiminden gecirilsin (Sonnet ile).

Guvenlik modeli — otomatik kurulum UC bagimsiz kapinin HEPSINI gecmeden olmaz:
  1) GUVEN KATMANI (bu modul): kaynak resmi org mu, ya da yildiz esigini asan
     bakimli bir repo mu? Lisans uygun mu? Risk tavani asilmis mi?
  2) DETERMINISTIK TARAYICI (scanner.py): kritik bulgu = otomatik red. Bu kapi
     LLM'e degil regex kural motoruna dayanir; dis saldiri bunu atlayamaz.
  3) SONNET ICERIK INCELEMESI (auto-security-reviewer subagent): dosyalar okunur,
     yapisal APPROVE/REJECT verdikti audit'e yazilir.

Otomatik kurulum TAVANI: risk_level in {low, medium}. high/critical ve tehlikeli
izin isteyen (oauth, broker, production_write, genis dosya sistemi, secret export,
email, prod db migration, main'e push) adaylar guven ne olursa olsun INSANA gider.
Bu tavan sealed immutable-core ile de tutarlidir (install_capability_high_risk,
oauth_grant, broker_* zaten human_approval_always/deny).

Guven ayarlari kod icinde GUVENLI-KISITLAYICI varsayilanlardir; istege bagli olarak
policies/trust.yaml ile daraltilabilir/genisletilebilir (insan kararidir).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

# Resmi / guvenilir kuruluslar (kucuk harf). Bu org'lardan gelen aday 'official' katman.
OFFICIAL_ORGS = {
    "anthropics", "modelcontextprotocol", "github", "microsoft", "trailofbits",
    "vercel-labs", "vercel", "langchain-ai", "openai", "google", "googleapis",
    "apache", "pytorch", "huggingface", "freqtrade", "ccxt", "microsoft-playwright",
    "snyk", "nvidia", "ai4finance-foundation", "tauricresearch", "minedojo",
    "agentskills", "kubernetes", "hashicorp", "cloudflare", "denoland",
}

SAFE_DEFAULTS = {
    "official_orgs": sorted(OFFICIAL_ORGS),
    "min_stars_for_high_star_tier": 800,   # resmi olmayan repolar icin yildiz esigi
    "max_age_days": 540,                    # son push ~18 aydan yeni olmali
    "allowed_licenses": [
        "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
        "MPL-2.0", "Unlicense", "CC0-1.0",
    ],
    "auto_risk_ceiling": ["low", "medium"],  # yalnizca bunlar otomatik; ustu insana
    "min_scan_score": 85,
    "dangerous_permissions": [
        "oauth_grant", "broker_live_order", "broker_withdrawal", "production_write",
        "broad_filesystem", "secret_export", "email_send", "database_migration_prod",
        "push_main", "withdrawal",
    ],
}


@dataclass
class Candidate:
    id: str
    source_url: str = ""
    org: str = ""
    stars: int = 0
    pushed_days_ago: int = 9999
    license: str = ""
    risk_level: str = "medium"
    permissions: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Candidate":
        return cls(
            id=d.get("id", ""),
            source_url=d.get("source_url", ""),
            org=(d.get("org", "") or "").lower(),
            stars=int(d.get("stars", 0) or 0),
            pushed_days_ago=int(d.get("pushed_days_ago", 9999) or 9999),
            license=d.get("license", "") or "",
            risk_level=d.get("risk_level", "medium") or "medium",
            permissions=list(d.get("permissions", []) or []),
        )


@dataclass
class TrustDecision:
    eligible: bool
    tier: str                 # official | high_star | untrusted
    reasons: list[str] = field(default_factory=list)
    requires_human: bool = True

    def to_dict(self) -> dict:
        return vars(self)


def load_trust(paths=None) -> dict:
    """SAFE_DEFAULTS + istege bagli policies/trust.yaml (varsa)."""
    cfg = dict(SAFE_DEFAULTS)
    if paths is not None and yaml is not None:
        f = Path(paths.policies) / "trust.yaml"
        if f.exists():
            try:
                override = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
                cfg.update({k: v for k, v in override.items() if v is not None})
            except Exception:
                pass  # bozuk override -> guvenli varsayilanlar (fail-safe)
    cfg["official_orgs"] = {o.lower() for o in cfg.get("official_orgs", [])}
    return cfg


def evaluate(candidate: Candidate, trust: dict) -> TrustDecision:
    """Adayin OTOMATIK kuruluma uygun olup olmadigina karar verir (yan etkisiz)."""
    reasons: list[str] = []

    # Katman belirle
    if candidate.org in trust["official_orgs"]:
        tier = "official"
        reasons.append(f"resmi/guvenilir org: {candidate.org}")
    elif candidate.stars >= trust["min_stars_for_high_star_tier"]:
        tier = "high_star"
        reasons.append(f"yuksek yildiz: {candidate.stars} >= {trust['min_stars_for_high_star_tier']}")
    else:
        return TrustDecision(False, "untrusted", [
            f"ne resmi org ne de yildiz esigi ({candidate.stars} < "
            f"{trust['min_stars_for_high_star_tier']}) -> otomatik degil, insana git"
        ], requires_human=True)

    blockers: list[str] = []

    # Lisans
    allowed = {l.lower() for l in trust["allowed_licenses"]}
    if candidate.license.lower() not in allowed:
        blockers.append(f"lisans uygun degil/belirsiz: '{candidate.license or 'yok'}'")

    # Tazelik
    if candidate.pushed_days_ago > trust["max_age_days"]:
        blockers.append(f"bakimsiz: son push {candidate.pushed_days_ago} gun once "
                        f"(> {trust['max_age_days']})")

    # Risk tavani
    if candidate.risk_level not in trust["auto_risk_ceiling"]:
        blockers.append(f"risk '{candidate.risk_level}' otomatik tavanin ustunde "
                        f"({trust['auto_risk_ceiling']}) -> insan onayi")

    # Tehlikeli izinler
    dangerous = set(trust["dangerous_permissions"])
    hit = [p for p in candidate.permissions if p in dangerous]
    if hit:
        blockers.append(f"tehlikeli izin(ler): {', '.join(hit)} -> insan onayi")

    if blockers:
        return TrustDecision(False, tier, reasons + blockers, requires_human=True)

    reasons.append("lisans/tazelik/risk/izin kapilari gecti")
    return TrustDecision(True, tier, reasons, requires_human=False)
