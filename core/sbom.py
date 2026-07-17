"""SBOM (Software Bill of Materials) — vizyon dokumani Bolum 23 / Faz 5.

Platformun "neyden olustugunu" tek, denetlenebilir envanterde toplar: calisma-zamani
bagimliliklari + KURULU yetenekler (id, surum, kaynak, risk, icerik hash'i, tarama
skoru, lisans). Tedarik zinciri seffafligi ve olay incelemesi icin. Salt-okuma.

Not: tam CycloneDX/SPDX imzali release Faz 5 hedefidir; bu, ayni bilgiyi minimal,
bagimliliksiz (stdlib) bir JSON envanteri olarak uretir.
"""
from __future__ import annotations

from pathlib import Path

from .paths import Paths
from .policy import file_sha256
from .registry import Registry


def _read_requirements(root: Path) -> list[dict]:
    req = root / "requirements.txt"
    out: list[dict] = []
    if not req.exists():
        return out
    for line in req.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # "PyYAML>=6.0" -> ad + kisit
        for sep in (">=", "==", "<=", "~=", ">", "<"):
            if sep in line:
                name, _, ver = line.partition(sep)
                out.append({"name": name.strip(), "constraint": f"{sep}{ver.strip()}",
                            "type": "python-dependency"})
                break
        else:
            out.append({"name": line, "constraint": "", "type": "python-dependency"})
    return out


def build_sbom(paths: Paths | None = None) -> dict:
    paths = paths or Paths()
    reg = Registry(paths.registry_db)
    try:
        rows = reg.list()
    finally:
        reg.close()

    # yalnizca kurulmus/aktif olanlar SBOM'a girer (staging/revoked haric)
    installed = [r for r in rows
                 if r["status"] in {"project-approved", "production-approved", "deprecated"}]
    capabilities = [{
        "id": r["id"],
        "version": r["version"],
        "type": r["type"],
        "status": r["status"],
        "risk_level": r["risk_level"],
        "source": r["source"] or "",
        "content_hash": r["content_hash"] or "",
        "scan_score": r["scan_score"],
        "validation_score": r["validation_score"],
        "license": r.get("license") if isinstance(r, dict) else None,
    } for r in installed]

    seal = ""
    if paths.immutable_seal.exists():
        seal = paths.immutable_seal.read_text(encoding="utf-8").strip()[:64]

    integrity = ""
    if paths.immutable_core.exists():
        integrity = file_sha256(paths.immutable_core)[:16]

    return {
        "format": "chiron-sbom/1",
        "root": str(paths.root),
        "dependencies": _read_requirements(paths.root),
        "capabilities": capabilities,
        "capability_count": len(capabilities),
        "policy": {
            "immutable_core_sha256_prefix": integrity,
            "sealed": bool(seal),
        },
    }
