"""Ajan kurulum betigi — INSAN calistirir (Claude degil).

Neden insan? guard_hook.py ve settings.json anayasal olarak korunur; agent onlari
degistiremez. Bu betik kullanicinin KENDI terminalinde calisir, orada guard hook
devrede degildir. Iki is yapar (ikisi de idempotent):

  1) guard_hook.py'deki '2>&1' false-positive'ini duzeltir: stderr/null yonlendirmeleri
     artik "dosya degistirme" sayilmaz; yalnizca gercek mutasyonlar bloklanir.
  2) Aktivasyon hook'larini (SessionStart + UserPromptSubmit) kalici olarak
     settings.json'a ekler (portable, versiyonlanabilir). Boylece settings.local.json'a
     gerek kalmaz.

Kullanim:
    python scripts/setup_ajan.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# --- 1) guard_hook 2>&1 yamasi -------------------------------------------------
SCRUB_FUNC = '''def _scrub_redirects(command: str) -> str:
    """stderr/stdout birlestirme ve null yonlendirmeleri mutasyon DEGILDIR."""
    s = re.sub(r"\\d*>\\s*&\\s*\\d+", " ", command)          # 2>&1, 1>&2
    s = re.sub(r"\\d*>\\s*\\$null", " ", s, flags=re.I)       # 2>$null
    s = re.sub(r"\\d*>\\s*/dev/null", " ", s)               # 2>/dev/null
    s = re.sub(r"\\d*>\\s*nul\\b", " ", s, flags=re.I)        # 2>nul (cmd)
    return s


'''


def patch_guard() -> str:
    f = ROOT / "core" / "guard_hook.py"
    text = f.read_text(encoding="utf-8")
    if "_scrub_redirects" in text:
        return "guard_hook: zaten yamali"

    # (a) yardimci fonksiyonu command_touches_protected'ten once ekle
    anchor = "def command_touches_protected("
    if anchor not in text:
        return "guard_hook: beklenen fonksiyon bulunamadi, elle kontrol gerekli"
    text = text.replace(anchor, SCRUB_FUNC + anchor, 1)

    # (b) mutasyon kontrolunu scrubbed komut uzerinde yap
    text = text.replace(
        "if basename in c and MUTATION_HINTS.search(command):",
        "if basename in c and MUTATION_HINTS.search(_scrub_redirects(command)):",
        1)

    f.write_text(text, encoding="utf-8")
    return "guard_hook: yama uygulandi (2>&1 false-positive giderildi)"


# --- 2) aktivasyon hook'larini settings.json'a tasi ---------------------------
ACTIVATION_HOOKS = {
    "SessionStart": [{"hooks": [{"type": "command",
                                 "command": "python -m core session-start"}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command",
                                     "command": "python -m core on-prompt"}]}],
}


def install_hooks() -> str:
    f = ROOT / ".claude" / "settings.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    hooks = data.setdefault("hooks", {})
    changed = False
    for event, spec in ACTIVATION_HOOKS.items():
        existing = json.dumps(hooks.get(event, []))
        if "core session-start" in existing or "core on-prompt" in existing:
            continue
        hooks.setdefault(event, [])
        hooks[event].extend(spec)
        changed = True
    if not changed:
        return "settings.json: aktivasyon hook'lari zaten kurulu"
    f.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # settings.local.json'daki gecici kopyayi temizle (cift tetikleme olmasin)
    local = ROOT / ".claude" / "settings.local.json"
    if local.exists():
        try:
            ld = json.loads(local.read_text(encoding="utf-8"))
            if "hooks" in ld:
                del ld["hooks"]
            if ld:
                local.write_text(json.dumps(ld, indent=2) + "\n", encoding="utf-8")
            else:
                local.unlink()
        except Exception:
            pass
    return "settings.json: aktivasyon hook'lari kalici olarak eklendi"


def main() -> None:
    print("=== Ajan kurulumu ===")
    print(" -", patch_guard())
    print(" -", install_hooks())
    print("\nSonraki adim: Claude Code'u bu klasorde YENIDEN baslat (hook'lar oturum")
    print("basinda yuklenir). Ardindan sistem otomatik devrede olur.")
    print("Komutlar: \"ajan devreye gir\" (ac) / \"is bitti\" (kapat).")


if __name__ == "__main__":
    main()
