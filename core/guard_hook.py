"""Claude Code PreToolUse guard hook — anayasal sinirin fiziksel uygulanmasi.

Claude'un su girisimlerini engeller (exit 2 -> tool cagrisi bloklanir):
  1) Korunan dosyalara Write/Edit/NotebookEdit
  2) Bash/PowerShell ile korunan dosyalari degistiren komutlar
  3) Insan-only CLI komutlari: `core approve`, `core seal-policy`

Kullanici (insan) politika duzenlemek isterse dosyayi kendisi elle duzenler
veya AJAN_GUARD_BYPASS=1 ortam degiskenini kendi terminalinde ayarlar.

Bu dosyanin kendisi de korunan yollar listesindedir.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# immutable-core.yaml okunamazsa devreye giren sabit yedek liste (fail-safe)
FALLBACK_PROTECTED = [
    "policies/immutable-core.yaml",
    "policies/immutable-core.sha256",
    "policies/permissions.yaml",
    "policies/trading.yaml",
    "audit/audit.jsonl",
    "core/guard_hook.py",
    "core/policy.py",
    "core/audit.py",
    ".claude/settings.json",
]

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}

MUTATION_HINTS = re.compile(
    r"(>>?|\brm\b|\bdel\b|\bmv\b|\bmove\b|\bcp\b|\bcopy\b|remove-item|set-content|"
    r"out-file|add-content|clear-content|\btee\b|sed\s+-i|truncate|new-item)",
    re.IGNORECASE,
)
HUMAN_ONLY = re.compile(r"-m\s+core(\.\w+)?\s+(approve|seal-policy)\b|core[/\\]__main__\.py\s+(approve|seal-policy)\b",
                        re.IGNORECASE)


def load_protected() -> list[str]:
    try:
        import yaml  # type: ignore
        doc = yaml.safe_load((ROOT / "policies" / "immutable-core.yaml").read_text(encoding="utf-8"))
        paths = doc.get("protected_paths") or []
        return list(set(paths) | set(FALLBACK_PROTECTED))
    except Exception:
        return FALLBACK_PROTECTED


def norm(p: str) -> str:
    return p.replace("\\", "/").lower()


def is_protected_file(file_path: str, protected: list[str]) -> str | None:
    fp = norm(file_path)
    try:
        fp = norm(str(Path(file_path).resolve()))
    except OSError:
        pass
    for entry in protected:
        e = norm(entry).rstrip("/")
        if entry.rstrip().endswith(("/", "\\")):
            # dizin korumasi (or. audit/): yol icinde dizin gecer mi
            if f"/{e}/" in f"/{fp}/":
                return entry
        elif fp == e or fp.endswith("/" + e):
            return entry
    return None


def _scrub_redirects(command: str) -> str:
    """stderr/stdout birlestirme ve null yonlendirmeleri mutasyon DEGILDIR."""
    s = re.sub(r"\d*>\s*&\s*\d+", " ", command)          # 2>&1, 1>&2
    s = re.sub(r"\d*>\s*\$null", " ", s, flags=re.I)       # 2>$null
    s = re.sub(r"\d*>\s*/dev/null", " ", s)               # 2>/dev/null
    s = re.sub(r"\d*>\s*nul\b", " ", s, flags=re.I)        # 2>nul (cmd)
    return s


def command_touches_protected(command: str, protected: list[str]) -> str | None:
    c = norm(command)
    for entry in protected:
        e = norm(entry).rstrip("/")
        basename = e.rsplit("/", 1)[-1]
        if basename in c and MUTATION_HINTS.search(_scrub_redirects(command)):
            return entry
    return None


def block(message: str) -> None:
    sys.stderr.write(
        f"[GUARD] Engellendi: {message}\n"
        "Bu islem anayasal sinir (immutable-core) kapsamindadir. "
        "Degisiklik yalnizca insan tarafindan elle yapilabilir; "
        "agent yalnizca degisiklik ONERISI sunabilir.\n"
    )
    _audit_block(message)
    sys.exit(2)


def _audit_block(message: str) -> None:
    try:
        sys.path.insert(0, str(ROOT))
        from core.audit import AuditLog
        AuditLog(ROOT / "audit" / "audit.jsonl").append(
            "guard_hook", "blocked", {"reason": message})
    except Exception:
        pass


def main() -> None:
    if os.environ.get("AJAN_GUARD_BYPASS") == "1":
        sys.exit(0)
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    protected = load_protected()

    if tool in WRITE_TOOLS:
        fp = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if fp:
            hit = is_protected_file(fp, protected)
            if hit:
                block(f"korunan dosyaya yazma girisimi: {hit}")

    if tool in SHELL_TOOLS:
        cmd = tool_input.get("command", "") or ""
        if HUMAN_ONLY.search(cmd):
            block("insan-only komut (approve / seal-policy) agent tarafindan calistirilamaz")
        hit = command_touches_protected(cmd, protected)
        if hit:
            block(f"shell komutu korunan dosyayi degistiriyor: {hit}")

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # hook'un kendi hatasi tum araclari kilitlemesin (kontrollu fail-open);
        # kritik koruma zaten policy engine + insan-only CLI tarafinda da var
        sys.exit(0)
