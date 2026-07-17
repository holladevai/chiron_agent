---
name: ai-council
description: Claude bir problemde TAKILDIGINDA diger AI modellerinden fikir/ikinci gorus alma proseduru. Ayni hata iki kez tekrarladiginda, bir yaklasim tikandiginda, zor bir tasarim/mimari karari verilirken ya da kullanici "en iyi yaklasim/baska fikir/farkli acidan bak" dediginde uygulanir. Ana beyin Claude kalir; kurul yalnizca GEREKTIGINDE danisilir (her gorevde degil). Ek saglayici anahtari yoksa Claude tek basina devam eder.
version: 1.0.0
risk_level: low
---

# AI Council — takilinca diger modellerden fikir al

Ana beyin Claude'dur. Bu skill, Claude tek basina zorlandiginda env'de anahtari
MEVCUT olan diger AI modellerine (OpenAI, Gemini, Mistral, DeepSeek, yerel Ollama…)
problemi dagitip fikir toplamayi ve sentezlemeyi tanimlar. Sakana AI'nin "tek model
degil, model takimi" ve "role gore farkli model" fikrinin token-verimli halidir:
kurul HER gorevde degil, YALNIZCA gerektiginde toplanir.

## Ne zaman danis (tetikleyiciler)

Su durumlardan biri varsa danismayi dusun:
- Ayni hata/basarisizlik iki kez tekrarladi (bir tool cagrisi iki kez patladi).
- Bir yaklasim tikandi; ilerleme durdu.
- Zor bir tasarim/mimari karari var; birden fazla makul secenek yarisiyor.
- Kullanici acikca "en iyi yaklasim", "baska fikir", "farkli acidan bak", "dogrula"
  diyor.
- Yuksek riskli/geri donusu zor bir karar; ikinci bir gorus degerli.

Basit, tek-yonlu isler icin danisma — token israfi olur (ponytail).

## Nasil danisilir

Once mevcut saglayicilari gor (maskeli):
```
python -m core providers
```
Sonra problemi kurula dagit (anahtar yoksa zarif bicimde bos doner):
```
python -m core consult "NET SORU / karar" --context-file <ilgili_dosya>
```
- `--context-file`: ilgili kod/hata/tasarim baglami (opsiyonel).
- `--exclude`: varsayilan `anthropic` (soruyu soran zaten Claude). Claude'un kendi
  ailesinden de fikir istersen `--exclude ""` ver.
- `--providers a,b`: yalnizca belirli saglayicilara sor.

Cikti her saglayicinin fikrini ayri ayri verir (`opinions`). Bir saglayici
hata/timeout verirse atlanir; digerleri etkilenmez.

## Fikirleri nasil kullan (sentez)

Kurul KARAR VERMEZ; Claude verir. Gelen fikirleri:
1. Ortak noktalari isaretle (birden cok model ayni seyi soyluyorsa guclu sinyal).
2. Celiskileri kendi muhakemen ve kanitla coz — oy sayma degil, gerekce tart.
3. Uygulanabilir olani KENDIN dogrula (kod ise `python -m core gate`, iddia ise test).
4. Nihai karari ve NEDEN'ini kisaca yaz; hangi fikri neden aldigini/reddettigini belirt.

Guvenlik notu: `consult` problemi UCUNCU TARAF API'lerine gonderir (veri disari
cikar). Hassas/gizli icerik varsa danisma ya da baglami sadelestir. Anahtarlar
audit'e maskeli yazilir, asla acik degil.

## Ilgili
- Yasamdongusu ve deterministik kapi: `software-lifecycle`, `python -m core gate`.
- Loop tasarimi: `loop-engineering`.
- Bagimsiz kod incelemesi (tek saglayici ici): `sw-reviewer` subagent.
