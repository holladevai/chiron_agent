from core.autoacquire import Candidate, evaluate, load_trust
from core.lifecycle import Pipeline
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def _trust():
    return load_trust(None)


def test_official_org_auto_eligible():
    t = _trust()
    c = Candidate.from_dict({"org": "anthropics", "stars": 10, "pushed_days_ago": 20,
                             "license": "MIT", "risk_level": "low", "permissions": []})
    d = evaluate(c, t)
    assert d.eligible and d.tier == "official" and not d.requires_human


def test_high_star_eligible():
    t = _trust()
    c = Candidate.from_dict({"org": "randomorg", "stars": 5000, "pushed_days_ago": 30,
                             "license": "Apache-2.0", "risk_level": "low"})
    d = evaluate(c, t)
    assert d.eligible and d.tier == "high_star"


def test_low_star_untrusted():
    d = evaluate(Candidate.from_dict({"org": "x", "stars": 5, "license": "MIT"}), _trust())
    assert not d.eligible and d.tier == "untrusted" and d.requires_human


def test_dangerous_permission_forces_human():
    c = Candidate.from_dict({"org": "anthropics", "stars": 10, "pushed_days_ago": 5,
                             "license": "MIT", "risk_level": "medium",
                             "permissions": ["oauth_grant"]})
    d = evaluate(c, _trust())
    assert not d.eligible and d.requires_human


def test_high_risk_forces_human():
    c = Candidate.from_dict({"org": "anthropics", "stars": 10, "pushed_days_ago": 5,
                             "license": "MIT", "risk_level": "high"})
    d = evaluate(c, _trust())
    assert not d.eligible


def test_stale_repo_rejected():
    c = Candidate.from_dict({"org": "randomorg", "stars": 9000, "pushed_days_ago": 2000,
                             "license": "MIT", "risk_level": "low"})
    d = evaluate(c, _trust())
    assert not d.eligible


def test_bad_license_rejected():
    c = Candidate.from_dict({"org": "anthropics", "stars": 10, "pushed_days_ago": 5,
                             "license": "GPL-3.0-only", "risk_level": "low"})
    d = evaluate(c, _trust())
    assert not d.eligible


def test_auto_promote_full_gates(platform):
    pipe = Pipeline(platform)
    pipe.stage(FIXTURES / "benign-skill", "auto1", risk_level="low", domains=["example"])
    pipe.evaluate("auto1")
    meta = {"org": "anthropics", "stars": 100, "pushed_days_ago": 10,
            "license": "MIT", "source_url": "https://github.com/anthropics/x"}
    # Sonnet onaylamazsa kurulmaz -> insana gider
    r_reject = pipe.auto_promote("auto1", meta, review_verdict="reject",
                                 review_summary="supheli")
    assert r_reject["auto_installed"] is False
    assert r_reject["gate_failed"] == "sonnet_review"
    # Sonnet onaylarsa uc kapi gecer -> otomatik kurulur
    r_ok = pipe.auto_promote("auto1", meta, review_verdict="approve",
                             review_summary="temiz")
    assert r_ok["auto_installed"] is True
    assert (platform.active_skills / "auto1").exists()
    pipe.close()


def test_auto_promote_untrusted_goes_human(platform):
    pipe = Pipeline(platform)
    pipe.stage(FIXTURES / "benign-skill", "auto2", risk_level="low")
    pipe.evaluate("auto2")
    meta = {"org": "nobody", "stars": 3, "license": "MIT", "pushed_days_ago": 5}
    r = pipe.auto_promote("auto2", meta, review_verdict="approve")
    assert r["auto_installed"] is False
    assert r["gate_failed"] == "trust"
    assert not (platform.active_skills / "auto2").exists()
    pipe.close()


def test_lesson_to_skill_promotion(platform):
    from core.learning import LessonStore
    from core.skillgen import generate_skill_dir
    store = LessonStore(platform.lessons_db)
    r = store.add("Girdi dogrulamasini her zaman uygula", domain="security",
                  trigger="kullanici girdisi islenirken", rationale="injection")
    lesson = store.get(r["id"])
    skill_dir, skill_id = generate_skill_dir(lesson, platform.staging_skills)
    assert (skill_dir / "SKILL.md").exists()
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "description:" in text and "risk_level: low" in text

    pipe = Pipeline(platform)
    st = pipe.stage(skill_dir, skill_id, risk_level="low", domains=["security"],
                    source="learned")
    assert st["staged"]
    ev = pipe.evaluate(skill_id)
    assert ev["passed"]
    pr = pipe.promote(skill_id)
    assert pr["decision"] == "allow" and pr["installed"]
    assert (platform.active_skills / skill_id / "SKILL.md").exists()
    pipe.close()
    store.close()
