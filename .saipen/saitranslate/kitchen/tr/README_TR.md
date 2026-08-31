<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
</p>

<div align="center">
  <h3><a href="README.ee.md">🇪🇪 LOE SEDA EESTI KEELES / ESTONIAN 🇪🇪</a></h3>
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="README.ded.md">👴 Дед-Версия (Russian)</a> &nbsp;|&nbsp;
  <a href="README.ja.md">🇯🇵 日本語 (Japanese)</a>
</div>

# SAIPEN

**AI kodlama ajanları için devam protokolü.**Proje hafızası düz metin
içindeki Markdown dosyalarında(`.saipen/`), bu nedenle herhangi bir uyumlu soğuk ajan —
sohbet geçmişi yok, oturum hafızası yok — çalıştırabilir`/saipen continue`, okuyabilir
kalıcı hale getirilmiş`next_action`, ve kullanıcıya yeniden açıklama istemeden çalışmayı sürdürebilir
Her şeyi. Durum projeye aittir, bir model satıcısının hafızasına değil.

**Devam etmek için bir komut. Düz dosya durumu. Makine kontrolü yapılan sözleşmeler.**

Depo her push işlemi sırasında kendini doğrular; kurulum, durum, kontroller ve
kaldırma işlemi tümüyle yereldir — bulut hizmeti, arka plan programı, veritabanı yok.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.233.4** | [Spesifikasyon](SPEC.md) | [Kılavuz](GUIDE.md) | [Çekirdek](saipen/CORE.md) | [Bakım](saipen/MAINTENANCE.md) | [Stil](saipen/STYLE.md) | [Kullanıcı Arayüzü](saipen/UI.md) | [Uygunluk](saipen/CONFORMANCE.md) |MIT

