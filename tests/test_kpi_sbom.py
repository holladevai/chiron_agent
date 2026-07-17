"""kpi.py + sbom.py — operasyonel metrik ve malzeme listesi (salt-okuma) testleri.

Izole gecici platformda registry + audit + ders verisi kurar, turetilen metrik ve
SBOM yapisini dogrular. Mevcut yapiyi bozmadan yalnizca OKUR.
"""
from __future__ import annotations

from core import kpi, sbom
from core.audit import AuditLog
from core.learning import LessonStore
from core.registry import Registry


def _seed(paths):
    reg = Registry(paths.registry_db)
    reg.add("skill-a", "1.0.0", status="project-approved", risk_level="low",
            source="seed", scan_score=100, validation_score=1.0)
    reg.add("skill-b", "1.0.0", status="project-approved", risk_level="medium",
            source="contrib", scan_score=90, validation_score=0.95)
    reg.add("skill-c", "0.1.0", status="revoked", risk_level="high",
            source="unknown", scan_score=40)
    reg.close()

    log = AuditLog(paths.audit_log)
    log.append("pipeline", "staged", {"capability": "skill-a"})
    log.append("pipeline", "staged", {"capability": "skill-b"})
    log.append("pipeline", "stage_rejected", {"capability": "skill-c"})
    log.append("guard_hook", "blocked", {"reason": "korunan dosya"})
    log.append("council", "consult", {"providers_used": ["openai"]})

    store = LessonStore(paths.lessons_db)
    lesson = store.add("Bir kural", domain="software")
    store.reinforce(lesson["id"], "win")
    store.close()


def test_kpi_structure_and_counts(platform):
    _seed(platform)
    k = kpi.compute_kpis(platform)
    assert set(k) >= {"capabilities", "acquisition_funnel", "security_activity",
                      "quality", "learning", "council", "audit", "freshness"}
    assert k["capabilities"]["active"] == 2          # a + b project-approved
    assert k["capabilities"]["by_status"]["revoked"] == 1
    assert k["acquisition_funnel"]["staged"] == 2
    assert k["acquisition_funnel"]["stage_rejected"] == 1
    assert k["security_activity"]["guard_blocked"] == 1
    assert k["council"]["consult_calls"] == 1
    assert k["audit"]["total_events"] == 5


def test_kpi_rates(platform):
    _seed(platform)
    k = kpi.compute_kpis(platform)
    # reject_rate = 1 / (2 staged + 1 rejected) = 0.333
    assert 0.3 <= k["acquisition_funnel"]["reject_rate"] <= 0.34
    # avg scan score active = (100 + 90) / 2
    assert k["quality"]["avg_scan_score_active"] == 95.0


def test_kpi_empty_platform(platform):
    # hic veri yokken cokme olmadan makul sifirlar
    k = kpi.compute_kpis(platform)
    assert k["capabilities"]["active"] == 0
    assert k["audit"]["total_events"] >= 0
    assert k["acquisition_funnel"]["reject_rate"] == 0.0


def test_sbom_structure(platform):
    _seed(platform)
    s = sbom.build_sbom(platform)
    assert s["format"] == "chiron-sbom/1"
    # yalnizca kurulu/aktif (a,b) SBOM'a girer; revoked (c) girmez
    ids = {c["id"] for c in s["capabilities"]}
    assert ids == {"skill-a", "skill-b"}
    assert s["capability_count"] == 2
    for c in s["capabilities"]:
        assert "content_hash" in c and "risk_level" in c


def test_sbom_dependencies_and_policy(platform):
    s = sbom.build_sbom(platform)
    assert isinstance(s["dependencies"], list)
    assert "policy" in s and "sealed" in s["policy"]


def test_sbom_parses_requirements(platform):
    (platform.root / "requirements.txt").write_text(
        "# yorum\nPyYAML>=6.0\npytest==7.4\nbare-package\n", encoding="utf-8")
    s = sbom.build_sbom(platform)
    deps = {d["name"]: d for d in s["dependencies"]}
    assert deps["PyYAML"]["constraint"] == ">=6.0"
    assert deps["pytest"]["constraint"] == "==7.4"
    assert deps["bare-package"]["constraint"] == ""
    assert all(d["type"] == "python-dependency" for d in s["dependencies"])
