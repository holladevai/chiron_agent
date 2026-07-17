---
name: software-lifecycle
description: NASA-seviyesi yazilim yasamdongusu prosedürü — plan, gelistir, test, bagimsiz review, dogrula. Herhangi bir kod/ozellik/duzeltme uzerinde calisirken; "profesyonelce yap", "eksiksiz", "test et", "uretim kalitesi" istendiginde; ya da bir loop icinde kod uretirken uygulanir. Deterministik bir Definition-of-Done kapisiyla biter (python -m core gate), belirsiz "yeterince iyi" karari vermez.
version: 1.0.0
risk_level: low
---

# Software Lifecycle (NASA-grade)

"Bir daha calistir, umarim gecer" yerine kati, kanitli bir yasamdongusu. Bir
uzman yazilim ekibinin (planlayici, gelistirici, test muhendisi, bagimsiz
inceleyici, dogrulayici) tek bir akista birlestirilmis halidir. Amac: her
degisikligin OLCULEBILIR bicimde "bitti" oldugunu kanitlamak.

## Cekirdek ilke: gorev-ayriligi ve olcum

- Isi YAPAN, ayni isin nihai ONAYLAYICISI olamaz. Uygulamayi yazan ajan, kendi
  kodunun bagimsiz incelemesini yapamaz — taze-baglamli bir inceleyici (bkz.
  `sw-reviewer` subagent veya `/code-review`) veya `evaluator` subagent gerekir.
- "Bitti" bir his degil, bir olcumdur. Nihai kapi makine tarafindan denetlenir:
  `python -m core gate`.

## Asamalar

### 1) Plan (koda dokunmadan once)
- Gereksinimi tek cumlede yaz: "Basari su OLCULEBILIR kosul saglaninca gerceklesir."
- Kabul kriterlerini deterministik ifade et: hangi testler gececek, hangi
  davranis dogrulanacak, kapsam esigi ne.
- Yuksek riskli/belirsizse once `capability-gap-analysis` uygula.
- Degisiklik yuzeyini kucuk ve tek konulu tut (ponytail: gereksiz kod yazma).

### 2) Gelistir
- Var olan desenlere ve kod stiline uy; cevredeki kodu taklit et.
- Her davranis degisikligi icin TEST once/birlikte yazilir (test-driven yaklasim).
- Guvenlik, hata yonetimi ve girdi dogrulamasindan asla odun verme.
- Anayasal korumali dosyalari (policy/guard/audit cekirdegi) degistirme; yalnizca
  oneri uret.

### 3) Test (cok katmanli)
- Unit + integration + mutlu-yol DISI (adversarial/negatif) vakalar.
- Guvenlik-kritik kod icin: atlatma denemeleri, sinir kosullari, kurcalama.
- Bilinen bosluklari gizleme; `xfail(strict)` ile isaretle ki gelisince uyarsin.

### 4) Bagimsiz review (taze baglam)
- Uygulayanin disinda bir goz: `sw-reviewer` subagent veya `/code-review`.
- Inceleyici dogrulugu, basitlestirmeyi, yeniden-kullanimi ve kenar durumlari arar.
- Bulgular duzeltildikten sonra tekrar kapiya donulur.

### 5) Dogrula (deterministik Definition-of-Done kapisi)
```
python -m core gate
```
Kapi su bes kontrolu makineyle olcer ve `done: true/false` doner:
1. tests — pytest tamami gecti
2. coverage — kapsam esik ustunde (varsayilan %85)
3. lint — ruff temiz
4. security — bandit temiz (kendi kaynagimiz)
5. integrity — audit zinciri + politika muhru saglam

`done` false ise cikti `next_actions` listesinde SIRADA ne duzeltilecegini soyler.

## Loop olarak surme (loop engineering ile)

Bu yasamdongusu bir dongude en guclu halini alir. Durma kosulu belirsiz birakma;
kapiya bagla:

```
/goal: python -m core gate "done: true" donene kadar devam et.
Her turda: kalan kontrolu oku (next_actions), yalnizca onu duzelt, tekrar olc.
```

Ayrintili loop tasarimi (dogru loop tipi, token yonetimi, taze-baglam review)
icin `loop-engineering` skill'ine bak. Anahtar kural: durma kosulu DETERMINISTIK
olmali (gate ciktisi), model "yeterince iyi mi" diye karar vermemeli.

## Anti-desenler
- Kapi yesil olmadan "bitti" demek.
- Kendi kodunu kendin onaylamak (bagimsiz review atlanamaz).
- Belirsiz durma kosuluyla loop kurmak (token israfi + kalite dususu).
- Testleri gecirmek icin testi zayiflatmak (gate'i kandirmak degil, kodu duzelt).