**Kısayol tuşları:** `cc` proje bağlamını yakınsamaya kadar sürdürür (ayarlanmışsa çalışan hedefi sürdürür), `sss` koda dokunmadan durumu bildirir ve `ss` kontrol noktası kaydedip durur. [19 tuşluk tam haritaya bakın](saipen/RFC.md#110-command-surface). Kiril ikizleri de çalışır: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

```text
Project
  |
  +-- .saipen/STATE.md ------ what is happening right now (phase, ticket, mode, next_action)
  +-- .saipen/BOARD.md ------ what work exists (DOING / TODO / DONE / BLOCKED)
  +-- .saipen/LOG.md -------- why the project reached this state (event history)
  +-- .saipen/KNOWLEDGE/ ---- what durable facts must survive sessions
          |
          v
   /saipen continue
          |
          v
      cold agent
          |
          v
     next_action -> work -> checkpoint -> next ticket
```

## Ne kalmış

Canlı proje hafızası içinde bulunur`.saipen/`— okuyabileceğiniz, fark çıkarabileceğiniz ve
kodun yanına commit edebileceğiniz düz dosyalar
bir arada:

|Dosya / alan|Cevaplar|
|---|---|
| `STATE.md` |Şu anda ne oluyor?(aşama, aktif bilet, çalışma modu, engelleyici) |
| `BOARD.md` |Hangi iş var / hangisi aktif?(bilet grafiği: YAPILIYOR, YAPILACAK, TAMAMLANDI, ENGELLİ) |
| `LOG.md` |Neden proje bu hale geldi?(ekleme-only olay grafiği) |
| `KNOWLEDGE/` |Hangi dayanıklı proje gerçekleri oturumlar arasında hayatta kalmalıdır?|
| `next_action` (içinde`STATE.md`) |Bir sonraki代理人 ne tam olarak yapmalı?|

Bu bir kontrol noktası sözleşmesidir, bir tasarım önerisi değildir:`saipen stop`ve her
bilet geçişi dosyaları sabit bir sırayla yazılır ve sonuç
bir doğrulayıcı tarafından kontrol edilir. Barındırılan bir veritabanında hiçbir şey saklanmaz ve bir şey kaybolmaz
oturum sona erer.

## Hızlı Başlangıç

**1. Makine başına bir kez kurun**— Claude Code, Codex, Gemini, OpenCode'ı öğretir,
Aider, Antigravity ve herhangi bir genel`~/.agents/skills`okuyucu(FreeBuff, vs.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`ajan talimatına blok ekler
zaten sahip olduğunuz(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— her birini`.bak`önce —
ve protokolü uygun beceri klasörlerine kopyalar. Bunların dışında hiçbir şey yok
yollar, daemon yok, ağ çağrıları yok.</sub>

**2. Bir proje başlatın**— klasörünüzde bir agent açın, şu yazın:

> `saipen set`

**Yükleme gerekmez mi?**Herhangi bir agent'a tek satır yapıştırın:

> Oku&lt;clone&gt;/saipen/BOOT.md önce(soğuk başlatma kerneli), sonra&lt;clone&gt;/saipen/INDEX.md +&lt;kopyala&gt;/saipen/STYLE.md ve bunları takip edin.

**Düşünceyi değiştirdiniz mi?**Bir komut bunu tekrar yerine koyar:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Bu, işaretlenmiş bloğu tamamen kaldırır(dosyanın diğer kısmını etkilemeden), kaydeder
a `.uninstalled.bak`önce kopya alır ve beceri klasörlerini kaldırır.

## Neden sadece sohbet geçmişi olmasın?

SAIPEN, belirli bir başarısızlığı hedefler: bir oturum bittiğinde hiçbir şeyi hatırlamayan bir AI kodlama ajansı
Diğer araçlar ve alışkanlıklar bu sorunun bir kısmını çözer:

|Yaklaşım|Ne için iyi|Ne taşımaz|
|---|---|---|
|Sohbet geçmişi / model belleği|Kolay, kurulum gerektirmez|Oturum ve sağlayıcıya bağlıdır; projeyle birlikte depolanmaz, bu nedenle soğuk bir ajan bunu asla görmez|
|Statik`AGENTS.md`/ talimat dosyası|Dayanıklı ayakta kalan kurallar ve gelenekler|Canlı görev durumunu temsil etmez`next_action`, veya kurtarma geçmişi|
|İssue / TODO izleyicisi|Görev ve backlog yönetimi|Kendi başına ajan devamı semantiğini tanımlamaz — bir soğuk ajanın devam etmesi gerektiğinde neyi okuyup çalıştırması gerektiği|
| **SAIPEN** |Canlı yürütme durumu, iş kuyruğu, olay tarihi, dayanıklı bilgi ve makine denetlenebilir devam kuralları — kodun yanındaki düz dosyalarda|Hiçbir şey; bu kombinasyon sözleşmedir|

Fark, tek bir dosya değildir. SAIPEN, devam etme adımını yapar
makine denetlenebilir: soğuk bir ajanın ilk eylemi`/saipen continue`dir
tarafından kalıcılaştırılan`next_action`ve doğrulayıcı tarafından doğrulanır, değil
hafızadan yeniden inşa edilir.

## Mühendislik kanıtı

SAIPEN, normatif düz dosya protokolü ile yürütülebilir, hata odaklı
kontroller. Depo, protokol/çevrim-makinesi tasarımı, Python
araçlar, şema sürümlü durum, kurtarma mantığı, regresyon testleri,
çok ajanlı iş akışı sınırları ve spesifikasyon disiplini.

- **Tasarlanmış sözleşmeler.** [SPEC.md](SPEC.md)dosya destekli
devam modelini ve sabit diskteki sözleşmeyi tanımlar;[CORE.md](saipen/CORE.md)
ve[MAINTENANCE.md](saipen/MAINTENANCE.md)mevcut normatif davranışları tanımlar.
- **Makine kontrolü durumu.**Stdlib-only canonical
  [doğrulayıcı](tools/validate.py)canlı
  [Durum şeması](extensions/schemas/state.schema.json)ve faz geçişlerini
bilet bağımlılıklarını, olay-grafiği bağlantılarını, çok belge
invariant'larını, yetenekleri ve kurtarma durumunu kontrol eder.
- **Hata kapsamı.** [CONFORMANCE.md](saipen/CONFORMANCE.md) gereksinimleri
  [senaryo sabitlerine](tests/scenarios/) eşler;
  [senaryo çalıştırıcısı](tools/run_scenarios.py) yapısal geçiş/kalma durumlarını çalıştırır
bozuk geri kazanım durumu, geçersiz geçişler, bağımlılık döngüleri ve
salt okunur kısıtlamaları içerir.
- **Regresyon kontrolleri.** [audit_checks.py](tools/audit_checks.py)değiştirir
bilinen iyi kopyaları ve doğrulayıcının kontrollerinin hâlâ kırmızı olabileceğini kanıtlar, bunun yerine
kalıcı olarak yeşil bir kontrolün kanıt olarak kabul edilmesi yerine.
- **Çalıştırılabilir katman.** [saipen.py](tools/saipen.py)günlüğe kayıtlı durum sağlar
işlemleri;[bootstrap/](bootstrap/)yüklemeyi, kaldırma ve dışa aktarmayı tutar
yardımcılar, isteğe bağlı bir[önceden-commit hook kurucu](tools/install_hook.py).
- **Açıkça yapılan tercihler.**Çekirdek protokol durumu, çalışma zamanı olmadan düz dosyalardır
bağımlılığı. Kanonik doğrulama ve CLI araçları Python gerektirir, ancak sadece
standart kütüphanesini kullanır ve hiçbir`pip`yüklemeye ihtiyaç duymaz.

## Mimari

Üç katman, kesinlikle tek yönlü bağımlılıklar:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Çekirdek, Bakım'a bağımlı değildir: otonom evrim devre dışı bırakıldığında, SAIPEN
hâlâ tam bir devam protokolüdür — soğuk bir ajan hâlâ devam eder.

- **Çekirdek durum makinesi** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Otonom bakım**— tahta durdu(içinde işlevsel hiçbir şey`## TODO`,
içinde hiçbir şey`## DOING`)ve değil`BLOCKED`? Otomatik geçişler`HUNT` (hata tarama)
  → `ADD` (özellikler geliştir) → `HUNT`, soru sorulmadı. Bir oturum oturuyor
  `BLOCKED`asla otomatik av etmez
  ([Bakım § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Hedef Modu** — `/saipen goal <objective>`tahtayı döndürür ve
amacını VERIFY/REVIEW üzerinden ilerletir, otomatik bakımın içine düşer
tamamlama kuralı ateşlenene veya yürütmeye kota ulaşıldığına kadar(3 dalgalar / 20 bilet,
ardından kontrol noktaları ve raporlar) ([Bakım § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Sertleştirme**— toplu girdi, cerrahi birer birer biletler haline ayrılır
  (CORE § 1.8); kirli ağaç devamı, işlem görmemiş işleri korur(CORE § 1.5);
gizli gibi değerler, günlüklerden silinir(`sk-***`) (CORE § 1.2).

## Genel komutlar

Günlük kullanım girdileri; tamamı mevcut yüzey şu anda burada yer alır
[Core § 1.10](saipen/CORE.md#110-command-surface).

|Komut|Yapar|
|---|---|
| `/saipen set` |Bir proje benimse: oluştur`.saipen/`Durum|
| `/saipen continue` |Devam eden proje durumundan devam et — tekrar bilgilendirme yok|
| `/saipen plan` |İstek veya ham backlog'u biletler haline dönüştür|
| `/saipen goal <text>` |Yeni bir hedefe karşı otonom dalgaları çalıştır|
| `/saipen validate` |Uygunluk kontrollerini çalıştır|
| `/saipen status` |Sadece okunabilir rapor: faz, biletler, engeller, eski kalma|
| `/saipen stop` |Kontrol noktası oluştur ve dur|

<details>
<summary><b>More commands</b></summary>

|Komut|Yapar|
|---|---|
| `/saipen hunt` |Hata/iyileştirme taramasını şimdi zorla|
| `/saipen markhunt` |Kuru, üst sınırlı olmayan denetim — bulguları kaydeder, hiçbir şeyi düzelmez|
| `/saipen ship` |Çıkış kapıları; izin verildiğinde komit, etiket ve push yap|
| `/saipen clean` |Tahtayı ve durumu temizle|
| `/saipen translate` |Ayrık çeviri fabrikası|
| `/saipen prepare` / `/saipen collect` |El ile devir için paket çalışması / hazır bir paketi entegre et|
| `/saipen test` |İlan edilen test takımı çalıştır, sadece rapor ver|
| `/saipen crew` |Sabit sıralı ekip devresi(av → tekrar üret → alım → inşa → çeviri → belge → gönder) |
| `/saipen improve` |Protokol iyileştirmeleri için meta-kontrol denetimi|
| `/saipen sub ...` |Salt okunur alt ajanlar oluştur/adopt et|

**Paket anahtarları.** `ee`/`qq`Tam çeviri/wiki paketlerini hazırlayın, entegrasyon olmadan
entegrasyon;`eee`/`qqq`Sadece hazır paketleri kabul edin, ardından entegre edin, doğrulayın,
inceleyin ve itin.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)tümüne yürüyor
sabit bir sırayla inşa edilmiş ekip — sensörler(saihunt, saitest, saipython, saiui),
üreticiler(saitranslate, saiwiki)ve Core, tek ana ağaç yazarı olarak —
başka bir taze geçişin hiçbir şeyi gerçekten değiştirmeyecek kadar bitene kadar. Tam olarak bir tane ekliyor
kendi mekanizması: dayanıklı bir orkestrasyon hedefi(`execution_intent:
birleşmek` with `birleşme_hedefi: ekip`)devre yeniden başlatılabilir hale getiren ve
kanıtlardan çıkarılabilecek şekilde çökmeyi sağlar.`saipen crew --dry-run --json`çıkarım yapar
devreyi salt okunur hale getirir;`bootstrap/saipen_crew.*`bir OPCİYONEL el ile
çok pencelik yardımcıdır, asla ne`saipen crew`anlama. Bak
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## SAIPEN'in ne olmadığını

- **Bir LLM veya bir model**— bu, ajanların takip ettiği bir protokoldür, bir zekâ değildir.
- **Bir IDE veya bir barındırılmış bellek veritabanı**— durum, projenizdeki düz dosyalar;
hiçbir şey barındırılmaz.
- **Git'in bir alternatifi**— Git hâlâ sürüm geçmişini yönetiyor;
  `.saipen/`kodunuzun diğer parçaları gibi kaydedin.
- **Dağıtılmış konsensüs**— aşağıda bulunan eşzamanlılık sınırını inceleyin.
- **Bir LLM'nin doğru mühendislik kararları alacağına dair garanti**— bu
bağlam kaybunu ve davranış kaymasını azaltır; ancak stokastik ajanları
hata yapamaz hale getirmez.

SAIPEN'in işi, devam/ durum sözleşmesi artı doğrulama ve araçlar —
bir sonraki ajanda, makine tarafından kontrol edilmiş bir başlangıç noktası, değil sihir.

**İş parçacığı sınırı.**Günlüklü durum değişiklikleri(SAIOPS)bir
proje kapsamında OS kilidi ve bir geri kazanım günlüğü([OPS § 5](saipen/OPS.md#5-locks)).
İlginç proje düzenlemeleri ve bağlantısız yazarlar bu kilide dışında yer alır. SAIPEN
dağıtılmış konsensüs değildir, bu yüzden bağlantısız yazarlar harici
koordinasyon([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ekosistem

|Proje|SAIPEN ile İlişki|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |SAIPEN projeleri için yerel Windows kontrol merkezi — otomatik keşfeder`.saipen/`çalışma alanlarını, canlı durumu ve uygunluk kararlarını görselleştirir, biletleri yönetir ve AI CLIs başlatır. Bir yardımcıdır, otorite değildir.|
| [SAIWORK](https://github.com/vacterro/saiwork) |SAIPEN entegrasyonu olan aşağı akış CodeNomad forks:`BOOT.md`/`STYLE.md`OpenCode başlatmalarına ekler, SAIPEN kısayolları ve proje durumu görünümleri sunar ve kalıcı bir istek kuyruğu ekler.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Otomatik algılayan taşınabilir Windows not defteri ve parçacık yöneticisi`.saipen/`klasörlerini ekler ve salt okunur STATE/BOARD/LOG izleyicisi ekler.|

## Dökümantasyon

|Belge|Ne olduğunu|
|---|---|
| [SPEC.md](SPEC.md) |Formal mimari, tasarım hedefleri, litmus testi|
| [CORE.md](saipen/CORE.md) |Normatif devam, durum makinesi ve komut sözleşmesi|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Otomatik bakım ve Hedef Mod|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Uygulanabilir/davranışsal gereksinimler ve doğrulayıcı kurallar|
| [GUIDE.md](GUIDE.md) |İnsan için öğretici|
| [RFC.md](saipen/RFC.md) |Uyumluluk, bölünmüş normatif belgelere yönlendirme|
| [STYLE.md](saipen/STYLE.md) |Ajan iletişim tarzı ve sesi|
| [UI.md](saipen/UI.md) |Klasik Altın UI tasarım kılavuzu|
|Broşür|Sunum broşürü —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [İngilizce](guides/GUIDE_EN.md) · 🇪🇪 [Estonya](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Almanca](guides/GUIDE_DE.md) · 🇫🇷 [Fransızca](guides/GUIDE_FR.md) · 🇪🇸 [İspanyolca](guides/GUIDE_ES.md) · 🇮🇹 [İtalyanca](guides/GUIDE_IT.md)

🇵🇹 [Portekizce](guides/GUIDE_PT.md) · 🇳🇱 [Hollanda](guides/GUIDE_NL.md) · 🇵🇱 [Lehçe](guides/GUIDE_PL.md) · 🇸🇪 [İsveççe](guides/GUIDE_SV.md) · 🇩🇰 [Danca](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Çeçençe](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Yapılandırma notları

**Cevap dili.**Ajan,**Estonya**varsayılan olarak — bu bir
ayar, bir protokol gerekliliği değil ve SAIPEN ile ilgili başka hiçbir şey Estonya dili değildir.
Protokol, kod, commit'ler ve her belge her
değeri boyunca İngilizce'dir. Değiştirmek için tek bir yerde:`reply_language:`dosyanın en üstündeki
[`saipen/STYLE.md`](saipen/STYLE.md). `et`Estonya,`en`İngilizce,`ru`Rusça,
`auto`mesajınızdan seçer.

**Adaptörler.**İnjector tarafından desteklenmeyen platform(DeepSeek, Qwen, standalone
OpenAI, vs.)? Platforma özel notlar burada bulunur`extensions/adapters/`.

## Ekran görüntülerleri

<details>
<summary><b>Click to expand</b></summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- translation-model: qwen3:14b contract:structured-markdown-v2 -->
<!-- source-digest: README.md sha256:bb47f7158db4a7a4fd99298427c1e4bc6859433c36435640e129cc6dad2a63b7 -->
