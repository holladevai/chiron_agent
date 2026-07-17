"""Danisma kurulu — Claude takildiginda diger modellerden fikir/ikinci gorus alir.

Ana beyin Claude'dur. Bu modul, zor/cozulmeyen bir islem icin problemi env'de
anahtari MEVCUT olan DIGER saglayicilara paralel dagitir, fikirleri toplar ve
Claude'un sentezlemesi icin geri dondurur. Bu bir "her turda" mekanizmasi degildir;
YALNIZCA gerektiginde (tekrarlayan hata, zor tasarim karari, "en iyi yaklasim")
cagirilir (bkz. ai-council skill).

Zarif bozulma: hic ek saglayici yoksa bos sonuc doner ve Claude tek basina yurur.
Bir saglayici hata verirse (timeout/limit/5xx) o atlanir; digerleri etkilenmez.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field

from . import providers as prov

DEFAULT_SYSTEM = (
    "Sen bir uzman danismansin. Baska bir AI (Claude) bir problemde takildi ve "
    "senden FIKIR/ikinci gorus istiyor. Kisa, somut, uygulanabilir bir oneri ver; "
    "varsa alternatif yaklasim ve dikkat edilecek tuzaklari belirt. Kod gerekiyorsa "
    "minimal ornek ver. Gereksiz uzatma."
)


@dataclass
class Opinion:
    provider: str
    model: str
    ok: bool
    answer: str = ""
    error: str = ""


@dataclass
class CouncilResult:
    question: str
    providers_used: list[str] = field(default_factory=list)
    opinions: list[Opinion] = field(default_factory=list)
    skipped_no_providers: bool = False
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "providers_used": self.providers_used,
            "opinions": [asdict(o) for o in self.opinions],
            "skipped_no_providers": self.skipped_no_providers,
            "note": self.note,
        }


def _ask(p: prov.Provider, question: str, context: str, system: str,
         max_tokens: int, timeout: int) -> Opinion:
    prompt = question if not context else f"BAGLAM:\n{context}\n\nSORU:\n{question}"
    try:
        text = prov.complete(p, prompt, system=system, max_tokens=max_tokens, timeout=timeout)
        if not text:
            return Opinion(p.name, p.model, False, error="bos yanit")
        return Opinion(p.name, p.model, True, answer=text)
    except Exception as e:  # noqa: BLE001 - bir saglayici hatasi digerlerini etkilemesin
        return Opinion(p.name, p.model, False, error=f"{type(e).__name__}: {e}")


def consult(question: str, *, context: str = "", exclude: tuple[str, ...] = ("anthropic",),
            providers: list[str] | None = None, system: str = DEFAULT_SYSTEM,
            max_tokens: int = 1024, timeout: int = 60,
            env: dict | None = None) -> CouncilResult:
    """Zor problemi mevcut diger saglayicilara dagitir; fikirleri toplar.

    exclude: varsayilan olarak 'anthropic' haric (soruyu soran zaten Claude).
    providers: verilirse yalnizca bu isimler kullanilir (yine env'de anahtari
               olanlarla kesisir).
    """
    avail = prov.available_providers(env)
    chosen = [p for p in avail if p.name not in exclude]
    if providers:
        want = set(providers)
        chosen = [p for p in chosen if p.name in want]

    if not chosen:
        return CouncilResult(
            question=question, skipped_no_providers=True,
            note=("Ek saglayici anahtari yok (veya haric tutuldu). "
                  "Claude tek basina devam etmeli. Anahtar eklemek icin ilgili "
                  "ortam degiskenini ayarla (or. OPENAI_API_KEY, GEMINI_API_KEY)."),
        )

    opinions: list[Opinion] = []
    with ThreadPoolExecutor(max_workers=min(5, len(chosen))) as ex:
        futs = {ex.submit(_ask, p, question, context, system, max_tokens, timeout): p
                for p in chosen}
        for fut in as_completed(futs):
            opinions.append(fut.result())

    # deterministik siralama (isim) — cikti tekrar uretilebilir olsun
    opinions.sort(key=lambda o: o.provider)
    ok_names = [o.provider for o in opinions if o.ok]
    note = f"{len(ok_names)}/{len(chosen)} saglayici fikir verdi."
    return CouncilResult(question=question, providers_used=ok_names,
                         opinions=opinions, note=note)
