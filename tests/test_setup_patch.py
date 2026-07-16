"""setup_ajan.py guard yamasinin mantigini izole dogrular.

guard_hook.py'yi degistirmeden, yamanin uyguladigi _scrub_redirects davranisini
ve command_touches_protected sonucunu gecici bir kopyada test eder.
"""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_guard(tmp_path, patched: bool):
    src = (ROOT / "core" / "guard_hook.py").read_text(encoding="utf-8")
    if patched:
        # setup_ajan.py ile ayni yamayi uygula
        spec = importlib.util.spec_from_file_location(
            "setup_ajan", ROOT / "scripts" / "setup_ajan.py")
        setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup)
        src = src.replace("def command_touches_protected(",
                          setup.SCRUB_FUNC + "def command_touches_protected(", 1)
        src = src.replace(
            "if basename in c and MUTATION_HINTS.search(command):",
            "if basename in c and MUTATION_HINTS.search(_scrub_redirects(command)):", 1)
    f = tmp_path / ("guard_p.py" if patched else "guard_u.py")
    f.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f.stem, f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_unpatched_false_positive(tmp_path):
    g = _load_guard(tmp_path, patched=False)
    prot = ["policies/immutable-core.sha256"]
    # 2>&1 iceren SALT-OKUMA komut -> yamasiz hatali sekilde bloklanir
    cmd = "python -m core verify 2>&1 | Select-String immutable-core.sha256"
    assert g.command_touches_protected(cmd, prot) is not None


def test_patched_allows_readonly_redirect(tmp_path):
    g = _load_guard(tmp_path, patched=True)
    prot = ["policies/immutable-core.sha256"]
    cmd = "python -m core verify 2>&1 | Select-String immutable-core.sha256"
    # yama sonrasi: 2>&1 mutasyon sayilmaz -> bloklanmaz
    assert g.command_touches_protected(cmd, prot) is None


def test_patched_still_blocks_real_mutation(tmp_path):
    g = _load_guard(tmp_path, patched=True)
    prot = ["policies/immutable-core.sha256"]
    # gercek yazma yonlendirmesi hala bloklanmali
    assert g.command_touches_protected("echo x > policies/immutable-core.sha256", prot) is not None
    assert g.command_touches_protected("rm policies/immutable-core.sha256", prot) is not None
    assert g.command_touches_protected(
        "Remove-Item policies/immutable-core.sha256 -Force", prot) is not None
