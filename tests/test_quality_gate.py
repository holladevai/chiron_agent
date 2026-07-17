"""quality_gate.py — deterministik Definition-of-Done kapisinin davranis testleri.

Alt-surecleri (pytest/coverage/ruff/bandit/verify) mock'layarak kapinin karar
mantigini hizli ve deterministik dogrular: done yalnizca engelleyici kontrol
yoksa True; unavailable yalnizca ZORUNLU kontrolde engeller.
"""
from __future__ import annotations

from core import quality_gate as qg
from core.quality_gate import Check, run_gate


def test_check_blocks_semantics():
    assert Check("x", "fail", required=True).blocks
    assert Check("x", "fail", required=False).blocks
    assert Check("x", "unavailable", required=True).blocks
    assert not Check("x", "unavailable", required=False).blocks
    assert not Check("x", "pass", required=True).blocks


def _patch_all(monkeypatch, mapping):
    """CHECK_FUNCS'i sabit Check dondurecek sekilde degistir."""
    for name, check in mapping.items():
        monkeypatch.setitem(qg.CHECK_FUNCS, name, (lambda c: (lambda root, mc: c))(check))


def test_all_pass_is_done(tmp_path, monkeypatch):
    _patch_all(monkeypatch, {
        "tests": Check("tests", "pass", True),
        "coverage": Check("coverage", "pass", False),
        "lint": Check("lint", "pass", False),
        "security": Check("security", "pass", False),
        "integrity": Check("integrity", "pass", True),
    })
    res = run_gate(tmp_path)
    assert res.done
    assert "DONE" in res.summary()


def test_failing_test_blocks_done(tmp_path, monkeypatch):
    _patch_all(monkeypatch, {
        "tests": Check("tests", "fail", True, "1 failed", "fix tests"),
        "coverage": Check("coverage", "pass", False),
        "lint": Check("lint", "pass", False),
        "security": Check("security", "pass", False),
        "integrity": Check("integrity", "pass", True),
    })
    res = run_gate(tmp_path)
    assert not res.done
    assert any("fix tests" in a for a in res.next_actions)


def test_missing_optional_tool_does_not_block(tmp_path, monkeypatch):
    _patch_all(monkeypatch, {
        "tests": Check("tests", "pass", True),
        "coverage": Check("coverage", "unavailable", False, "coverage yok"),
        "lint": Check("lint", "unavailable", False, "ruff yok"),
        "security": Check("security", "unavailable", False, "bandit yok"),
        "integrity": Check("integrity", "pass", True),
    })
    res = run_gate(tmp_path)
    assert res.done                      # zorunlu kontroller gecti
    assert len(res.warnings) == 3        # opsiyonel araclar uyari olarak raporlanir


def test_missing_required_tool_blocks(tmp_path, monkeypatch):
    _patch_all(monkeypatch, {
        "tests": Check("tests", "pass", True),
        "coverage": Check("coverage", "pass", False),
        "lint": Check("lint", "pass", False),
        "security": Check("security", "pass", False),
        "integrity": Check("integrity", "unavailable", True, "verify yok"),
    })
    res = run_gate(tmp_path)
    assert not res.done                  # zorunlu kontrol yok -> done degil


def test_lint_failure_blocks_but_is_optional_required_false(tmp_path, monkeypatch):
    _patch_all(monkeypatch, {
        "tests": Check("tests", "pass", True),
        "coverage": Check("coverage", "pass", False),
        "lint": Check("lint", "fail", False, "F401", "ruff --fix"),
        "security": Check("security", "pass", False),
        "integrity": Check("integrity", "pass", True),
    })
    res = run_gate(tmp_path)
    assert not res.done                  # fail her zaman engeller (opsiyonel olsa da)


def test_skip_excludes_check(tmp_path, monkeypatch):
    _patch_all(monkeypatch, {
        "tests": Check("tests", "pass", True),
        "coverage": Check("coverage", "fail", False, "dusuk"),
        "lint": Check("lint", "pass", False),
        "security": Check("security", "pass", False),
        "integrity": Check("integrity", "pass", True),
    })
    res = run_gate(tmp_path, skip=("coverage",))
    assert res.done                      # coverage atlandi -> engel yok
    assert all(c.name != "coverage" for c in res.checks)


