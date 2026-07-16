"""Token-verimli kendi kendine ogrenme katmani.

Tasarim ilkesi (kullanicinin token kaygisina yanit):
  - Depolama ve geri cagirma TAMAMEN deterministik Python'dur -> 0 LLM token.
  - Ogrenme "ders" (lesson) biriktirir: her ders ~1-2 satir (kural + tetikleyici
    + gerekce). Transkript veya uzun metin SAKLANMAZ.
  - Geri cagirma leksikaldir (kelime ortusmesi); embedding API'si YOK, ek maliyet YOK.
  - Injection butcelidir: bir goreve en fazla k=5 ilgili ders, her biri kirpilmis
    olarak enjekte edilir. Tum dersler asla context'e yuklenmez (progressive disclosure).
  - Anti-bloat: benzer ders eklenince yenisi acilmaz, mevcut dersin sayaci artar.
  - Frekans kapisi: bir ders yalnizca TEKRAR ETTIGINDE (uses >= esik) ve net
    pozitifse skill adayi olur. Boylece her basari skill'e donusup context'i sismez.
  - C; ponytail felsefesi: "en iyi ders, yeni bir kural yazmadan cozulen istir."
    Ders eklemeden once "bu genel ve tekrar eden bir sey mi?" sorusu sorulur.

Ders yasam dongusu:
  candidate -> (tekrar + net pozitif) -> skill_candidate -> (skill-creator-safe) -> skill
  net negatif veya uzun sure kullanilmamis -> pruned
"""
from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

