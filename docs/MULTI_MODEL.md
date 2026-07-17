# Çoklu-Model Danışma Kurulu (AI Council)

**Ana beyin Claude'dur.** Bu katman, env'de anahtarı **mevcut** olan diğer AI
modellerini (OpenAI, Gemini, Mistral, DeepSeek, Groq, xAI, OpenRouter, yerel
Ollama…) keşfeder ve Claude bir işte **takıldığında** onlardan fikir/ikinci görüş
alır. Sakana AI'nin *"tek model değil, model takımı"* ve *"role göre farklı model"*
fikrinin token-verimli, ponytail-uyumlu hâlidir: kurul **her görevde değil,
yalnızca gerektiğinde** toplanır.

## "Kaç API varsa o kadar, tek varsa tekiyle" — otomatik güç ayarı

Anahtarlar **yalnızca ortam değişkeninden** okunur; kod/log/repo'ya asla girmez,
audit'e **maskeli** yazılır (`sk-1...abcd`).

| Mevcut anahtar | `python -m core providers` modu | Davranış |
|---|---|---|
| 0–1 (örn. sadece Claude) | `solo` | Claude tek başına — bugünkü davranış, hiç bozulmaz |
| 2 | `verify` | İkinci sağlayıcı bağımsız görüş/çapraz-doğrulama verebilir |
| 3+ | `council` | Paralel N fikir toplanır, Claude sentezler |

Hiç ek anahtar yoksa `consult` **zarif biçimde** boş döner ve "Claude tek başına
devam etmeli" notunu verir — sistem çalışmaya devam eder.

## Komutlar

```bash
# Hangi sağlayıcılar mevcut (maskeli)?
python -m core providers

# Takılınca fikir al (anahtar yoksa zarifçe boş döner):
python -m core consult "NET SORU veya karar" --context-file <ilgili_dosya>
```

Seçenekler:
- `--context-file f` — ilgili kod/hata/tasarım bağlamı
- `--exclude a,b` — hariç sağlayıcılar (varsayılan `anthropic`; soruyu soran zaten Claude)
- `--providers a,b` — yalnızca belirli sağlayıcılara sor
- `--timeout N`, `--max-tokens N`

Çıktı, her sağlayıcının fikrini ayrı verir (`opinions`). Biri hata/timeout verirse
atlanır, diğerleri etkilenmez (paralel + fallback).

## Anahtar ekleme

İlgili ortam değişkenini ayarlaman yeterli — kod değişmez:

| Sağlayıcı | Env anahtarı | Model override | Not |
|---|---|---|---|
| **NVIDIA NIM** | `NVIDIA_API_KEY` (`nvapi-…`) | `CHIRON_NVIDIA_MODEL` | 🥇 En iyi **açık kodlama** modelleri (Qwen3-Coder-480B, DeepSeek, Kimi K2); OpenAI-uyumlu, ücretsiz kredi |
| **Moonshot / Kimi** | `MOONSHOT_API_KEY` | `CHIRON_MOONSHOT_MODEL` | Kimi K2 — ajanik kodlamada güçlü |
| Fireworks | `FIREWORKS_API_KEY` | `CHIRON_FIREWORKS_MODEL` | Açık kodlama modelleri hızlı servis |
| Together | `TOGETHER_API_KEY` | `CHIRON_TOGETHER_MODEL` | Qwen3-Coder vb. |
| DeepSeek | `DEEPSEEK_API_KEY` | `CHIRON_DEEPSEEK_MODEL` | `deepseek-chat` (V3) / `deepseek-reasoner` |
| OpenAI | `OPENAI_API_KEY` | `CHIRON_OPENAI_MODEL` | |
| Google Gemini | `GEMINI_API_KEY` | `CHIRON_GOOGLE_MODEL` | |
| Mistral | `MISTRAL_API_KEY` | `CHIRON_MISTRAL_MODEL` | Codestral kodlama için |
| Groq | `GROQ_API_KEY` | `CHIRON_GROQ_MODEL` | çok hızlı çıkarım |
| xAI (Grok) | `XAI_API_KEY` | `CHIRON_XAI_MODEL` | |
| OpenRouter | `OPENROUTER_API_KEY` | `CHIRON_OPENROUTER_MODEL` | tek anahtar, 400+ model |
| Ollama (yerel) | `CHIRON_OLLAMA_BASE` | `CHIRON_OLLAMA_MODEL` | anahtarsız, yerel |
| Anthropic | `ANTHROPIC_API_KEY` | `CHIRON_ANTHROPIC_MODEL` | (soruyu soran zaten Claude → varsayılan hariç) |

