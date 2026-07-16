# Otonom Uzmanlaşan AI Agent Platformu (ajan)

Bir AI agent'ın (Claude Code) karşılaştığı görevlerde **uzman prosedürleri zorunlu
kılan**, eksik yeteneklerini kendisi fark edip **güvenli sandbox'ta test ederek** ve
**politika kapılarından geçirerek** kendi yetenek kütüphanesine kontrollü biçimde
ekleyen, çalışır durumda bir sistemdir.

- Tasarım gerekçesi: [otonom_uzmanlasan_ai_agent_skills_mcp_mimarisi.md](otonom_uzmanlasan_ai_agent_skills_mcp_mimarisi.md)
- Agent çalışma kuralları: [CLAUDE.md](CLAUDE.md)
- IDE / global kurulum: [docs/IDE.md](docs/IDE.md)

> **Lisans:** Bu proje [PolyForm Noncommercial 1.0.0](LICENSE) ile lisanslıdır —
> **ticari kullanım yasaktır.** Ayrıntı için aşağıdaki [Lisans](#lisans) bölümüne bakın.

---

## Ana ilke

> Agent araştırmada ve sandbox testinde otonomdur; kalıcı kurulum, geniş yetki,
> production değişikliği ve canlı trading **deny-by-default** ve onay kontrollüdür.

Üç katmanlı davranış:

1. **Bilineni doğru yap** — doğrulanmış skill/tool kullan.
2. **Eksik yeteneği güvenli edin** — araştır, tara, sandbox'ta test et, politikaya göre ekle.
3. **Yeni uzmanlık üret** — skill yoksa birincil kaynaklardan üret, evaluator ile doğrula.

---

## Özellikler

### 1. Otomatik aktivasyon
Sistem her Claude Code oturumunda kendiliğinden devreye girer (`SessionStart` hook'u
çalışma protokolünü context'e enjekte eder). Komutla da kontrol edilir:

| Komut (prompt içinde) | Etki |
|---|---|
| `ajan devreye gir`, `ajan aktif`, `/ajan` | Protokolü açar |
| `is bitti`, `ajan dur`, `ajan kapat` | Protokolü bu oturumda kapatır |

Durum kalıcıdır (`.ajan_state.json`); varsayılan **aktif**. Elle kontrol:
```bash
python -m core ajan on|off|status
```

### 2. Yetkinlik açığı analizi (capability gap)
Riskli, belirsiz veya "en iyi / en güncel / doğrula" istenen her görevde agent önce
kendi güven skorunu ölçer:
```bash
python -m core gap --domain trading --skills backtest-integrity --risk high
```
Çıktıya göre yönlenir:
- `proceed` → mevcut skill'lerle yürüt
- `proceed_with_verification` → yürüt, sonucu `evaluator` subagent'ı doğrulasın
- `research_and_stage_capability` → eksik yeteneği güvenli akışla edin

### 3. Güvenli yetenek edinme (internetten hiçbir şey doğrudan kurulmaz)
İki şerit vardır:

**A) Otomatik şerit** — kaynak resmî org veya GitHub'da yüksek yıldızlı + bakımlı
repo ise, insan onayı beklenmez ama üç kapı zorunludur:
```
capability-manager (aday + metadata)
  → autoacquire-check   (güven katmanı: kaynak itibarı)
  → stage + statik tarama (prompt injection / exfiltration / pipe-to-shell)
  → eval (sandbox)
  → auto-security-reviewer (Sonnet, dosyaları OKUYARAK denetler)
  → autoacquire-promote (üç kapı geçerse otomatik kurulur; değilse insana düşer)
```

**B) Standart şerit** — bilinmeyen kaynak, yüksek risk veya tehlikeli izin:
```
keşif (capability-manager)
  → stage + statik tarama
  → security-gatekeeper (bağımsız/düşmanca denetim)
  → eval (sandbox, ağ kapalı)
  → promote (politika kararı):
       allow            → otomatik kurulur (düşük risk)
       require_approval → approvals/pending/<id>.md → İNSAN onaylar
       deny             → reddedilir
```

Otomatik şerit yalnızca risk ∈ {low, medium} ve tehlikeli izin YOK ise geçerlidir;
aksi hâlde immutable-core gereği insana gider (oauth / broker / high-risk).

### 4. Token-verimli öğrenme (deneyim hafızası)
Sistem deneyimden öğrenir ama context'i şişirmez. Dersler deterministik Python'da
(SQLite) saklanır; LLM'e göreve ilgili en fazla 5 kısa ders enjekte edilir:
```bash
python -m core learn recall --domain trading --query "backtest slippage" --k 5   # görev başı
python -m core learn add "KURAL" --domain trading --why "gerekçe"                # görev sonu (seçici)
```
Ders yalnızca **genel + tekrar eden + kanıtlı** olduğunda eklenir.