_WORD = re.compile(r"[a-z0-9]+")
STOP = {
    "the", "a", "an", "and", "or", "to", "of", "in", "for", "on", "is", "be",
    "ve", "ile", "bir", "bu", "icin", "de", "da", "mi", "ne", "cok",
}
MAX_RULE_LEN = 200
RECALL_K = 5
PROMOTE_MIN_USES = 3
PRUNE_UNUSED_DAYS = 120

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL DEFAULT '',
    trigger TEXT NOT NULL DEFAULT '',
    rule TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    keywords TEXT NOT NULL DEFAULT '',
    uses INTEGER NOT NULL DEFAULT 1,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'candidate',
    source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    last_used TEXT NOT NULL
);
"""


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if w not in STOP and len(w) > 2}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class Lesson:
    id: int
    domain: str
    trigger: str
    rule: str
    rationale: str
    uses: int
    wins: int
    losses: int
    status: str

    def render(self) -> str:
        """Injection icin kcompakt tek satir (token butcesi icin kirpik)."""
        base = f"[{self.domain or 'genel'}] {self.rule}"
        if self.rationale:
            base += f" — cunku {self.rationale}"
        return base[:MAX_RULE_LEN]


class LessonStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- ekleme (anti-bloat: benzer ders varsa birlestir) --------------
    def add(self, rule: str, *, domain: str = "", trigger: str = "",
            rationale: str = "", source: str = "",
            dedup_threshold: float = 0.6) -> dict:
        rule = rule.strip()[:MAX_RULE_LEN]
        if not rule:
            raise ValueError("bos ders")
        kw = _tokens(f"{rule} {trigger} {domain}")
        # benzer ders var mi?
        for row in self._conn.execute(
                "SELECT * FROM lessons WHERE domain=? OR domain=''", (domain,)).fetchall():
            existing_kw = set((row["keywords"] or "").split())
            if _jaccard(kw, existing_kw) >= dedup_threshold:
                self._conn.execute(
                    "UPDATE lessons SET uses=uses+1, last_used=? WHERE id=?",
                    (_now(), row["id"]))
                self._conn.commit()
                out = dict(self._conn.execute(
                    "SELECT * FROM lessons WHERE id=?", (row["id"],)).fetchone())
                out["merged"] = True
                return out
        cur = self._conn.execute(
            """INSERT INTO lessons (domain, trigger, rule, rationale, keywords,
                                    uses, status, source, created_at, last_used)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (domain, trigger, rule, rationale, " ".join(sorted(kw)),
             1, "candidate", source, _now(), _now()))
        self._conn.commit()
        out = dict(self._conn.execute(
            "SELECT * FROM lessons WHERE id=?", (cur.lastrowid,)).fetchone())
        out["merged"] = False
        return out

    # --- geri cagirma (leksikal, butceli) ------------------------------
    def recall(self, query: str = "", domain: str = "", k: int = RECALL_K) -> list[Lesson]:
        qkw = _tokens(f"{query} {domain}")
        scored = []
        for row in self._conn.execute(
                "SELECT * FROM lessons WHERE status != 'pruned'").fetchall():
            if row["losses"] > row["wins"] + 1:  # net negatif dersleri gosterme
                continue
            lkw = set((row["keywords"] or "").split())
            score = _jaccard(qkw, lkw) * 2.0
            if domain and row["domain"] == domain:
                score += 0.5
            score += 0.05 * min(row["uses"], 10)  # tekrar eden dersler hafif oncelikli
            if score > 0.1:
                scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for _, row in scored[:k]:
            self._conn.execute("UPDATE lessons SET last_used=? WHERE id=?",
                               (_now(), row["id"]))
            out.append(Lesson(row["id"], row["domain"], row["trigger"], row["rule"],
                              row["rationale"], row["uses"], row["wins"],
                              row["losses"], row["status"]))
        self._conn.commit()
        return out

    # --- pekistirme (win/loss geri bildirimi) --------------------------
    def reinforce(self, lesson_id: int, outcome: str) -> dict:
        col = {"win": "wins", "loss": "losses"}.get(outcome)
        if not col:
            raise ValueError("outcome: 'win' | 'loss'")
        self._conn.execute(
            f"UPDATE lessons SET {col}={col}+1, last_used=? WHERE id=?",
            (_now(), lesson_id))
        self._conn.commit()
        row = self._conn.execute("SELECT * FROM lessons WHERE id=?", (lesson_id,)).fetchone()
        if row is None:
            raise KeyError(lesson_id)
        # net cok negatifse otomatik budama
        if row["losses"] >= 3 and row["losses"] > row["wins"] * 2:
            self._conn.execute("UPDATE lessons SET status='pruned' WHERE id=?", (lesson_id,))
            self._conn.commit()
        return dict(self._conn.execute("SELECT * FROM lessons WHERE id=?", (lesson_id,)).fetchone())

    # --- skill terfi adaylari (frekans kapisi) -------------------------
    def promotion_candidates(self, min_uses: int = PROMOTE_MIN_USES) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM lessons WHERE status='candidate' AND uses >= ? "
            "AND wins >= losses ORDER BY uses DESC", (min_uses,)).fetchall()
        return [dict(r) for r in rows]

    def get(self, lesson_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM lessons WHERE id=?", (lesson_id,)).fetchone()
        return dict(row) if row else None

    def mark_status(self, lesson_id: int, status: str) -> None:
        if status not in ("candidate", "skill_candidate", "promoted", "pruned"):
            raise ValueError(status)
        self._conn.execute("UPDATE lessons SET status=? WHERE id=?", (status, lesson_id))
        self._conn.commit()

    # --- budama --------------------------------------------------------
    def prune(self, unused_days: int = PRUNE_UNUSED_DAYS) -> int:
        cutoff = time.time() - unused_days * 86400
        pruned = 0
        for row in self._conn.execute(
                "SELECT id, last_used, uses FROM lessons WHERE status='candidate'").fetchall():
            try:
                t = time.mktime(time.strptime(row["last_used"][:19], "%Y-%m-%dT%H:%M:%S"))
            except ValueError:
                t = 0
            if t < cutoff and row["uses"] <= 1:
                self._conn.execute("UPDATE lessons SET status='pruned' WHERE id=?", (row["id"],))
                pruned += 1
        self._conn.commit()
        return pruned

    def list(self, status: str | None = None) -> list[dict]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM lessons WHERE status=? ORDER BY uses DESC", (status,)).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM lessons ORDER BY uses DESC").fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        rows = self._conn.execute(
            "SELECT status, COUNT(*) c FROM lessons GROUP BY status").fetchall()
        return {r["status"]: r["c"] for r in rows}
