"""Operasyonel KPI olcumu — vizyon dokumani Bolum 33'un somut hali.

Mevcut deterministik kayitlardan (audit zinciri + registry + ders defteri) TUREV
metrikler uretir. Hicbir sey yazmaz; salt-okuma. Boylece "sistem ne kadar is yapti,
ne kadar guvenli, ne kadar ogrendi" olculebilir olur — LLM'e yuk bindirmeden.

Metrikler:
  - yetenek envanteri: statuye gore sayim + aktif sayisi
  - edinme hunisi: staged / rejected / installed / revoked + oranlar
  - guvenlik etkinligi: guard blocked, stage_rejected sayilari
  - kalite: aktif yeteneklerin ort. tarama/dogrulama skoru
  - ogrenme: ders sayilari + toplam kullanim (reuse sinyali)
  - denetim: toplam olay + eyleme gore kirilim
  - tazelik: yeniden-dogrulama bekleyen (stale) sayisi
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .learning import LessonStore
from .paths import Paths
from .registry import ACTIVE_STATUSES, Registry


def _read_audit(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _rate(numer: int, denom: int) -> float:
    return round(numer / denom, 3) if denom else 0.0


def compute_kpis(paths: Paths | None = None) -> dict:
    paths = paths or Paths()
    reg = Registry(paths.registry_db)
    try:
        rows = reg.list()
    finally:
        reg.close()

    by_status = Counter(r["status"] for r in rows)
    active = [r for r in rows if r["status"] in ACTIVE_STATUSES]
    revoked = by_status.get("revoked", 0)
    installed = len(active) + by_status.get("deprecated", 0)

    def _avg(field: str) -> float:
        vals = [r[field] for r in active if r.get(field) is not None]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    # audit
    events = _read_audit(paths.audit_log)
    actions = Counter(e.get("action", "?") for e in events)
    staged = actions.get("staged", 0)
    stage_rejected = actions.get("stage_rejected", 0)
    promote_decisions = actions.get("promote_decision", 0)
    blocked = actions.get("blocked", 0)
    consults = actions.get("consult", 0)

    # ogrenme
    lessons_stats: dict = {}
    total_uses = 0
    try:
        store = LessonStore(paths.lessons_db)
        try:
            lessons_stats = store.stats()
            rows_l = store._conn.execute("SELECT COALESCE(SUM(uses),0) s FROM lessons").fetchone()
            total_uses = int(rows_l["s"]) if rows_l else 0
        finally:
            store.close()
    except Exception:
        pass

    # tazelik
    reg2 = Registry(paths.registry_db)
    try:
        stale_n = len(reg2.stale())
    finally:
        reg2.close()

    return {
        "capabilities": {
            "total_records": len(rows),
            "by_status": dict(by_status),
            "active": len(active),
        },
        "acquisition_funnel": {
            "staged": staged,
            "stage_rejected": stage_rejected,
            "promote_decisions": promote_decisions,
            "installed": installed,
            "revoked": revoked,
            "reject_rate": _rate(stage_rejected, staged + stage_rejected),
            "revoke_rate": _rate(revoked, installed + revoked),
        },
        "security_activity": {
            "guard_blocked": blocked,
            "stage_rejected": stage_rejected,
        },
        "quality": {
            "avg_scan_score_active": _avg("scan_score"),
            "avg_validation_score_active": _avg("validation_score"),
        },
        "learning": {
            "lessons_by_status": lessons_stats,
            "total_lesson_uses": total_uses,
        },
        "council": {
            "consult_calls": consults,
        },
        "audit": {
            "total_events": len(events),
            "by_action": dict(actions),
        },
        "freshness": {
            "stale_awaiting_revalidation": stale_n,
        },
    }
