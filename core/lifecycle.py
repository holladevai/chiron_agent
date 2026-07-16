"""Capability Acquisition Pipeline orkestrasyonu.

Akis (vizyon dokumani bolum 11 ve 28'in calisan hali):

  stage(aday)     : staging/skills/<id> altina alinir + statik tarama
                    kritik bulgu -> reddedilir ve kaydi 'revoked' olur
  evaluate(id)    : eval suite sandbox'ta calisir -> sandbox-validated
  promote(id)     : policy karari
                    - allow            -> .claude/skills/<id> tasinir (aktif)
                    - require_approval -> approvals/pending/<id>.md onay paketi
                    - deny             -> reddedilir
  approve(id)     : YALNIZCA insan calistirir (CLI interaktif onay ister)
  revoke(id)      : aktif skill registry/revoked/ altina tasinir

Onemli: staging'deki hicbir skill Claude Code tarafindan yuklenmez;
yalnizca .claude/skills/ altindakiler aktiftir. Terfi = fiziksel tasima.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from .audit import AuditLog
from . import autoacquire
from .confidence import assess
from .evals import run_eval
from .paths import Paths
from .policy import ALLOW, DENY, REQUIRE_APPROVAL, PolicyEngine
from .registry import Registry, dir_content_hash
from .scanner import scan_path


class Pipeline:
    def __init__(self, paths: Paths | None = None):
        self.paths = paths or Paths()
        self.paths.ensure()
        self.audit = AuditLog(self.paths.audit_log)
        self.policy = PolicyEngine(self.paths)
        self.registry = Registry(self.paths.registry_db)

    # ------------------------------------------------------------------
    def stage(self, source_dir: Path, capability_id: str | None = None, *,
              risk_level: str = "medium", domains: list[str] | None = None,
              source: str = "", version: str = "0.1.0") -> dict:
        """Adayi staging'e alir, tarar, registry'ye experimental yazar."""
        source_dir = Path(source_dir)
        cid = capability_id or source_dir.name
        scan = scan_path(source_dir)

        decision = self.policy.decide(
            "stage_capability", risk_level,
            {"security_scan_passed": scan.verdict in ("pass", "review")},
        )
        result = {
            "capability": cid,
            "scan": scan.to_dict(),
            "decision": decision.effect,
            "reason": decision.reason,
        }
        if decision.effect != ALLOW:
            self.registry.add(cid, version, status="revoked", risk_level=risk_level,
                              domains=domains, source=source, scan_score=scan.score,
                              notes=f"staging reddedildi: {decision.reason}; verdict={scan.verdict}")
            self.audit.append("pipeline", "stage_rejected",
                              {"capability": cid, "verdict": scan.verdict,
                               "findings": len(scan.findings)})
            result["staged"] = False
            return result

        target = self.paths.staging_skills / cid
        if source_dir.resolve() != target.resolve():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source_dir, target)
        self.registry.add(
            cid, version, status="experimental", risk_level=risk_level,
            domains=domains, source=source, path=str(target),
            content_hash=dir_content_hash(target), scan_score=scan.score,
        )
        self.audit.append("pipeline", "staged",
                          {"capability": cid, "scan_score": scan.score,
                           "verdict": scan.verdict})
        result["staged"] = True
        result["path"] = str(target)
        return result

    # ------------------------------------------------------------------
    def evaluate(self, capability_id: str) -> dict:
        """Eval suite calistirir; gecerse sandbox-validated."""
        row = self.registry.latest(capability_id)
        if row is None:
            raise KeyError(f"registry'de yok: {capability_id}")
        skill_dir = Path(row["path"]) if row["path"] else self.paths.staging_skills / capability_id
        if not skill_dir.exists():
            raise FileNotFoundError(f"skill dizini yok: {skill_dir}")

        # icerik degisti mi? (tedarik zinciri kontrolu)
        current_hash = dir_content_hash(skill_dir)
        if row["content_hash"] and current_hash != row["content_hash"]:
            self.audit.append("pipeline", "content_hash_mismatch",
                              {"capability": capability_id})
            return {"capability": capability_id, "passed": False,
                    "error": "icerik hash'i degismis: yeniden stage edilmeli"}

        ev = run_eval(capability_id, skill_dir,
                      evals_dir=self.paths.evals_dir,
                      runs_dir=self.paths.sandbox_runs)
        if ev.passed:
            self.registry.set_status(capability_id, "sandbox-validated")
        self.registry.set_validation(capability_id, ev.score)
        self.audit.append("pipeline", "evaluated",
                          {"capability": capability_id, "score": ev.score,
                           "passed": ev.passed,
                           "critical_failures": ev.critical_failures})
        return ev.to_dict()

    # ------------------------------------------------------------------
    def promote(self, capability_id: str) -> dict:
        """Policy karari verir; allow ise aktif skill dizinine tasir."""
        row = self.registry.latest(capability_id)
        if row is None:
            raise KeyError(f"registry'de yok: {capability_id}")

        context = {
            "security_scan_passed": (row["scan_score"] or 0) >= 70,
            "sandbox_eval_passed": row["status"] == "sandbox-validated"
                                   and (row["validation_score"] or 0) >= 0.9,
        }
        decision = self.policy.decide("install_capability", row["risk_level"], context)
        out = {"capability": capability_id, "decision": decision.effect,
               "reason": decision.reason, "rule": decision.rule_id,
               "missing_conditions": decision.missing_conditions}

        if decision.effect == ALLOW:
            self._install(row)
            out["installed"] = True
        elif decision.effect == REQUIRE_APPROVAL:
            pkg = self._write_approval_package(row, decision.missing_conditions)
            out["approval_package"] = str(pkg)
            out["installed"] = False
        else:
            out["installed"] = False
        self.audit.append("pipeline", "promote_decision",
                          {"capability": capability_id, "decision": decision.effect,
                           "reason": decision.reason})
        return out

    # ------------------------------------------------------------------
    def auto_promote(self, capability_id: str, meta: dict,
                     review_verdict: str, review_summary: str = "") -> dict:
        """Guvenilir kaynak icin INSAN ONAYI BEKLEMEDEN otomatik kurulum.

        UC kapinin HEPSI gecmeden kurmaz:
          1) Guven katmani (autoacquire.evaluate): resmi org veya yildiz esigi +
             lisans/tazelik/risk-tavani/izin kontrolu
          2) Deterministik tarayici: taze re-scan, kritik yok + skor >= esik
          3) Sonnet icerik incelemesi: review_verdict == 'approve'

        Herhangi biri gecmezse otomatik kurmaz; insan onay paketi olusturur.
        Yuksek/kritik risk ve tehlikeli izinler guven katmaninda zaten elenir.
        """
        row = self.registry.latest(capability_id)
        if row is None:
            raise KeyError(f"registry'de yok: {capability_id}")

        trust = autoacquire.load_trust(self.paths)
        cand = autoacquire.Candidate.from_dict({**meta, "id": capability_id,
                                                "risk_level": row["risk_level"]})
        decision = autoacquire.evaluate(cand, trust)

        out = {"capability": capability_id, "tier": decision.tier,
               "trust_reasons": decision.reasons, "auto_installed": False}

        # --- Kapi 1: guven katmani ---
        if not decision.eligible:
            out["gate_failed"] = "trust"
            out["reason"] = "guven katmani gecilemedi -> insan onayi"
            self._to_human(row, decision.reasons)
            out["approval_package"] = str(self.paths.approvals_pending / f"{capability_id}.md")
            self.audit.append("autoacquire", "auto_denied_trust",
                              {"capability": capability_id, "tier": decision.tier,
                               "reasons": decision.reasons})
            return out

        # --- Kapi 2: taze deterministik tarama ---
        skill_dir = Path(row["path"]) if row["path"] else self.paths.staging_skills / capability_id
        scan = scan_path(skill_dir)
        if scan.has_critical or scan.score < trust["min_scan_score"]:
            out["gate_failed"] = "scanner"
            out["scan"] = {"score": scan.score, "verdict": scan.verdict}
            out["reason"] = f"tarama kapisi: verdict={scan.verdict} skor={scan.score}"
            self.registry.set_status(capability_id, "revoked")
            self.audit.append("autoacquire", "auto_denied_scan",
                              {"capability": capability_id, "score": scan.score,
                               "verdict": scan.verdict})
            return out

        # --- eval gecmis olmali ---
        if row["status"] != "sandbox-validated" or (row["validation_score"] or 0) < 0.9:
            out["gate_failed"] = "eval"
            out["reason"] = "sandbox eval gecilmemis (once python -m core eval)"
            self.audit.append("autoacquire", "auto_blocked_eval",
                              {"capability": capability_id, "status": row["status"]})
            return out

        # --- Kapi 3: Sonnet icerik incelemesi ---
        if (review_verdict or "").lower() != "approve":
            out["gate_failed"] = "sonnet_review"
            out["reason"] = f"Sonnet incelemesi onaylamadi: verdict={review_verdict}"
            self._to_human(row, [f"Sonnet review: {review_verdict} — {review_summary}"])
            out["approval_package"] = str(self.paths.approvals_pending / f"{capability_id}.md")
            self.audit.append("autoacquire", "auto_denied_review",
                              {"capability": capability_id, "verdict": review_verdict,
                               "summary": review_summary[:200]})
            return out

        # --- Uc kapi da gecti: otomatik kur ---
        self._install(row)
        out["auto_installed"] = True
        out["reason"] = "uc kapi gecti (guven + tarama + Sonnet) -> otomatik kuruldu"
        self.audit.append("autoacquire", "auto_installed", {
            "capability": capability_id, "tier": decision.tier,
            "source_url": meta.get("source_url", ""), "org": cand.org,
            "stars": cand.stars, "license": cand.license,
            "risk_level": row["risk_level"], "scan_score": scan.score,
            "sonnet_verdict": review_verdict, "sonnet_summary": review_summary[:200],
        })
        return out

    def _to_human(self, row: dict, extra_reasons: list[str]) -> None:
        self._write_approval_package(row, extra_reasons)

    # ------------------------------------------------------------------
    def approve(self, capability_id: str, approver: str, *, confirmed: bool) -> dict:
        """Insan onayi. CLI bu fonksiyonu interaktif dogrulamadan sonra cagirir.

        confirmed=False ile cagrilirsa hicbir sey yapmaz (fail-closed).
        """
        if not confirmed:
            return {"capability": capability_id, "installed": False,
                    "error": "onay dogrulanmadi"}
        row = self.registry.latest(capability_id)
        if row is None:
            raise KeyError(f"registry'de yok: {capability_id}")
        if row["status"] not in ("sandbox-validated",):
            return {"capability": capability_id, "installed": False,
                    "error": f"onaylanamaz: durum '{row['status']}', "
                             "once eval gecmeli (sandbox-validated)"}
        self._install(row)
        pending = self.paths.approvals_pending / f"{capability_id}.md"
        if pending.exists():
            decided = self.paths.approvals_decided / f"{capability_id}-{time.strftime('%Y%m%d-%H%M%S')}.md"
            shutil.move(str(pending), str(decided))
        self.audit.append(approver, "human_approved", {"capability": capability_id})
        return {"capability": capability_id, "installed": True, "approver": approver}

    # ------------------------------------------------------------------
    def revoke(self, capability_id: str, reason: str = "") -> dict:
        row = self.registry.latest(capability_id)
        if row is None:
            raise KeyError(f"registry'de yok: {capability_id}")
        active = self.paths.active_skills / capability_id
        if active.exists():
            dest = self.paths.revoked_dir / f"{capability_id}-{time.strftime('%Y%m%d-%H%M%S')}"
            shutil.move(str(active), str(dest))
        self.registry.set_status(capability_id, "revoked")
        self.audit.append("pipeline", "revoked",
                          {"capability": capability_id, "reason": reason})
        return {"capability": capability_id, "revoked": True, "reason": reason}

    # ------------------------------------------------------------------
    def gap(self, domain: str, required_skills: list[str],
            risk_level: str = "medium") -> dict:
        report = assess(self.registry, domain=domain,
                        required_skills=required_skills, risk_level=risk_level)
        self.audit.append("pipeline", "gap_assessed",
                          {"domain": domain, "confidence": report.confidence,
                           "action": report.action, "missing": report.missing})
        return report.to_dict()

    # ------------------------------------------------------------------
    def _install(self, row: dict) -> None:
        cid = row["id"]
        src = Path(row["path"]) if row["path"] else self.paths.staging_skills / cid
        dest = self.paths.active_skills / cid
        if src.exists() and src.resolve() != dest.resolve():
            if dest.exists():
                # eski surumu geri alinabilir sekilde sakla
                backup = self.paths.revoked_dir / f"{cid}-replaced-{time.strftime('%Y%m%d-%H%M%S')}"
                shutil.move(str(dest), str(backup))
            shutil.move(str(src), str(dest))
        self.registry.add(
            cid, row["version"], type=row["type"],
            domains=json.loads(row["domains"] or "[]"),
            status="project-approved", risk_level=row["risk_level"],
            source=row["source"], path=str(dest),
            content_hash=dir_content_hash(dest) if dest.exists() else row["content_hash"],
            validation_score=row["validation_score"], scan_score=row["scan_score"],
            notes=row["notes"],
        )
        self.audit.append("pipeline", "installed", {"capability": cid})

    def _write_approval_package(self, row: dict, missing: list[str]) -> Path:
        cid = row["id"]
        pkg = self.paths.approvals_pending / f"{cid}.md"
        domains = ", ".join(json.loads(row["domains"] or "[]")) or "-"
        content = f"""# Onay Paketi: {cid}

## Eklenmek istenen kabiliyet
`{cid}` v{row['version']} ({row['type']})

## Alanlar
{domains}

## Kaynak
{row['source'] or 'belirtilmemis'}

## Risk seviyesi
{row['risk_level']}

## Test sonuclari
- Statik tarama skoru: {row['scan_score']}/100
- Eval skoru: {row['validation_score']:.2f} (esik: 0.90)
- Durum: {row['status']}
- Eksik kosullar: {', '.join(missing) or 'yok'}

## Onaylamak icin (yalnizca insan, interaktif terminalde)
```
python -m core approve {cid} --by "AD SOYAD"
```

## Reddetmek icin
```
python -m core revoke {cid} --reason "gerekce"
```
"""
        pkg.write_text(content, encoding="utf-8")
        return pkg

    def close(self) -> None:
        self.registry.close()
