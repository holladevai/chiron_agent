# Loop Engineering & NASA-grade Software Lifecycle

Chiron, bir AI agent'i "bir daha çalıştır, umarım geçer" seviyesinden **ölçülebilir,
katı bir yazılım ekibine** çıkarır. İki parça bunu sağlar:

1. **Deterministik Definition-of-Done kapısı** — `python -m core gate`
2. **Süreci kodlayan skill'ler** — `software-lifecycle` + `loop-engineering`
   (+ taze-bağlam `sw-reviewer` subagent)

Bu, resmi [Anthropic loop rehberinin](https://claude.com/blog/getting-started-with-loops)
temel ilkesini uygular: iyi bir loop **deterministik durma kriteriyle** (kaç test
geçti, eşik aşıldı mı) durur; model "yeterince iyi mi" diye karar vermez.

---

## 1. Deterministik durma koşulu: `core gate`

Loop mühendisliğinin kalbi, makine-doğrulamalı bir "bitti" tanımıdır. Tek komut
beş kapıyı ölçer ve `done: true/false` döner:

```bash
python -m core gate
```

| Kontrol | Ne ölçer | Zorunlu |
|---|---|---|
| `tests` | pytest tamamı geçti | ✅ |
| `coverage` | kapsam ≥ eşik (varsayılan %85) | opsiyonel* |
| `lint` | ruff temiz | opsiyonel* |
| `security` | bandit temiz (kendi kaynağımız) | opsiyonel* |
| `integrity` | audit zinciri + politika mührü sağlam | ✅ |

\* Araç kuruluysa uygulanır; **fail her zaman engeller**, yalnızca araç *yoksa*
uyarı olur. Zorunlu kontroller (tests, integrity) daima çalışır.

Çıktı `next_actions` alanında **sırada ne düzeltileceğini** söyler — loop bir
sonraki turda tam olarak bunu okur:

```json
{
  "done": false,
  "summary": "4 gecti, 1 kaldi, 0 yok -> DEVAM",
  "next_actions": ["[coverage] Kapsami yukselt (yeni test ekle); hedef %85"]
}
```

Seçenekler: `--min-coverage 90`, `--skip lint,security` (örn. hızlı iç döngü için).

---

## 2. Loop olarak sürme (goal-based)

En güçlü desen, döngüyü kapıya bağlamaktır:

```
/goal: `python -m core gate` "done: true" dönene kadar devam et.
Her tur: kapı çıktısındaki next_actions'ı oku; YALNIZCA o kontrolü düzelt; tekrar ölç.
Uygulamayı yazan, kendi kodunu onaylamaz — bağımsız review için sw-reviewer kullan.
```

Neden goal-based? Resmi rehber: doğrulanabilir çıkış kriteri olduğunda Claude
"yeterince iyi mi" kararı vermez, **kapı ölçer** ve loop erken/geç bitmez.

### Loop tipini işe göre seç
| İş | Loop tipi | Durma |
|---|---|---|
| Bir özelliği bitir | **`/goal`** | `core gate` → done |
| Kısa keşif/deneme | turn-based | Claude bitti der |
| Periyodik bakım (bağımlılık, triyaj) | `/loop`, `/schedule` | iptal / iş bitti |
| İnsansız rutin | proactive | rutin kapatılana kadar |

Ayrıntı: `loop-engineering` skill'i (kuruludur, açıklamasına göre otomatik çağrılır).

---

## 3. NASA-grade yaşamdöngüsü (plan → geliştir → test → review → doğrula)

`software-lifecycle` skill'i, bir uzman ekibin sürecini tek akışta birleştirir.
Çekirdek kural: **işi yapan, onu onaylayamaz** (görev-ayrılığı / IV&V).

```
Plan      → ölçülebilir kabul kriteri (gerekirse capability-gap-analysis)
Geliştir  → mevcut desenlere uy; test önce/birlikte; güvenlikten ödün yok
Test      → unit + integration + adversarial; bilinen boşluk xfail(strict)
Review    → TAZE bağlam: sw-reviewer subagent veya /code-review
Doğrula   → python -m core gate  (done: true olmadan "bitti" yok)
```

### Taze-bağlam review
Uygulamayı yazan ajan kendi kodunu inceleyemez. `sw-reviewer` subagent'ı diff'e
temiz bir gözle bakar (doğruluk, kenar durum, basitleştirme, güvenlik) ve kendi
ölçümünü (`core gate`) üretir. Bu, resmi rehberin "ikinci-ajan, taze bağlam"
ilkesidir.

---

## 4. Bu depo bunu kendi üstünde kanıtlar (dogfood)

`software-lifecycle` ve `loop-engineering` skill'leri **elle `.claude/skills/`
altına konmadı**; platformun kendi hattından geçirilerek kuruldu:

```
stage → statik tarama (100/pass) → sandbox eval (score 1.0) → promote (allow) → kuruldu
```

Yani platform, "güvenli yetenek edinme" akışını kendi yazılım-mühendisliği
yeteneklerini kurmak için kullandı — anayasal sınırlara (tarama/eval/politika)
sadık kalarak.

---

## Anti-desenler (kaçın)
- Kapı yeşil olmadan "bitti" demek.
- Kendi kodunu kendin onaylamak (bağımsız review atlanamaz).
- Belirsiz durma koşuluyla loop (token israfı + kalite düşüşü).
- Testi zayıflatarak kapıyı "geçmek" (kapıyı kandırma — kodu düzelt).
- Deterministik tek-seferlik işi loop'a sokmak (script yeter).