### 5. Dersten otomatik skill üretimi (kendi kendine öğrenme → kalıcı yetenek)
Tekrar eden ve doğrulanmış bir ders (uses ≥ 3, net pozitif) otomatik skill olur:
```bash
python -m core learn promotion-candidates   # olgunlaşan dersler
python -m core learn promote <ders-id>      # skill üret + tara + eval + kur
```
Üretilen skill düşük riskliyse otomatik kurulur ve Claude Code onu açıklamasına
göre ihtiyaç olunca kendiliğinden çağırır.

### 6. Anayasal güvenlik sınırları (değiştirilemez)
`policies/immutable-core.yaml` agent'ın değiştiremeyeceği sınırları tanımlar;
`core/guard_hook.py` bunları **fiziksel olarak** uygular (PreToolUse hook).
Agent asla yapamaz:
- Politika, güvenlik kuralları, audit log veya guard hook'u değiştirmek
- `.claude/skills/` altına tarama/eval/onaydan geçmemiş yetenek koymak
- Production'a yazmak, e-posta göndermek, canlı trade açmak (insan onayı şart)
- Broker'dan para çekmek, kendi risk limitlerini değiştirmek (mutlak yasak)

Politikayı yalnızca **insan** değiştirir ve `python -m core seal-policy` ile mühürler.

### 7. Hash-zincirli audit
Her karar `audit/audit.jsonl` dosyasına hash-zincirli yazılır; sonradan
değiştirilemez. `python -m core verify` zincir bütünlüğünü doğrular.

### 8. Bağımsız doğrulama (subagent'lar)
Kural: yüksek riskli bir işi yapan/bulan agent, aynı işin nihai onaylayıcısı olamaz.

| Subagent | Görev |
|---|---|
| `capability-manager` | Eksik yetenek araştırır, puanlar, staging'e hazırlar |
| `security-gatekeeper` | Adayı kurulmadan önce bağımsız/düşmanca denetler |
| `auto-security-reviewer` | Otomatik şeritte aday dosyalarını okuyarak APPROVE/REJECT verir |
| `evaluator` | İş sonucunu kanıtla, bağımsız doğrular |

### 9. Minimalist mühendislik (ponytail felsefesi)
"En iyi kod, hiç yazmadığın koddur." Kod yazmadan / bağımlılık veya yetenek
kurmadan önce karar merdiveni uygulanır: *bu gerçekten gerekli mi? zaten var mı?
stdlib yeter mi?* Güvenlik ve doğrulama bundan **muaftır** (asla atlanmaz).

---

## Kurulum

```bash
git clone https://github.com/holladevai/ajan_code.git
cd ajan_code
pip install -r requirements.txt
python -m core init      # dizinler, politika mührü, seed skill kayıtları
python -m core verify    # audit zinciri + politika bütünlüğü
pytest -q                # çekirdek testleri
```

İlk kurulumda bir kez (guard hook ve settings.json anayasal korumalı olduğundan
bunu insan çalıştırır):
```bash
python scripts/setup_ajan.py
```

### Global kurulum (her projede / her IDE'de)
Cursor / Windsurf / VS Code'da **Claude Code eklentisiyle** kullanılır. Bir kez:
```bash
python scripts/install_global.py   # pip install -e . + ~/.claude'a skills/agents/hooks
```
Platformun evi bu repodur; tüm projeler aynı yetenek kütüphanesini ve politikaları
paylaşır. Ayrıntı: [docs/IDE.md](docs/IDE.md).

---

## CLI referansı

```
python -m core <komut> [--root DIZIN]
```

### Agent'ın serbestçe kullanabildiği (salt-okunur / analiz)
| Komut | İşlev |
|---|---|
| `gap` | Yetkinlik açığı ve güven skoru raporu |
| `scan <dizin>` | Aday skill/tool statik güvenlik taraması |
| `list` | Registry'deki tüm yetenekler |
| `search <kelime>` | Registry'de arama |
| `stale` | Yeniden doğrulama bekleyen yetenekler |
| `verify` | Audit zinciri + politika bütünlüğü doğrulama |
| `report <id>` | Tek yeteneğin tam kaydı |
| `learn recall/add/...` | Ders defteri (öğrenme) |

### Yan etkili ama agent'ın kullanabildiği (politika kapılı)
| Komut | İşlev |
|---|---|
| `stage` | Adayı staging'e al (tarama + kayıt) |
| `eval` | Sandbox eval çalıştır |
| `promote` | Politika kararıyla kuruluma taşı |
| `revoke` | Yeteneği iptal et / geri al |
| `sandbox-run` | Komutu izole sandbox'ta çalıştır (temiz env, ağ kapalı) |
| `autoacquire-check` | Aday otomatik kuruluma uygun mu (güven katmanı) |
| `autoacquire-promote` | Üç kapıyı geçirip otomatik kur |