Yeni sağlayıcı eklemek = `core/providers.py` içindeki `PROVIDERS` tablosuna bir satır.

### Önerilen kodlama modelleri — **17 Temmuz 2026 itibarıyla doğrulandı**

Model kimlikleri hızlı değişir; aşağıdakiler o tarihte doğrulanmış gerçek kimliklerdir.
`CHIRON_<PROV>_MODEL` ile override edilebilir.

| Amaç | Model kimliği | Nerede |
|---|---|---|
| En iyi açık kodlama (büyük, SOTA) | `qwen/qwen3-coder-480b-a35b-instruct` | NVIDIA NIM / Fireworks / Together |
| Verimli kodlama (tek iş istasyonu, ~%96 kalite) | Qwen3-Coder-Next (80B-A3B) | NVIDIA NIM |
| Ajanik kodlama uzmanı | **`kimi-k2.7-code`** (veya `-highspeed`) | Moonshot |
| Otonom ajan (SWE-Bench sınıfı, yüksek throughput) | Nemotron-3-Super-120B | NVIDIA NIM |
| Hızlı/ucuz kod | DeepSeek V4 Flash | NVIDIA NIM / DeepSeek |
| Güçlü muhakeme + kod | DeepSeek (`deepseek-chat` V-serisi / `deepseek-reasoner`) | DeepSeek / NVIDIA NIM |
| Hafif/yerel | Qwen3-Coder küçük varyant, Devstral 2 | Ollama (yerel) |

> ⚠️ **Kimi K2 (2025) serisi 25 Mayıs 2026'da emekliye ayrıldı** — eski `kimi-k2-*-preview`
> kimlikleri artık çalışmaz. Güncel: `kimi-k3` (amiral), `kimi-k2.7-code` (kodlama),
> `kimi-k2.6` (multimodal). Chiron varsayılanı `kimi-k2.7-code`.

### 🆓 Kimi'yi ÜCRETSİZ kullanma (17 Tem 2026)

Kimi K2.6, **OpenRouter üzerinden ücretsiz** sunuluyor (262k bağlam). Tek anahtar yeter:

```bash
setx OPENROUTER_API_KEY "sk-or-..."           # OpenRouter'dan ücretsiz anahtar
setx CHIRON_OPENROUTER_MODEL "moonshotai/kimi-k2.6:free"
python -m core providers                        # openrouter görünür, ücretsiz Kimi hazır
python -m core consult "zor soru" --context-file kod.py
```

Ayrıca NVIDIA NIM yeni kullanıcılara **1000 ücretsiz kredi** verir (üst kodlama
modellerini denemek için).

> Kaynaklar (17 Tem 2026 doğrulama): [Kimi model listesi](https://platform.kimi.ai/docs/models) ·
> [Kimi K2.6 free — OpenRouter](https://openrouter.ai/moonshotai/kimi-k2.6:free) ·
> [Kimi K3 duyurusu (VentureBeat)](https://venturebeat.com/technology/chinas-moonshot-ai-releases-kimi-k3-the-largest-open-source-model-ever-rivaling-top-u-s-systems) ·
> [NVIDIA NIM (OpenAI-uyumlu)](https://ai-sdk.dev/providers/openai-compatible-providers/nim) ·
> [2026 açık kodlama modelleri](https://kilo.ai/open-source-models)

## Fikirler nasıl kullanılır (sentez)

Kurul **karar vermez; Claude verir** (bkz. `ai-council` skill). Gelen fikirler:
1. Ortak noktaları işaretle (birden çok model aynı şeyi diyorsa güçlü sinyal).
2. Çelişkileri **gerekçeyle** çöz — oy sayma değil, muhakeme.
3. Uygulanabilir olanı **kendin doğrula**: kod ise `python -m core gate`, iddia ise test.
4. Nihai kararı ve nedenini yaz; hangi fikri neden aldığını/reddettiğini belirt.

## Güvenlik

- `consult`, problemi **üçüncü taraf API'lerine** gönderir → veri makineden çıkar.
  Hassas/gizli içerikte danışma ya da bağlamı sadeleştir. Bu, bilinçli, insan
  tarafından (anahtar koyarak) **opt-in** edilen bir yetenektir; asla otomatik değildir.
- Anahtarlar audit'e **maskeli** yazılır; olay kaydında yalnızca kullanılan
  sağlayıcı adları görünür (soru/anahtar değil).
- Minimal bağımlılık: yalnızca stdlib `urllib`; harici SDK yok, dış proxy yok
  (anahtarlar/veri üçüncü bir aracıya gitmez, doğrudan sağlayıcıya gider).
