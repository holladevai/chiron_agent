"""Deterministik 'Definition of Done' kapisi — loop engineering'in durma kosulu.

Resmi loop rehberi (Anthropic) su ilkeyi vurgular: iyi bir loop, "kac test gecti
veya belli bir esigi asma gibi DETERMINISTIK kriterlerle" durmalidir; boylece
model "yeterince iyi mi" diye ozel bir karar vermez, kapi makine tarafindan
olculur. Bu modul o kapiyi tek yerde toplar:

  1) tests       — pytest (basarisiz test = done degil)
  2) coverage    — coverage.py, esik alti = done degil
  3) lint        — ruff (uyari = done degil)
  4) security    — bandit (kendi kaynagimiz)
  5) integrity   — python -m core verify (audit zinciri + politika muhru)

Araclar kurulu degilse ilgili kontrol "unavailable" olur: zorunlu kontroller
(tests, integrity) her zaman calisir; kalite kontrolleri (coverage/lint/security)
kuruluysa uygulanir, degilse uyari olarak raporlanir. `done`, calisabilen tum
kontrollerin gecmesi demektir.

Ciktisi yapisaldir: her kontrol icin gecti/kaldi + duzeltme ipucu; loop bir sonraki
turda neyi duzeltecegini bu ipuclarindan okur. Bu, "gormeyi/olcmeyi saglayan" geri
bildirim katmanidir (resmi rehber: verification'a olcum/etkilesim ekle).
"""
from __future__ import annotations

import shutil
import subprocess  # nosec B404 - kalite araclarini kontrollu, sabit komutlarla calistiririz
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_MIN_COVERAGE = 85


@dataclass
class Check:
    name: str
    status: str          # "pass" | "fail" | "unavailable"
    required: bool
    detail: str = ""
    fix_hint: str = ""

    @property
    def blocks(self) -> bool:
        # done'i engelleyen: kalan (fail). unavailable yalnizca zorunlu kontrolde engeller.
        if self.status == "fail":
            return True
        if self.status == "unavailable" and self.required:
            return True
        return False


@dataclass
class GateResult:
    done: bool
    checks: list[Check] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "done": self.done,
            "summary": self.summary(),
            "checks": [asdict(c) for c in self.checks],
            "warnings": self.warnings,
            "next_actions": self.next_actions,
        }

    def summary(self) -> str:
        p = sum(1 for c in self.checks if c.status == "pass")
        f = sum(1 for c in self.checks if c.status == "fail")
        u = sum(1 for c in self.checks if c.status == "unavailable")
        return f"{p} gecti, {f} kaldi, {u} yok -> {'DONE' if self.done else 'DEVAM'}"


def _run(cmd: list[str], cwd: Path, timeout: int = 900) -> tuple[int, str]:
    """Sabit bir komutu calistirir; (rc, birlesik cikti) dondurur."""
    try:
        proc = subprocess.run(  # nosec B603 - cmd sabit listeler; kullanici girdisi enterpole edilmez
            cmd, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, errors="replace",
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, f"zaman asimi ({timeout}s): {' '.join(cmd)}"
    except FileNotFoundError:
        return 127, f"komut yok: {cmd[0]}"


def _has(tool: str) -> bool:
    return shutil.which(tool) is not None


def _check_tests(root: Path) -> Check:
    rc, out = _run([sys.executable, "-m", "pytest", "-q"], root)
    if rc == 0:
        return Check("tests", "pass", True, "pytest tum testler gecti")
    tail = out.strip().splitlines()[-1] if out.strip() else "cikti yok"
    return Check("tests", "fail", True, tail,
                 "Basarisiz testleri duzelt: python -m pytest -q")


def _check_coverage(root: Path, min_cov: int) -> Check:
    if not _has("coverage") and shutil.which("python"):
        # coverage modul olarak kurulu olabilir; deneyerek anla
        rc_probe, _ = _run([sys.executable, "-m", "coverage", "--version"], root, timeout=60)
        if rc_probe != 0:
            return Check("coverage", "unavailable", False,
                         "coverage kurulu degil",
                         "pip install -e .[dev]")
    rc, _ = _run([sys.executable, "-m", "coverage", "run", "-m", "pytest", "-q"], root)
    if rc == 127:
        return Check("coverage", "unavailable", False, "coverage yok",
                     "pip install -e .[dev]")
    rc2, out = _run([sys.executable, "-m", "coverage", "report", f"--fail-under={min_cov}"], root, timeout=120)
    total = ""
    for line in out.splitlines():
        if line.startswith("TOTAL"):
            total = line.strip()
    if rc2 == 0:
        return Check("coverage", "pass", False, total or f">= %{min_cov}")
    return Check("coverage", "fail", False, total or f"esik %{min_cov} altinda",
                 f"Kapsami yukselt (yeni test ekle) veya esigi gozden gecir; hedef %{min_cov}")


def _check_ruff(root: Path) -> Check:
    if not _has("ruff"):
        return Check("lint", "unavailable", False, "ruff kurulu degil", "pip install -e .[dev]")
    rc, out = _run(["ruff", "check", "core", "tests", "scripts"], root, timeout=120)
    if rc == 0:
        return Check("lint", "pass", False, "ruff temiz")
    first = next((l for l in out.splitlines() if l.strip()), "ruff uyarilari")
    return Check("lint", "fail", False, first, "ruff check --fix core tests scripts")


def _check_bandit(root: Path) -> Check:
    if not _has("bandit"):
        return Check("security", "unavailable", False, "bandit kurulu degil", "pip install -e .[dev]")
    rc, out = _run(["bandit", "-c", "pyproject.toml", "-r", "core", "-q"], root, timeout=120)
    if rc == 0:
        return Check("security", "pass", False, "bandit temiz")
    return Check("security", "fail", False, "bandit bulgu(lar) uretti",
                 "Bulgulari incele; gercekse duzelt, yanlis-pozitifse pyproject skips gerekcelendir")


def _check_integrity(root: Path) -> Check:
    rc, out = _run([sys.executable, "-m", "core", "verify"], root, timeout=120)
    if rc == 0:
        return Check("integrity", "pass", True, "audit zinciri + politika muhru saglam")
    return Check("integrity", "fail", True, "butunluk dogrulanamadi",
                 "python -m core verify ciktisini incele")


CHECK_FUNCS = {
    "tests": lambda root, mc: _check_tests(root),
    "coverage": lambda root, mc: _check_coverage(root, mc),
    "lint": lambda root, mc: _check_ruff(root),
    "security": lambda root, mc: _check_bandit(root),
    "integrity": lambda root, mc: _check_integrity(root),
}


def run_gate(root: Path, *, min_coverage: int = DEFAULT_MIN_COVERAGE,
             skip: tuple[str, ...] = ()) -> GateResult:
    """Tum kapilari calistirir ve deterministik `done` karari uretir."""
    root = Path(root)
    checks: list[Check] = []
    for name, fn in CHECK_FUNCS.items():
        if name in skip:
            continue
        checks.append(fn(root, min_coverage))

    done = not any(c.blocks for c in checks)
    warnings = [f"{c.name}: {c.detail}" for c in checks if c.status == "unavailable"]
    next_actions = [f"[{c.name}] {c.fix_hint}" for c in checks if c.status == "fail" and c.fix_hint]
    return GateResult(done=done, checks=checks, warnings=warnings, next_actions=next_actions)
