"""Platform CLI: python -m core <komut>

Agent'in kullandigi komutlar:
  gap, scan, stage, eval, promote, revoke, list, search, stale, verify,
  report, sandbox-run

Yalnizca INSAN kullanir (guard hook agent'i engeller):
  approve, seal-policy
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .audit import AuditLog
from .learning import LessonStore
from .lifecycle import Pipeline
from .paths import Paths
from .policy import PolicyEngine
from .registry import dir_content_hash
from .scanner import scan_path
from . import sandbox as sbx


def _print(data) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(json.dumps(data, indent=2, ensure_ascii=True, default=str))


def cmd_init(args, paths: Paths) -> int:
    paths.ensure()
    policy = PolicyEngine(paths)
    if not paths.immutable_seal.exists():
        digest = policy.seal()
        print(f"immutable-core muhurlendi: {digest[:16]}...")
    ok, msg = policy.verify_integrity()
    print(f"politika butunlugu: {msg}")

    pipe = Pipeline(paths)
    pipe.audit.append("human", "platform_init", {"root": str(paths.root)})

    # Aktif dizindeki seed skill'leri registry'ye kaydet (guvenilir kabul edilir,
    # cunku insan tarafindan kurulumla birlikte gelmistir)
    seeded = []
    for d in sorted(paths.active_skills.iterdir()) if paths.active_skills.exists() else []:
        if not d.is_dir() or not (d / "SKILL.md").exists():
            continue
        scan = scan_path(d)
        pipe.registry.add(
            d.name, "1.0.0", status="project-approved", risk_level="low",
            source="seed", path=str(d), content_hash=dir_content_hash(d),
            scan_score=scan.score, validation_score=1.0,
            notes="platform kurulumuyla gelen seed skill",
        )
        pipe.registry.set_validation(d.name, 1.0)
        seeded.append(f"{d.name} (tarama: {scan.score}/100)")
    pipe.audit.append("human", "seeds_registered", {"skills": seeded})
    pipe.close()
    print(f"seed skill kaydi: {len(seeded)}")
    for s in seeded:
        print(f"  - {s}")
    print("platform hazir.")
    return 0


def cmd_ajan(args, paths: Paths) -> int:
    from . import activate
    if args.state == "on":
        activate.set_active(paths, True)
        _print({"ajan": "active"})
    elif args.state == "off":
        activate.set_active(paths, False)
        _print({"ajan": "inactive"})
    else:
        _print({"ajan": "active" if activate.is_active(paths) else "inactive"})
    return 0


def cmd_seal(args, paths: Paths) -> int:
    digest = PolicyEngine(paths).seal()
    AuditLog(paths.audit_log).append("human", "policy_sealed", {"sha256": digest})
    print(f"yeni muhur: {digest}")
    return 0


def cmd_gap(args, paths: Paths) -> int:
    pipe = Pipeline(paths)
    report = pipe.gap(args.domain, [s.strip() for s in args.skills.split(",") if s.strip()],
                      args.risk)
    pipe.close()
    _print(report)
    return 0


def cmd_scan(args, paths: Paths) -> int:
    result = scan_path(Path(args.path))
    _print(result.to_dict())
    return 0 if result.verdict in ("pass", "review") else 1


def cmd_stage(args, paths: Paths) -> int:
    pipe = Pipeline(paths)
    result = pipe.stage(
        Path(args.path), args.id,
        risk_level=args.risk,
        domains=[d.strip() for d in (args.domains or "").split(",") if d.strip()],
        source=args.source or "", version=args.version,
    )
    pipe.close()
    _print(result)
    return 0 if result.get("staged") else 1


def cmd_eval(args, paths: Paths) -> int:
    pipe = Pipeline(paths)
    result = pipe.evaluate(args.id)
    pipe.close()
    _print(result)
    return 0 if result.get("passed") else 1


def cmd_promote(args, paths: Paths) -> int:
    pipe = Pipeline(paths)
    result = pipe.promote(args.id)
    pipe.close()
    _print(result)
    return 0 if result.get("decision") != "deny" else 1


def cmd_approve(args, paths: Paths) -> int:
    # Insan-only: interaktif teyit ister. Claude'un non-interaktif kabugu
    # stdin'e cevap veremeyecegi icin dogal olarak basarisiz olur;
    # ayrica guard hook bu komutu agent icin zaten engeller.
    if not sys.stdin.isatty():
        print("HATA: approve yalnizca interaktif terminalde calisir (insan onayi).",
              file=sys.stderr)
        return 2
    print(f"'{args.id}' yetenegi kalici olarak kurulacak.")
    answer = input("Onayliyor musunuz? (evet/hayir): ").strip().lower()
    if answer not in ("evet", "e", "yes", "y"):
        print("iptal edildi.")
        return 1
    pipe = Pipeline(paths)
    result = pipe.approve(args.id, args.by, confirmed=True)
    pipe.close()
    _print(result)
    return 0 if result.get("installed") else 1


def cmd_revoke(args, paths: Paths) -> int:
    pipe = Pipeline(paths)
    result = pipe.revoke(args.id, args.reason or "")
    pipe.close()
    _print(result)
    return 0


def cmd_list(args, paths: Paths) -> int:
    pipe = Pipeline(paths)
    rows = pipe.registry.list(args.status)
    pipe.close()
    _print([{k: r[k] for k in ("id", "version", "type", "status", "risk_level",
                               "validation_score", "scan_score", "last_validated_at")}
            for r in rows])
    return 0


def cmd_search(args, paths: Paths) -> int:
    pipe = Pipeline(paths)
    rows = pipe.registry.search(args.query or "", args.domain or "",
                                active_only=args.active)
    pipe.close()
    _print([{k: r[k] for k in ("id", "version", "status", "risk_level",
                               "validation_score")} for r in rows])
    return 0


def cmd_stale(args, paths: Paths) -> int:
    pipe = Pipeline(paths)
    rows = pipe.registry.stale(args.days)
    pipe.close()
    _print([{"id": r["id"], "version": r["version"],
             "last_validated_at": r["last_validated_at"]} for r in rows])
    return 0


def cmd_verify(args, paths: Paths) -> int:
    audit_ok, audit_msg = AuditLog(paths.audit_log).verify()
    policy_ok, policy_msg = PolicyEngine(paths).verify_integrity()
    _print({"audit": {"ok": audit_ok, "message": audit_msg},
            "policy": {"ok": policy_ok, "message": policy_msg}})
    return 0 if (audit_ok and policy_ok) else 1


def cmd_report(args, paths: Paths) -> int:
    pipe = Pipeline(paths)
    row = pipe.registry.latest(args.id)
    pipe.close()
    if row is None:
        print(f"kayit yok: {args.id}", file=sys.stderr)
        return 1
    _print(row)
    return 0


def cmd_sandbox_run(args, paths: Paths) -> int:
    if args.cmd and args.cmd[0] == "--":
        args.cmd = args.cmd[1:]
    if not args.cmd:
        print("HATA: calistirilacak komut verilmedi", file=sys.stderr)
        return 2
    result = sbx.run(args.cmd, runs_dir=paths.sandbox_runs,
                     cwd=Path(args.cwd) if args.cwd else None,
                     timeout=args.timeout, network=args.network)
    AuditLog(paths.audit_log).append(
        "sandbox", "run", {"cmd": args.cmd, "exit": result.exit_code,
                           "network": args.network, "timed_out": result.timed_out})
    _print(result.to_dict())
    return 0 if result.ok else 1


def _ensure_ready(paths: Paths) -> None:
    """Idempotent otomatik kurulum: muhur + dizinler + seed kayitlari."""
    paths.ensure()
    policy = PolicyEngine(paths)
    if not paths.immutable_seal.exists():
        policy.seal()
    pipe = Pipeline(paths)
    try:
        for d in sorted(paths.active_skills.iterdir()) if paths.active_skills.exists() else []:
            if not d.is_dir() or not (d / "SKILL.md").exists():
                continue
            if pipe.registry.latest(d.name) is None:
                scan = scan_path(d)
                pipe.registry.add(d.name, "1.0.0", status="project-approved",
                                  risk_level="low", source="seed", path=str(d),
                                  content_hash=dir_content_hash(d), scan_score=scan.score,
                                  validation_score=1.0, notes="seed")
                pipe.registry.set_validation(d.name, 1.0)
    finally:
        pipe.close()


def cmd_session_start(args, paths: Paths) -> int:
    from . import activate
    try:
        _ensure_ready(paths)
        if activate.is_active(paths):
            ok, _ = PolicyEngine(paths).verify_integrity()
            banner = "" if ok else "[UYARI] politika butunlugu dogrulanamadi (fail-closed).\n"
            print(banner + activate.PROTOCOL)
        # pasifse cikti yok (sessiz)
    except Exception:
        pass
    return 0


def cmd_on_prompt(args, paths: Paths) -> int:
    from . import activate
    try:
        raw = sys.stdin.buffer.read()
        payload = json.loads(raw.decode("utf-8-sig", errors="replace") or "{}")
        prompt = payload.get("prompt") or payload.get("user_prompt") or ""
        action = activate.classify(prompt)
        if action == "engage":
            activate.set_active(paths, True)
            AuditLog(paths.audit_log).append("human", "ajan_engaged", {})
            print(activate.PROTOCOL)
        elif action == "disengage":
            activate.set_active(paths, False)
            AuditLog(paths.audit_log).append("human", "ajan_disengaged", {})
            print(activate.DISENGAGED_NOTE)
        # tetikleyici yoksa cikti yok (0 token)
    except Exception:
        pass
    return 0


def _load_meta(args) -> dict:
    if args.meta_file:
        return json.loads(Path(args.meta_file).read_text(encoding="utf-8"))
    if args.meta:
        return json.loads(args.meta)
    return {}


def cmd_autoacquire_check(args, paths: Paths) -> int:
    from .autoacquire import Candidate, evaluate, load_trust
    meta = _load_meta(args)
    meta.setdefault("id", args.id or meta.get("id", ""))
    trust = load_trust(paths)
    decision = evaluate(Candidate.from_dict(meta), trust)
    _print(decision.to_dict())
    return 0 if decision.eligible else 1


def cmd_autoacquire_promote(args, paths: Paths) -> int:
    pipe = Pipeline(paths)
    meta = _load_meta(args)
    summary = args.review_summary or ""
    if args.review_file:
        rv = json.loads(Path(args.review_file).read_text(encoding="utf-8"))
        verdict = str(rv.get("verdict", "")).lower()
        summary = rv.get("summary", summary)
    else:
        verdict = (args.review_verdict or "").lower()
    result = pipe.auto_promote(args.id, meta, verdict, summary)
    pipe.close()
    _print(result)
    return 0 if result.get("auto_installed") else 1


def _learn_promote(args, paths: Paths, store, audit) -> int:
    """Dogrulanmis, tekrar eden bir dersi OTOMATIK skill'e donusturur.

    Kapilar: ders uses >= min ve net pozitif olmali; uretilen skill statik tarama
    ve eval'den gecmeli; dusuk riskli oldugu icin politika otomatik kurar. Kurulunca
    Claude Code onu aciklamasina gore otomatik kullanir.
    """
    from .skillgen import generate_skill_dir
    lesson = store.get(args.id)
    if lesson is None:
        print(f"ders yok: {args.id}", file=sys.stderr)
        return 1
    if not args.force:
        if lesson["uses"] < args.min_uses:
            _print({"promoted": False,
                    "reason": f"ders yeterince tekrar etmedi (uses={lesson['uses']} "
                              f"< {args.min_uses}); --force ile zorlanabilir"})
            return 1
        if lesson["losses"] > lesson["wins"]:
            _print({"promoted": False,
                    "reason": f"ders net negatif (wins={lesson['wins']} "
                              f"losses={lesson['losses']})"})
            return 1

    skill_dir, skill_id = generate_skill_dir(lesson, paths.staging_skills)
    pipe = Pipeline(paths)
    try:
        st = pipe.stage(skill_dir, skill_id, risk_level="low",
                        domains=[lesson["domain"]] if lesson["domain"] else [],
                        source=f"learned-lesson:{lesson['id']}")
        if not st.get("staged"):
            _print({"promoted": False, "gate": "scan", "detail": st})
            return 1
        ev = pipe.evaluate(skill_id)
        if not ev.get("passed"):
            _print({"promoted": False, "gate": "eval", "detail": ev})
            return 1
        pr = pipe.promote(skill_id)
        installed = pr.get("installed", False)
        if installed:
            store.mark_status(args.id, "promoted")
        audit.append("learning", "lesson_promoted_to_skill",
                     {"lesson_id": args.id, "skill": skill_id,
                      "installed": installed, "decision": pr.get("decision")})
        _print({"promoted": installed, "skill": skill_id,
                "decision": pr.get("decision"),
                "auto_used": "kurulunca Claude Code aciklamasina gore otomatik cagirir"
                             if installed else None,
                "detail": pr})
        return 0 if installed else 1
    finally:
        pipe.close()


def cmd_learn(args, paths: Paths) -> int:
    store = LessonStore(paths.lessons_db)
    audit = AuditLog(paths.audit_log)
    try:
        if args.learn_cmd == "add":
            res = store.add(args.rule, domain=args.domain or "",
                            trigger=args.trigger or "", rationale=args.why or "",
                            source=args.source or "task")
            audit.append("learning", "lesson_added",
                         {"id": res["id"], "merged": res["merged"],
                          "uses": res["uses"]})
            _print({"id": res["id"], "merged": res["merged"], "uses": res["uses"],
                    "note": "birlestirildi (anti-bloat)" if res["merged"] else "yeni ders"})
        elif args.learn_cmd == "recall":
            lessons = store.recall(args.query or "", args.domain or "", args.k)
            _print({"count": len(lessons),
                    "lessons": [{"id": l.id, "text": l.render(),
                                 "uses": l.uses} for l in lessons]})
        elif args.learn_cmd == "reinforce":
            res = store.reinforce(args.id, args.outcome)
            _print({"id": res["id"], "wins": res["wins"], "losses": res["losses"],
                    "status": res["status"]})
        elif args.learn_cmd == "promotion-candidates":
            cands = store.promotion_candidates(args.min_uses)
            _print([{"id": c["id"], "rule": c["rule"], "domain": c["domain"],
                     "uses": c["uses"], "wins": c["wins"]} for c in cands])
        elif args.learn_cmd == "list":
            _print([{"id": r["id"], "domain": r["domain"], "rule": r["rule"],
                     "uses": r["uses"], "wins": r["wins"], "losses": r["losses"],
                     "status": r["status"]} for r in store.list(args.status)])
        elif args.learn_cmd == "prune":
            n = store.prune(args.days)
            audit.append("learning", "pruned", {"count": n})
            _print({"pruned": n})
        elif args.learn_cmd == "promote":
            return _learn_promote(args, paths, store, audit)
        elif args.learn_cmd == "stats":
            _print(store.stats())
        else:
            print("bilinmeyen learn komutu", file=sys.stderr)
            return 2
        return 0
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m core",
                                     description="Otonom yetenek platformu CLI")
    parser.add_argument("--root", default=None, help="platform kok dizini (test icin)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="platformu baslat (dizinler, muhur, seed kayitlari)")
    sub.add_parser("seal-policy", help="[INSAN] immutable-core degisikligini muhurle")
    sub.add_parser("session-start", help="[HOOK] oturum baslangici: auto-init + protokol")
    sub.add_parser("on-prompt", help="[HOOK] prompt'ta 'ajan devreye gir' / 'is bitti' yakala")
    p = sub.add_parser("ajan", help="ajan durumunu ac/kapa/goster")
    p.add_argument("state", choices=["on", "off", "status"])

    p = sub.add_parser("gap", help="yetkinlik acigi ve guven skoru raporu")
    p.add_argument("--domain", required=True)
    p.add_argument("--skills", required=True, help="virgullu skill id listesi")
    p.add_argument("--risk", default="medium",
                   choices=["low", "medium", "high", "critical"])

    p = sub.add_parser("scan", help="aday skill/tool statik guvenlik taramasi")
    p.add_argument("path")

    p = sub.add_parser("stage", help="adayi staging'e al (tarama + kayit)")
    p.add_argument("path")
    p.add_argument("--id", default=None)
    p.add_argument("--risk", default="medium",
                   choices=["low", "medium", "high", "critical"])
    p.add_argument("--domains", default="")
    p.add_argument("--source", default="")
    p.add_argument("--version", default="0.1.0")

    p = sub.add_parser("eval", help="sandbox eval calistir")
    p.add_argument("id")

    p = sub.add_parser("promote", help="politika karariyla kuruluma tasi")
    p.add_argument("id")

    p = sub.add_parser("approve", help="[INSAN] bekleyen onayi uygula")
    p.add_argument("id")
    p.add_argument("--by", required=True, help="onaylayan kisi")

    p = sub.add_parser("revoke", help="yetenegi iptal et / geri al")
    p.add_argument("id")
    p.add_argument("--reason", default="")

    p = sub.add_parser("list", help="registry kayitlari")
    p.add_argument("--status", default=None)

    p = sub.add_parser("search", help="registry'de ara")
    p.add_argument("--query", default="")
    p.add_argument("--domain", default="")
    p.add_argument("--active", action="store_true")

    p = sub.add_parser("stale", help="yeniden dogrulama bekleyenler")
    p.add_argument("--days", type=int, default=90)

    sub.add_parser("verify", help="audit zinciri + politika butunlugu dogrula")

    p = sub.add_parser("report", help="tek yetenegin tam kaydi")
    p.add_argument("id")

    p = sub.add_parser("sandbox-run", help="komutu izole sandbox'ta calistir")
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--network", action="store_true")
    p.add_argument("--cwd", default=None)
    p.add_argument("cmd", nargs=argparse.REMAINDER)

    # --- otomatik edinme (guvenilir kaynak) ---
    ac = sub.add_parser("autoacquire-check",
                        help="aday otomatik kuruluma uygun mu (guven katmani)")
    ac.add_argument("id")
    ac.add_argument("--meta", default="", help="JSON metadata string")
    ac.add_argument("--meta-file", default="", help="JSON metadata dosyasi")
    ap2 = sub.add_parser("autoacquire-promote",
                         help="uc kapiyi (guven+tarama+Sonnet) gecirip otomatik kur")
    ap2.add_argument("id")
    ap2.add_argument("--meta", default="", help="JSON metadata string")
    ap2.add_argument("--meta-file", default="", help="JSON metadata dosyasi")
    ap2.add_argument("--review-verdict", default="", choices=["", "approve", "reject"],
                     help="Sonnet inceleme sonucu")
    ap2.add_argument("--review-file", default="", help="Sonnet inceleme JSON dosyasi")
    ap2.add_argument("--review-summary", default="")

    # --- ogrenme (token-verimli) ---
    lp = sub.add_parser("learn", help="kendi kendine ogrenme: ders defteri")
    lsub = lp.add_subparsers(dest="learn_cmd", required=True)
    la = lsub.add_parser("add", help="kisa ders ekle (tekrar edeni birlestirir)")
    la.add_argument("rule", help="1-2 cumlelik kural")
    la.add_argument("--domain", default="")
    la.add_argument("--trigger", default="", help="ne zaman gecerli")
    la.add_argument("--why", default="", help="gerekce")
    la.add_argument("--source", default="task")
    lr = lsub.add_parser("recall", help="goreve ilgili en fazla k ders getir")
    lr.add_argument("--query", default="")
    lr.add_argument("--domain", default="")
    lr.add_argument("--k", type=int, default=5)
    lf = lsub.add_parser("reinforce", help="dersi pekistir (win/loss)")
    lf.add_argument("id", type=int)
    lf.add_argument("outcome", choices=["win", "loss"])
    lpc = lsub.add_parser("promotion-candidates", help="skill'e terfi adaylari")
    lpc.add_argument("--min-uses", type=int, default=3)
    ll = lsub.add_parser("list", help="dersleri listele")
    ll.add_argument("--status", default=None)
    lpr = lsub.add_parser("prune", help="kullanilmayan dersleri buda")
    lpr.add_argument("--days", type=int, default=120)
    lsub.add_parser("stats", help="ders istatistikleri")
    lpm = lsub.add_parser("promote",
                          help="dogrulanmis dersi OTOMATIK skill'e donustur (tara+eval+kur)")
    lpm.add_argument("id", type=int)
    lpm.add_argument("--min-uses", type=int, default=3)
    lpm.add_argument("--force", action="store_true",
                     help="uses/net-pozitif kapilarini atla (dikkatli)")

    args = parser.parse_args(argv)
    paths = Paths(Path(args.root).resolve()) if args.root else Paths()

    handlers = {
        "init": cmd_init, "seal-policy": cmd_seal, "gap": cmd_gap,
        "scan": cmd_scan, "stage": cmd_stage, "eval": cmd_eval,
        "promote": cmd_promote, "approve": cmd_approve, "revoke": cmd_revoke,
        "list": cmd_list, "search": cmd_search, "stale": cmd_stale,
        "verify": cmd_verify, "report": cmd_report,
        "sandbox-run": cmd_sandbox_run, "learn": cmd_learn,
        "autoacquire-check": cmd_autoacquire_check,
        "autoacquire-promote": cmd_autoacquire_promote,
        "session-start": cmd_session_start, "on-prompt": cmd_on_prompt,
        "ajan": cmd_ajan,
    }
    return handlers[args.command](args, paths)


if __name__ == "__main__":
    sys.exit(main())
