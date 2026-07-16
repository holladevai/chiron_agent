# Otonom Uzmanlasan AI Agent Platformu

Bu depo, bir AI agent'in (Claude) karsilastigi her gorevde uzman prosedurleri
uygulamasini, eksik yeteneklerini fark etmesini, guvenilir kaynaklardan
skill/MCP/tool bulmasini, bunlari **sandbox'ta test ederek** ve **politika
kapilarindan gecirerek** kendi yetenek kutuphanesine kontrollu bicimde eklemesini
saglayan calisir bir sistemdir.

Tam tasarim gerekcesi: `otonom_uzmanlasan_ai_agent_skills_mcp_mimarisi.md`.

## Temel calisma kurali (HER gorevde)

1. **Once yetkinlik acigini olc.** Gorev yuksek riskli (finans/trading/guvenlik),
   belirsiz, ya da kullanici "en guncel/en iyi/dogrula" diyorsa, koda baslamadan
   once `capability-gap-analysis` skill'ini uygula ve:
   ```
   python -m core gap --domain <alan> --skills <id1,id2> --risk <seviye>
   ```
2. **Confidence'a gore yonlen:**
   - `proceed` -> mevcut skill'lerle yurut.
   - `proceed_with_verification` -> yurut, sonucu `evaluator` subagent'ina dogrulat.
   - `research_and_stage_capability` -> `capability-manager` subagent ile eksik
     yetenegi `secure-capability-acquisition` akisiyla edin.
3. **Sonucu kanitla.** "Bitti" demeden once evaluator/eval ile kanit uret.

## Token-verimli calisma (ponytail) ve ogrenme

Bu platform **az token** ilkesiyle calisir:

- **Minimalist muhendislik** ([[minimalist-engineering]], ponytail felsefesi):
  kod yazmadan / bagimlilik veya yetenek kurmadan once karar merdivenini uygula —
  "bu gercekten gerekli mi? zaten var mi? stdlib yeter mi?". Cogu zaman en iyi
  yetenek KURULMAYAN yetenektir. Guvenlik/dogrulama bundan MUAF (asla atlanmaz).
- **Deneyim hafizasi** ([[experience-memory]]): sistem deneyimden ogrenir ama
  context'i sismez. Ogrenme deterministik Python'da (SQLite) saklanir; LLM'e
  yalnizca goreve ilgili en fazla 5 kisa ders enjekte edilir:
  ```
  python -m core learn recall --domain <alan> --query "kelimeler" --k 5   # gorev basi
  python -m core learn add "KURAL" --domain <alan> --why "gerekce"        # gorev sonu (secici)
  ```
  Ders yalnizca genel + tekrar eden + kanitli oldugunda eklenir. Tekrar eden
  dersler (uses>=3) skill adayidir; ancak KANITLANMIS desenler kalici skill olur.

## Degismez guvenlik sinirlari (anayasal)

`policies/immutable-core.yaml` senin degistiremeyecegin sinirlari tanimlar.
`core/guard_hook.py` bunlari fiziksel olarak uygular (PreToolUse). Asla yapamazsin:
- Politika, guvenlik kurallari, audit log veya guard hook'u degistirmek
- `.claude/skills/` altina bir yetenegi tarama/eval/onaydan gecirmeden koymak
- Production'a yazmak, e-posta gondermek, canli trade acmak (hepsi insan onayi)
- Broker'dan para cekmek, agent'in kendi risk limitlerini degistirmek (yasak)

Politikayi yalnizca INSAN elle degistirir ve `python -m core seal-policy` ile muhurler.

## Yetenek edinme akisi (internetten bulunan hicbir sey dogrudan kurulmaz)

Iki serit var. Once kaynagin guvenilir olup olmadigina bak:

**A) Otomatik serit** — kaynak resmi org VEYA GitHub'da yuksek yildizli+bakimli repo
ise (bkz. [[auto-capability-acquisition]]). Insan onayi BEKLENMEZ ama uc kapi zorunlu:
```
capability-manager (aday+metadata) -> autoacquire-check (guven katmani)
  -> stage + statik tarama -> eval -> auto-security-reviewer (SONNET okur)
  -> autoacquire-promote (uc kapi gecerse OTOMATIK kurar; degilse insana duser)
```

**B) Standart serit** — bilinmeyen kaynak, yuksek risk veya tehlikeli izin
(bkz. [[secure-capability-acquisition]]):
```
kesif (capability-manager) -> stage + statik tarama -> security-gatekeeper
  -> eval (sandbox) -> promote (policy karari)
     - allow (dusuk risk)    -> otomatik kurulur
     - require_approval       -> approvals/pending/<id>.md -> INSAN approve eder
     - deny                   -> reddedilir
```

Otomatik serit yalnizca risk in {low, medium} ve tehlikeli izin YOK ise gecerli;
aksi halde immutable-core geregi insana gider (oauth/broker/high-risk).

## Dersten OTOMATIK skill uretimi (kendi kendine ogrenme -> kalici yetenek)

Tekrar eden ve dogrulanmis bir ders (uses>=3, net pozitif) otomatik skill olur:
```
python -m core learn promotion-candidates      # olgunlasan dersler
python -m core learn promote <ders-id>          # skill uret + tara + eval + kur
```
Uretilen skill dusuk riskliyse otomatik kurulur ve Claude Code onu ACIKLAMASINA
gore ihtiyac olunca otomatik cagirir. Web'den edinilip dogrulanan bilgiler de
once `learn add` ile kaydedilir, tekrar edip kanitlanınca ayni yolla skill olur.

## CLI komutlari

Agent'in serbestce kullanabilecegi (allowlist'te):
`gap, scan, list, search, stale, verify, report`

Yan etkili ama agent'in kullanabildigi: `stage, eval, promote, revoke, sandbox-run`

Yalnizca INSAN (guard hook agent'i engeller): `approve, seal-policy`

```
python -m core verify          # audit zinciri + politika butunlugu
python -m core list            # tum yetenekler
python -m core scan <dizin>    # aday statik guvenlik taramasi
```

## Alt-agent'lar (subagent)

- `capability-manager` — eksik yetenek arastirir, puanlar, staging'e hazirlar
- `security-gatekeeper` — aday'i kurulmadan once bagimsiz/dusmanca denetler
- `evaluator` — is sonucunu kanitla bagimsiz dogrular (isi yapan onaylayamaz)

Kural: yuksek riskli bir isi yapan/bulan agent, ayni isin nihai onaylayicisi olamaz.

## Dizinler

- `core/` — Python cekirdek (policy, scanner, registry, sandbox, evals, lifecycle)
- `policies/` — deny-by-default politikalar; `immutable-core.yaml` degistirilemez
- `.claude/skills/` — AKTIF (yuklu) skill'ler. Yalnizca burasi yuklenir.
- `staging/skills/` — test edilen adaylar (aktif degil)
- `registry/registry.db` — surumlu yetenek katalogu (SQLite)
- `evals/` — olculebilir dogrulama spec'leri
- `approvals/pending/` — insan onayi bekleyen paketler
- `audit/audit.jsonl` — hash-zincirli, degistirilemez denetim kaydi
- `sandbox/runs/` — izole calisma dizinleri

## Kurulum / dogrulama

```
python -m core init      # dizinler, muhur, seed skill kayitlari
python -m core verify    # her sey saglam mi
pytest -q                # cekirdek testleri
```
