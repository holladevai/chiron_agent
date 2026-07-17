---
name: loop-engineering
description: Bir ajan dongusunu (loop) dogru tasarlama proseduru — dogru loop tipini sec, DETERMINISTIK durma kosulu tanimla, taze-baglam dogrulama ekle, token'i yonet. Bir gorevi tekrar eden turlarla yurutmek, "X olana kadar devam et" istemek, periyodik/otomatik is kurmak ya da bir sonucu istenen olcuye getirene kadar iterasyon yapmak gerektiginde uygulanir.
version: 1.0.0
risk_level: low
---

# Loop Engineering

Bir loop, "durma kosulu saglanana kadar tekrarlanan is turleri"dir. Iyi loop
muhendisligi = dogru tetikleyici + DETERMINISTIK durma + olculebilir dogrulama.
Kotu loop = belirsiz durma kosulu (token israfi, kalite dususu) veya deterministik
bir isi loop'a sokmak (script yeter).

## Once karar: bu is gercekten loop mu?
En basit cozumden basla. Tek seferlik/deterministik is icin loop kurma — duz
komut veya script yeter. Loop, tekrar + olculebilir hedef oldugunda degerlidir.

## Dort loop tipi (tetikleyici / durma / kullanim)

1. **Turn-based** — kullanici komutuyla; Claude "bitti" deyince veya baglam
   gerektiginde durur. Kisa, kesif isleri. Dogrulamayi bir SKILL.md'ye kodlayarak
   Claude'un kendi isini uctan uca kontrol etmesini saglarsin.
2. **Goal-based (`/goal`)** — hedef saglanana VEYA azami tur limitine kadar.
   Dogrulanabilir cikis kriteri olan isler icin en iyisi; Claude "yeterince iyi mi"
   karari vermez, kapi olcer.
3. **Time-based (`/loop`, `/schedule`)** — belirli araliklarla; kullanici iptaline
   veya is bitene kadar. Periyodik isler / dis sistemlerle etkilesim.
4. **Proactive** — olay/zamanlama ile, gercek-zamanli insan olmadan; her gorev
   hedefe ulasinca cikar, rutin kapatilana kadar surer. Iyi tanimli tekrar eden is
   (hata triyaji, migrasyon, bagimlilik guncelleme).

## Dogru loop'un bilesenleri

- **Plan:** yurutmeden ONCE net basari kriteri. Tercihen DETERMINISTIK: gecen test
  sayisi, kapsam esigi, skor esigi. Bu proje icin hazir kapi: `python -m core gate`.
- **Execution:** her turda yapilacak is net olsun.
- **Verification:** kaliteyi kodla. Claude'un sonucu GORMESINI/OLCMESINI saglayan
  arac/kontrol ekle. Ikinci-ajan review'i taze baglamla daha az yanli.
- **Stopping:** acik ve olculebilir. "Yeterince iyi" gibi belirsiz kosul kullanma.
- **Iteration:** durma saglanana kadar tekrarla; her turda yalnizca sirada olani
  duzelt (kapi ciktisindaki `next_actions`).

## Bu platform icin kanonik desen

Yazilim isi icin loop'u deterministik kapiya bagla:

```
/goal: `python -m core gate` "done: true" donene kadar devam et.
Her tur: kapi ciktisindan next_actions'i oku; yalnizca o kontrolu duzelt; tekrar olc.
Uygulamayi yazan, kendi kodunu onaylamaz — bagimsiz review icin taze baglam kullan.
```

Yasamdongusunun tamami (plan->gelistir->test->review->dogrula) icin
`software-lifecycle` skill'ine bak.

## Token yonetimi
- Net basari/durma kriteri yaz ki Claude cozume daha erken varsin.
- Rutini gerektiginden sik calistirma — arayi, izledigin seyin degisme sikligiyla esle.
- Kucuk isler icin coklu ajan/loop kurma; primitive'i ise gore sec.

## Anti-desenler
- Belirsiz durma kosulu -> asiri iterasyon, token israfi.
- Yetersiz dogrulama -> sessiz kalite dususu.
- Deterministik isi loop'a sokmak -> script kullan.
- Cok sik zamanlama -> israf.