# --- tekil kontrol fonksiyonlari (_run mock'lanir) ---------------------------

def _fake_run(monkeypatch, rc, out):
    monkeypatch.setattr(qg, "_run", lambda cmd, cwd, timeout=900: (rc, out))


def test_check_tests_pass(tmp_path, monkeypatch):
    _fake_run(monkeypatch, 0, "5 passed")
    c = qg._check_tests(tmp_path)
    assert c.status == "pass" and c.required


def test_check_tests_fail(tmp_path, monkeypatch):
    _fake_run(monkeypatch, 1, "E\n1 failed in 0.1s")
    c = qg._check_tests(tmp_path)
    assert c.status == "fail" and c.fix_hint


def test_check_integrity_pass_and_fail(tmp_path, monkeypatch):
    _fake_run(monkeypatch, 0, "ok")
    assert qg._check_integrity(tmp_path).status == "pass"
    _fake_run(monkeypatch, 1, "bozuk")
    assert qg._check_integrity(tmp_path).status == "fail"


def test_check_ruff_variants(tmp_path, monkeypatch):
    monkeypatch.setattr(qg, "_has", lambda t: False)
    assert qg._check_ruff(tmp_path).status == "unavailable"
    monkeypatch.setattr(qg, "_has", lambda t: True)
    _fake_run(monkeypatch, 0, "")
    assert qg._check_ruff(tmp_path).status == "pass"
    _fake_run(monkeypatch, 1, "F401 unused")
    assert qg._check_ruff(tmp_path).status == "fail"


def test_check_bandit_variants(tmp_path, monkeypatch):
    monkeypatch.setattr(qg, "_has", lambda t: False)
    assert qg._check_bandit(tmp_path).status == "unavailable"
    monkeypatch.setattr(qg, "_has", lambda t: True)
    _fake_run(monkeypatch, 0, "")
    assert qg._check_bandit(tmp_path).status == "pass"
    _fake_run(monkeypatch, 1, "Issue: B105")
    assert qg._check_bandit(tmp_path).status == "fail"


def test_check_coverage_pass_and_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(qg, "_has", lambda t: True)
    monkeypatch.setattr(qg, "_run",
                        lambda cmd, cwd, timeout=900: (0, "TOTAL 1000 50 95%"))
    assert qg._check_coverage(tmp_path, 85).status == "pass"

    calls = {"n": 0}

    def two_step(cmd, cwd, timeout=900):
        calls["n"] += 1
        # 1. cagri: coverage run -> ok; 2. cagri: report --fail-under -> fail
        return (0, "") if calls["n"] == 1 else (2, "TOTAL 1000 300 70%")
    monkeypatch.setattr(qg, "_run", two_step)
    assert qg._check_coverage(tmp_path, 85).status == "fail"


def test_check_coverage_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(qg, "_has", lambda t: False)
    monkeypatch.setattr(qg, "_run",
                        lambda cmd, cwd, timeout=900: (127, "komut yok"))
    assert qg._check_coverage(tmp_path, 85).status == "unavailable"


def test_run_helper_missing_binary(tmp_path):
    rc, out = qg._run(["definitely-not-real-binary-xyz"], tmp_path, timeout=10)
    assert rc == 127


def test_to_dict_shape(tmp_path, monkeypatch):
    _patch_all(monkeypatch, {
        "tests": Check("tests", "pass", True),
        "coverage": Check("coverage", "pass", False),
        "lint": Check("lint", "pass", False),
        "security": Check("security", "pass", False),
        "integrity": Check("integrity", "pass", True),
    })
    d = run_gate(tmp_path).to_dict()
    assert set(d) == {"done", "summary", "checks", "warnings", "next_actions"}
    assert d["done"] is True
    assert len(d["checks"]) == 5
