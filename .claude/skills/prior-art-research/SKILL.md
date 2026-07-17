---
name: prior-art-research
description: Bir proje/özellik/tasarım PLANLAMADAN ÖNCE benzerlerini (pazar yerleri, satılan temalar/şablonlar, rakip ürünler, örnekler) araştırma; sundukları özellikleri ve tema/tasarım yaklaşımını çıkarma; ÇÖZEMEDİKLERİ boşlukları analiz etme; kullanıcı geri bildirimlerini/yorumlarını okuma ve tüm bunları plana yansıtma prosedürü. Herhangi bir web sitesi, uygulama, ürün, kütüphane veya tasarım işine başlarken plan aşamasında uygulanır.
version: 1.0.0
risk_level: low
---

# Prior-Art / Pazar Araştırması (plan öncesi)

"Boş sayfadan" plan yapma. Ciddi bir iş kurmadan önce, aynı problemi çözmüş olanlara
bak: ne sunmuşlar, nasıl tasarlamışlar, NEYİ çözememişler, kullanıcılar neye kızmış.
Plan bu kanıtla şekillenir — güçlüyü benimse, tuzaktan kaçın, boşluğu doldurarak farklılaş.

## Ne zaman uygulanır
Yeni bir proje/özellik/tasarım planlarken (web sitesi, uygulama, ürün, kütüphane,
görsel tema). Küçük mekanik düzeltmelerde gerekmez (ponytail). `software-lifecycle`
akışının PLAN aşamasının ilk adımıdır.

## 1) Benzerlerini bul (kaynak haritası)
İşe göre uygun kaynaklardan 5-10 güçlü örnek topla:
- **Web tema/şablon pazarları:** ThemeForest, TemplateMonster, Webflow şablonları,
  UI kit pazarları — satılan temalar özellik + fiyat + demo + puan içerir.
- **Tasarım vitrinleri:** Awwwards, Dribbble, Behance, Godly, Land-book — trend,
  düzen, animasyon, tipografi, renk yaklaşımı.
- **Ürünler:** Product Hunt, G2, Capterra, AlternativeTo — özellik ve konumlandırma.
- **Kod:** GitHub (yıldız/aktiflik), örnek repolar, açık kaynak alternatifler.
- **Uygulama:** App Store / Play yorumları.
Kaynak adını ve linkini kaydet (sonra plana kanıt olarak koy).

## 2) Özellik + tema çıkar
Her örnek için not al:
- **Özellikler:** ne sunuyor (liste). Ortak/olmazsa-olmaz olanları işaretle.
- **Tema/tasarım:** düzen, animasyon (ör. 3D/scroll/parallax), renk paleti,
  tipografi, ton (minimal/kurumsal/deneysel).
- **Teknoloji:** görünen stack (varsa), performans/erişilebilirlik izlenimi.
Küçük bir **özellik matrisi** çıkar (örnek × özellik).

## 3) Boşluk / eksik analizi (en kritik adım)
- Hiçbirinin iyi çözemediği ne var? (yavaşlık, mobil, erişilebilirlik, karmaşıklık,
  aşırı efekt, özelleştirme zorluğu…)
- Tekrarlayan sınırlar/ödünler neler?
- Bu boşluk = senin **farklılaşma** fırsatın.

## 4) Kullanıcı geri bildirimi
- Yorum/puan/inceleme oku (pazar yorumları, G2/Capterra, forum, Reddit, issue'lar).
- Tekrarlayan **şikayetleri** ve **övgüleri** ayıkla ("çok ağır", "kurulumu zor",
  "harika ama X yok"). Bunlar plan için altın.

## 5) Plana yansıt (çıktı)
Planı bu bulgularla yaz:
- **Benimse:** kanıtlanmış güçlü desenler (örneklerin ortak iyi yanları).
- **Kaçın:** tekrarlayan şikayet/tuzaklar.
- **Farklılaş:** çözülmemiş boşluğu senin işin nasıl kapatacak.
- Her kararın yanına kısa gerekçe + kaynak.

```
PRIOR-ART ÖZET
Örnekler: (ad — link — 1 satır)
Ortak özellikler / olmazsa-olmaz: ...
Tema/tasarım desenleri: ...
Çözülmemiş boşluklar: ...
Kullanıcı şikayetleri (tekrarlayan): ...
-> PLAN KARARLARI: benimse / kaçın / farklılaş (+gerekçe)
```

## İlkeler
- **Kopyalama değil, sentez:** fikir/desen öğren; birebir kopya, marka/telif ihlali YOK.
- **Kanıtla:** iddiaları kaynağa bağla; emin değilsen işaretle.
- **Token-verimli:** 5-10 güçlü örnek yeter; hepsini tarama.
- İlgili: `software-lifecycle` (plan aşaması), `capability-gap-analysis`,
  `experience-memory` (geçmiş dersleri de hatırla), `ai-council` (zor kararda fikir).
