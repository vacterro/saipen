<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Etiketi" width="200"/>
</p>

# SAIPEN

**Yapay zeka kodlama ajanları için devamlılık protokolü.** Sade markdown formatında kalıcı proje hafızası; böylece sohbet geçmişi olmayan soğuk bir ajan `/saipen continue` komutunu çalıştırır ve işine bir dakikadan kısa sürede yeniden başlar -- yeniden bilgilendirme yok, her sağlayıcıda, her gün.

**Tek komut. Sıfır hafıza kaybı.**

**v7.144.0** | [Spec](SPEC.md) | [Rehber](GUIDE.md) | [RFC](saipen/RFC.md) | [Stil](saipen/STYLE.md) | [Kullanıcı Arayüzü](saipen/UI.md) | [Uyum](saipen/CONFORMANCE.md) | sade markdown | sıfır bağımlılık | MIT

[![Rusça Rehber](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![İngilizce Rehber](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Estonca Rehber](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japonca Rehber](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Dede Sesi](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Kullanıcı -> /saipen continue
Ajan      -> STATE okur ("Şu an ne yapıyorum?")
Ajan      -> BOARD okur ("Hangi görevi alıyorum?")
Ajan      -> next_action okur (komutu çalıştırır)
Ajan      -> Çalışır.
```

### Proje Durumu > Model Hafızası
Hafıza bir modelin kafasında değil, projede yaşar. `Proje -> Hafıza -> LLM`, `Proje -> SAIPEN Durumu -> LLM` haline gelir.

### Temel Protokol Mantığı ve Garantileri
- **Çekirdek Durum Makinesi**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **İsteksiz (Zero-Prompt) Otonomi**: Açık yapılacak iş kalmadı mı? Otomatik geçiş: `HUNT` (hata tara) → `ADD` (özellik geliştir) → `HUNT` döngüsü. Sıfır soru sorulur.
- **Açık Tetikleyiciler**: `/saipen clean` (depo temizliği), `/saipen translate` (izole `.saipen/saitranslate/` fabrikası), `/saipen markhunt` (kuru/sadece kayıt limitsiz denetim), `/saipen prepare` (devir teslim için işi paketle), `/saipen validate` (uyumluluk kontrolü), `/saipen goal` (otonom dalga yürütme). Meta/kontrol: `/saipen status` (salt okunur rapor), `/saipen stop` (durumu kaydet ve durdur). Tam liste: RFC.md § 1.10.
- **Sıkı Güvenilirlik**: Toplu girdi ayrıştırma (cerrahi 1'er 1'er biletler), kirli ağaç benimseme (işlenmemiş değişiklikleri asla silmez), sır gizleme (`sk-***`).

## SAIPEN Tarafından Desteklenen Projeler
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — SAIPEN hafıza protokolü ile yerel olarak entegre edilmiş yüksek performanslı istem yönetim aracı.

## İki Katman

| Katman | Gerekli | Amaç |
|---|---|---|
| **Çekirdek (Core)** | ✅ | İşe güvenle devam etmek |
| **Bakım (Maintenance)** | Çekirdek Üzerine | Görevlendirme olmadan yazılımı geliştirmek |

**Otomatik Gelişim.** Açık yapılacak iş kalmadı mı, `/saipen` yazın: `HUNT` hataları, ölü kodları, başarısız testleri denetler. Temiz mi? `ADD` bir sonraki belirgin eksik kabiliyeti inşa eder, doğrular, tekrar avlanır. Ürün olgunlaştığında -> zarifçe durur.

**GOAL Modu.** `/saipen goal <istediğiniz şey>` panoyu döndürür (eski biletlerin derecesi düşürülür, asla silinmez) ve yeni hedefi ileriye doğru çalıştırır -- biletler arasında "devam edeyim mi?" yok, VERIFY/REVIEW asla atlanmaz. SHIP mevcut bir uzak depoya otomatik push yapar; yepyeni bir depo yine de bir kez sorar. Hedefi göndermek (SHIP) de durma noktası değildir -- ürün olgunlaşana, engellenene veya çalışma sınırına ulaşana kadar (3 dalga / 20 bilet, ardından kaydeder ve raporlar) doğrudan otonom HUNT/ADD bakımına geçer.

## Hızlı Başlangıç

**1. Her makine için bir kez kurun** -- Claude Code, Gemini, OpenCode, Aider, Codex, Antigravity ve herhangi bir genel `~/.agents/skills` okuyucuya (FreeBuff, vb.) öğretir:
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Bir proje başlatın** -- klasörünüzde bir ajan açın ve yazın:
> `saipen set`

Kurulum yok mu? Herhangi bir ajana tek satır yapıştırın:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Platform yukarıdaki listede yok mu (DeepSeek, Qwen, bağımsız OpenAI vb.)?
Platform bazlı notlar `extensions/adapters/` içinde yer alır.

## Belge ve Şartname Bağlantıları
- **[SPEC.md](SPEC.md)** -- resmi mimari, tasarım hedefleri, turnusol testi.
- **[RFC.md](saipen/RFC.md)** -- ajanlar tarafından yürütülen kuralsal şartname.
- **[GUIDE.md](GUIDE.md)** -- insan eğitimi ve ELI5 rehberleri:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- ajan iletişim stili ve ses tanımı.
- **[UI.md](saipen/UI.md)** -- Koyu Altın Win95 UI tasarım yönergeleri.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- davranışsal test senaryoları ve doğrulayıcı kuralları.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>