### Yalnızca İNSAN (guard hook agent'ı engeller)
| Komut | İşlev |
|---|---|
| `approve <id>` | Bekleyen onayı uygula |
| `seal-policy` | immutable-core değişikliğini mühürle |

---

## Tipik kullanım senaryoları

**Senaryo 1 — Riskli görev, agent kendini ölçer:**
```
Kullanıcı: "Şu stratejiyi backtest et, en güncel yöntemle doğrula."
Agent:  python -m core gap --domain trading --skills backtest-integrity --risk high
        → proceed_with_verification → işi yapar → evaluator subagent kanıtla doğrular
```

**Senaryo 2 — Eksik yetenek, güvenilir kaynak (otomatik şerit):**
```
Agent eksik skill fark eder → capability-manager aday bulur (resmî org reposu)
→ autoacquire-check PASS → stage + scan temiz → eval PASS
→ auto-security-reviewer APPROVE → otomatik kurulur, insan onayı gerekmez
```

**Senaryo 3 — Eksik yetenek, bilinmeyen kaynak (standart şerit):**
```
Aday bilinmeyen repo'dan → stage + scan → security-gatekeeper inceler
→ eval → promote kararı: require_approval → approvals/pending/<id>.md
→ İNSAN: python -m core approve <id>
```

**Senaryo 4 — Tekrarlayan ders skill olur:**
```
Görev sonlarında: learn add "X yaparken önce Y kontrol et" --domain web
3+ kullanım + net pozitif → learn promote <id> → kalıcı skill, otomatik çağrılır
```

---

## Bileşenler

| Katman | Konum | İşlev |
|---|---|---|
| Anayasal politika | `policies/immutable-core.yaml` | Agent'ın değiştiremeyeceği sınırlar (mühürlü) |
| Politika motoru | `core/policy.py` | Deny-by-default, risk temelli karar |
| Statik tarayıcı | `core/scanner.py` | Prompt injection / exfiltration / pipe-to-shell tespiti |
| Registry | `core/registry.py` | SQLite sürümlü yetenek kataloğu |
| Sandbox | `core/sandbox.py` | Taşınabilir süreç izolasyonu (temiz env, ağ kapalı) |
| Güven skoru | `core/confidence.py` | Kanıta dayalı yetkinlik açığı ölçümü |
| Eval runner | `core/evals.py` | Ölçülebilir doğrulama testleri |
| Pipeline | `core/lifecycle.py` | stage → eval → promote → approve/revoke |
| Audit | `core/audit.py` | Hash-zincirli, değiştirilemez denetim kaydı |
| Öğrenme | `core/learning.py` | Token-verimli ders defteri (ponytail felsefesi) |
| Guard hook | `core/guard_hook.py` | Claude Code PreToolUse anayasal koruma |

## Dizin yapısı

```
core/               Python çekirdek (policy, scanner, registry, sandbox, evals, lifecycle)
policies/           Deny-by-default politikalar; immutable-core.yaml değiştirilemez
.claude/skills/     AKTİF (yüklü) skill'ler — yalnızca burası yüklenir
.claude/agents/     Subagent tanımları
staging/skills/     Test edilen adaylar (aktif değil)
registry/           Sürümlü yetenek kataloğu (SQLite)
evals/              Ölçülebilir doğrulama spec'leri
approvals/pending/  İnsan onayı bekleyen paketler
audit/              Hash-zincirli denetim kaydı (audit.jsonl)
sandbox/runs/       İzole çalışma dizinleri
scripts/            Kurulum yardımcıları (setup_ajan.py, install_global.py)
tests/              Çekirdek testleri
docs/               IDE / global kurulum dokümanı
```

## Güvenlik özeti

- İnternetten bulunan hiçbir skill/MCP **doğrudan kurulmaz**; keşif → tarama →
  bağımsız güvenlik incelemesi → sandbox eval → politika kararı zorunludur.
- Kritik bulgulu aday **otomatik reddedilir**.
- İşi yapan/bulan agent, aynı işin **nihai onaylayıcısı olamaz** (ayrı subagent'lar).
- `approve` ve `seal-policy` yalnızca **insan** tarafından çalıştırılır; guard hook
  agent'ı fiziksel olarak engeller.
- Token verimliliği (ponytail): gereksiz kod/bağımlılık/skill eklenmez; öğrenme
  context'i şişirmeden, küçük dersler ve leksikal geri çağırma ile yapılır.

## Lisans

**PolyForm Noncommercial License 1.0.0** — tam metin: [LICENSE](LICENSE)

- ✅ Kişisel kullanım, araştırma, eğitim, deneme, kâr amacı gütmeyen kullanım serbesttir.
- ❌ **Ticari kullanım yasaktır** (ürün/hizmet içinde kullanmak, satmak, ticari
  faaliyette çalıştırmak dahil).
- Telif: © 2026 holladevai. Tüm hakları saklıdır (lisansta verilen izinler hariç).
