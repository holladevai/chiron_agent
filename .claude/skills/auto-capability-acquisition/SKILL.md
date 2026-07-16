---
name: auto-capability-acquisition
description: Guvenilir kaynaklardan (resmi org veya GitHub'da yuksek yildizli, bakimli repo) gelen dusuk/orta riskli yetenekleri INSAN ONAYI BEKLEMEDEN otomatik edinir ve kurar; icerigi Sonnet ile okuyarak guvenlik denetiminden gecirir. Eksik yetenek tespit edildiginde ve aday guvenilir kaynaktan geliyorsa bu otomatik hat kullanilir.
version: 1.0.0
risk_level: medium
---

# Auto Capability Acquisition (guvenilir kaynak = otomatik)

Bu skill, [[secure-capability-acquisition]] akisinin OTOMATIK seridir. Fark:
guvenilir kaynaktan gelen adaylar icin insan onayi beklenmez — ama UC bagimsiz
guvenlik kapisi yine de zorunludur.

## Ne zaman otomatik, ne zaman insan?

**Otomatik (insan onayi YOK):** aday su kosullari saglıyorsa
- Kaynak resmi/guvenilir org (anthropics, modelcontextprotocol, microsoft,
  trailofbits, github, ...) VEYA GitHub yildizi esigin ustunde (varsayilan >=800)
- Repo bakimli (son push < ~18 ay) ve lisans uygun (MIT/Apache/BSD/...)
- Risk dusuk veya orta
- Tehlikeli izin YOK (oauth, broker, production_write, genis dosya sistemi,
  secret export, email, prod db, main'e push)

**Insan onayi (otomatik DEGIL):** yukaridakilerden biri saglanmiyorsa — bilinmeyen
kaynak, dusuk yildiz, bakimsiz, yuksek risk veya tehlikeli izin. Aday kaybolmaz;
onay paketine duser.

## Otomatik akis

1. **Aday + metadata topla.** `capability-manager` subagent adayi bulur ve su
   metadata'yi cikarir (JSON):
   ```json
   {"id": "...", "source_url": "...", "org": "...", "stars": 0,
    "pushed_days_ago": 0, "license": "MIT", "risk_level": "low", "permissions": []}
   ```

2. **Kapi 1 — guven katmani:**
   ```
   python -m core autoacquire-check <id> --meta-file <metadata.json>
   ```
   `eligible=false` ise otomatik durur -> insan onayi. `true` ise devam.

3. **Staging + Kapi 2 — deterministik tarama:**
   ```
   python -m core stage <dizin> --id <id> --risk <low|medium> --source <url>
   python -m core eval <id>
   ```
   Kritik bulgu = otomatik red. Eval >= 0.90 gerekli.

4. **Kapi 3 — Sonnet icerik incelemesi:** `auto-security-reviewer` subagent'ini
   cagir (Sonnet modeliyle calisir). Dosyalari okur, JSON verdikt dondurur ve
   bir dosyaya yazar.

5. **Otomatik kurulum (uc kapi da gecerse):**
   ```
   python -m core autoacquire-promote <id> --meta-file <metadata.json> \
       --review-file <sonnet-verdict.json>
   ```
   - Uc kapi gecti -> otomatik kurulur, audit'e tam koken (kaynak, yildiz, lisans,
     tarama skoru, Sonnet verdikti) yazilir.
   - Herhangi biri gecmezse -> otomatik kurulmaz, `approvals/pending/` altina
     insan onay paketi duser.

## Neden guvenli?

- Guven katmani tek basina yeterli DEGILDIR; tarama + Sonnet okumasi da sart.
- Deterministik tarama LLM'e degil regex'e dayanir; dis saldiri onu atlayamaz.
- Yuksek/kritik risk ve tehlikeli izinler guven katmaninda elenir; sealed
  immutable-core zaten oauth/broker/high-risk kurulumu insana baglar.
- Isi bulan (capability-manager) ile denetleyen (auto-security-reviewer) ayridir.

## Kaynaklar

- Motor: core/autoacquire.py, core/lifecycle.py (auto_promote)
- Ilgili: [[secure-capability-acquisition]], [[mcp-security-review]],
  [[capability-gap-analysis]], [[minimalist-engineering]]
