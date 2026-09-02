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

**Protokol kelanjutan untuk agen pemrograman AI.**Memori proyek berada dalam format teks biasa
berkas Markdown di dalam proyek(`.saipen/`), sehingga setiap agen dingin yang kompatibel —
tanpa riwayat percakapan, tanpa memori sesi — dapat berjalan`/saipen continue`, membaca
yang telah disimpan`next_action`, dan melanjutkan pekerjaan tanpa meminta pengguna untuk menjelaskan kembali
apa pun. Keadaan milik proyek, bukan memori satu vendor model tertentu.

**Satu perintah untuk melanjutkan. Keadaan berkas teks biasa. Kontrak yang dicek oleh mesin.**

Repository memvalidasi dirinya sendiri setiap kali ada push; instalasi, keadaan, pemeriksaan, dan
uninstall are all local — no cloud service, no daemon, no database.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.241.1** | [Spesifikasi](SPEC.md) | [Panduan](GUIDE.md) | [Inti](saipen/CORE.md) | [Pemeliharaan](saipen/MAINTENANCE.md) | [Gaya](saipen/STYLE.md) | [UI](saipen/UI.md) | [Kesesuaian](saipen/CONFORMANCE.md) |MIT

**Tombol cepat:** `cc` melanjutkan konteks proyek hingga konvergensi (melanjutkan tujuan aktif jika ada yang ditetapkan), `sss` melaporkan status tanpa menyentuh kode, dan `ss` menyimpan titik periksa lalu berhenti. [Lihat peta 19 tombol lengkap](saipen/RFC.md#110-command-surface). Kembar Sirilik juga berfungsi: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## Apa yang tetap ada

Memori proyek langsung berada di`.saipen/`— file biasa yang bisa Anda baca, beda, dan
commit di sebelah kode. Agen dingin menjawab lima pertanyaan dari file
sendirian:

|File / bidang|Jawaban|
|---|---|
| `STATE.md` |Apa yang sedang terjadi saat ini?(fase, tiket aktif, mode operasi, penghalang) |
| `BOARD.md` |Apa pekerjaan yang ada / apa yang sedang berlangsung?(grafik tiket: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |Mengapa proyek mencapai keadaan ini?(grafik acara yang hanya menambahkan) |
| `KNOWLEDGE/` |Apa fakta proyek yang tahan lama harus bertahan selama sesi?|
| `next_action` (dalam`STATE.md`) |Apa tindakan tepat yang harus dilakukan agen berikutnya?|

Ini adalah kontrak checkpoint, bukan saran desain:`saipen stop`dan setiap
transisi tiket menulis file dalam urutan tetap, dan hasilnya diperiksa oleh
validator. Tidak ada yang disimpan dalam database yang dihosting, dan tidak ada yang hilang ketika
sesi berakhir.

## Pemula cepat

**1. Instal sekali per mesin**— mengajarkan Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity, dan apa pun yang generic`~/.agents/skills`pembaca(FreeBuff, dll.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`blok ke instruksi agen
file yang sudah Anda miliki(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— menyimpan cadangan ke`.bak`pertama —
dan menyalin protokol ke dalam folder keterampilan yang sesuai. Tidak ada yang di luar itu
jalur, tanpa daemon, tanpa panggilan jaringan.</sub>

**2. Mulai sebuah proyek**— buka agen di folder Anda, ketik:

> `saipen set`

**Tanpa instal?**Tempel satu baris ke agen apa pun:

> Baca&lt;clone&gt;/saipen/BOOT.md terlebih dahulu(inti cold-start), lalu&lt;clone&gt;/saipen/INDEX.md +&lt;clone&gt;/saipen/STYLE.md dan ikuti mereka.

**Berubah pikiran?**Satu perintah mengembalikannya:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Ini menghapus tepat blok yang ditandai(menghargai bagian lain dari file Anda), menyimpan
a `.uninstalled.bak`salin terlebih dahulu, dan menghapus folder keterampilan.

## Mengapa tidak hanya riwayat percakapan?

SAIPEN menargetkan kegagalan tertentu: agen penulisan kode AI yang tidak mengingat apa pun
setelah sesi berakhir. Alat dan kebiasaan lain menutupi sebagian dari masalah tersebut:

|Pendekatan|Apa kegunaannya|Apa yang tidak dibawa|
|---|---|---|
|Riwayat chat / memori model|Praktis, tanpa pengaturan awal|Tergantung pada sesi dan vendor; tidak disimpan bersama proyek, sehingga agen baru tidak pernah melihatnya|
|Statik`AGENTS.md`File instruksi|Aturan dan konvensi yang stabil|Tidak secara langsung mewakili status tugas yang sedang berlangsung`next_action`, atau riwayat pemulihan|
|Pemantau masalah / TODO|Manajemen tugas dan backlog|Tidak sendirian mendefinisikan semantik kelanjutan agen — apa yang harus dibaca dan dieksekusi oleh agen dingin saat dilanjutkan|
| **SAIPEN** |Status eksekusi langsung, antrian pekerjaan, sejarah acara, pengetahuan yang tahan lama, dan aturan kelanjutan yang diverifikasi oleh mesin — disimpan dalam file biasa di sebelah kode|Tidak ada; kombinasi tersebut adalah kontrak|

Perbedaannya bukanlah satu file pun. Ini adalah bahwa SAIPEN yang membuat langkah melanjutkan
dapat diverifikasi oleh mesin: tindakan pertama agen dingin setelah`/saipen continue`adalah
ditentukan oleh yang disimpan`next_action`dan diverifikasi oleh validator, bukan
direkonstruksi dari ingatan.

## Bukti rekayasa

SAIPEN memadukan protokol file biasa yang normatif dengan yang dapat dieksekusi, berorientasi kegagalan
pemeriksaan. Repositori menunjukkan desain protokol/mesin status, Python
alat bantu, status yang didorong oleh skema, pemikiran pemulihan, pengujian regresi,
batas alur kerja multi-agens, dan disiplin spesifikasi.

- **Kontrak yang dirancang.** [SPEC.md](SPEC.md)mendefinisikan model kelanjutan yang didukung file
dan kontrak disk yang stabil;[CORE.md](saipen/CORE.md)
dan[MAINTENANCE.md](saipen/MAINTENANCE.md)memiliki perilaku normatif saat ini.
- **Status yang diperiksa mesin.**The stdlib-only canonical
  [validasi](tools/validate.py)membaca live
  [schema STATE](extensions/schemas/state.schema.json)dan memeriksa fase
transisi, ketergantungan tiket, tautan grafik acara, lintas dokumen
invariant, kemampuan, dan state pemulihan.
- **Cakupan kegagalan.** [CONFORMANCE.md](saipen/CONFORMANCE.md)memetakan
persyaratan ke[fixture skenario](tests/scenarios/); the
  [pembaca skenario](tools/run_scenarios.py)menjalankan kasus lulus/gagal struktural
termasuk keadaan pemulihan korup, transisi tidak valid, siklus ketergantungan, dan
pembatasan hanya baca.
- **Kontrol regresi.** [audit_checks.py](tools/audit_checks.py)mengubah
salinan yang diketahui baik dan membuktikan pemeriksaan validator masih bisa merah, daripada
menganggap pemeriksaan hijau permanen sebagai bukti.
- **Lapisan eksekusi.** [saipen.py](tools/saipen.py)menyediakan state yang tercatat
operasi;[bootstrap/](bootstrap/)menyimpan install, uninstall, dan export
helpers, dengan opsional[pre-commit hook installer](tools/install_hook.py).
- **Kompromi eksplisit.**State protokol inti adalah file biasa tanpa runtime
ketergantungan. Validasi kanonik dan alat CLI memerlukan Python, tetapi hanya menggunakan
perpustakaan standarnya dan tidak memerlukan`pip`instalasi.

## Arsitektur

Tiga lapisan, ketergantungan satu arah secara ketat:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Inti tidak bergantung pada Pemeliharaan: dengan evolusi otonom dinonaktifkan, SAIPEN
masih merupakan protokol kelanjutan lengkap — agen dingin masih dapat melanjutkan.

- **Mesin keadaan inti** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Pemeliharaan otonom**— papan dihentikan(tidak ada yang dapat dioperasikan dalam`## TODO`,
tidak ada dalam`## DOING`)dan tidak`BLOCKED`? Transisi otomatis`HUNT` (memindai bug)
  → `ADD` (mengembangkan fitur) → `HUNT`, tanpa pertanyaan sama sekali. Sesi yang duduk di
  `BLOCKED`tidak pernah secara otomatis berburu
  ([Pemeliharaan § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Mode Tujuan** — `/saipen goal <objective>`memutar papan dan menjalankan
objektif ke depan melalui VERIFY/REVIEW, jatuh ke pemeliharaan otonom
hingga aturan penyelesaian berlaku atau jalannya mencapai batasnya(3 gelombang / 20 tiket,
kemudian membuat titik pemeriksaan dan melaporkan) ([Pemeliharaan § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Penguatan**— input batch diparse menjadi tiket satu per satu secara bedah
  (CORE § 1.8); penerus pohon kotor mempertahankan pekerjaan yang belum dikomit(CORE § 1.5);
nilai-nilai seperti rahasia dihilangkan dari log(`sk-***`) (CORE § 1.2).

## Perintah umum

Pintu masuk sehari-hari; permukaan saat ini lengkap berada di
[Core § 1.10](saipen/CORE.md#110-command-surface).

|Perintah|Melakukan|
|---|---|
| `/saipen set` |Adopsi proyek: buat`.saipen/`status|
| `/saipen continue` |Melanjutkan dari status proyek yang telah disimpan — tanpa penjelasan ulang|
| `/saipen plan` |Mengubah permintaan atau backlog mentah menjadi tiket|
| `/saipen goal <text>` |Eksekusi gelombang otonom terhadap objektif baru|
| `/saipen validate` |Menjalankan pemeriksaan konformitas|
| `/saipen status` |Laporan hanya untuk dibaca: fase, tiket, penghalang, keusangan|
| `/saipen stop` |Membuat checkpoint dan menghentikan|

<details>
<summary><b>More commands</b></summary>

|Perintah|Melakukan|
|---|---|
| `/saipen hunt` |Mengakselerasi pemeriksaan kelemahan/peningkatan sekarang|
| `/saipen markhunt` |Audit kering tanpa batas — mencatat temuan, tidak melakukan perbaikan apa pun|
| `/saipen ship` |Pintu rilis; commit, tag, dan push ketika diperbolehkan|
| `/saipen clean` |Pembersihan papan dan status|
| `/saipen translate` |Pabrik terjemahan terisolasi|
| `/saipen prepare` / `/saipen collect` |Kerja paket untuk handoff / mengintegrasikan paket yang siap|
| `/saipen test` |Lakukan suite tes yang dinyatakan, hanya melaporkan|
| `/saipen crew` |Sirkuit kru berurutan tetap(buru → reproduksi → intake → bangun → terjemahkan → dokumentasikan → kirim) |
| `/saipen improve` |Audit meta-kontrol terhadap peningkatan protokol|
| `/saipen sub ...` |Spawn/adopt sub-agent hanya untuk membaca|

**Kunci paket.** `ee`/`qq`Persiapkan paket terjemahan/wiki lengkap tanpa
mengintegrasikan;`eee`/`qqq`Terima hanya paket yang siap, lalu integrasikan, verifikasi,
ulas, dan kirim.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)melangkah seluruhnya
kru bawaan dalam urutan tetap — sensor(saihunt, saitest, saipython, saiui),
produsen(saitranslate, saiwiki)dan Core sebagai penulis utama pohon tunggal —
sampai ada ulasan segar lain yang tidak memiliki perubahan nyata yang tersisa. Ini menambahkan tepat satu
mekanisme sendiri: target orkestrasi tahan lama(``execution_intent:
konvergen` with `converge_target: crew`)yang membuat sirkuit dapat dilanjutkan dan
dapat diturunkan dari bukti crash.`saipen crew --dry-run --json`menurunkan
sirkuit hanya baca;`bootstrap/saipen_crew.*`adalah BUKAN wajib manual
bantuan multi-window, bukan apa`saipen crew`yang dimaksud. Lihat
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Apa yang SAIPEN bukan

- **Sebuah LLM atau model**— ini adalah protokol yang diikuti oleh agen, bukan kecerdasan.
- **Sebuah IDE atau database memori yang dihosting**— state adalah file biasa dalam proyek Anda;
tidak ada yang dihosting.
- **Pengganti Git**— Git masih memiliki sejarah versi; commitlah
  `.saipen/`seperti kode lainnya.
- **Konsensus terdistribusi**— lihat batas konkurensi di bawah ini.
- **Jaminan bahwa LLM akan membuat keputusan rekayasa yang benar**— itu
mengurangi kehilangan konteks dan drift perilaku; itu tidak membuat agen stokastik
tidak pernah salah.

Tugas SAIPEN adalah kontrak kelanjutan/keadaan plus validasi dan alat —
memberikan agen berikutnya titik awal yang telah dicek oleh mesin, bukan sihir.

**Batasi koncurrent.**Mutasi state yang dijurnal(SAIOPS)menggunakan
kunci OS berbasis proyek dan jurnal pemulihan([OPS § 5](saipen/OPS.md#5-locks)).
Perubahan proyek biasa dan penulis yang terputus berada di luar kunci tersebut. SAIPEN
bukan konsensus terdistribusi, sehingga penulis yang terputus memerlukan koordinasi eksternal
koordinasi([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ekosistem

|Proyek|Hubungan dengan SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Pusat kontrol Windows lokal untuk proyek SAIPEN — secara otomatis menemukan`.saipen/`ruang kerja, memvisualisasikan kondisi hidup dan keputusan konformitas, mengelola tiket, dan meluncurkan AI CLIs. Sebuah pendamping, bukan otoritas.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Fork CodeNomad downstream yang mengintegrasikan SAIPEN: menyuntikkan`BOOT.md`/`STYLE.md`ke dalam peluncuran OpenCode, menampilkan pintasan SAIPEN dan tampilan status proyek, serta menambahkan antrian prompt yang bertahan.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Pad Windows portabel dan manajer snippet yang secara otomatis mendeteksi`.saipen/`folder dan menambahkan penglihat STATE/BOARD/LOG hanya untuk dibaca.|

## Dokumentasi

|Dokumen|Apa itu|
|---|---|
| [SPEC.md](SPEC.md) |Arsitektur formal, tujuan desain, uji litmus|
| [CORE.md](saipen/CORE.md) |Kontinuasi normatif, mesin keadaan, dan kontrak perintah|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Pemeliharaan otonom dan Mode Tujuan|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Persyaratan eksekusi/perilaku dan aturan validator|
| [GUIDE.md](GUIDE.md) |Tutorial manusia|
| [RFC.md](saipen/RFC.md) |Redirect kompatibilitas ke dokumen normatif terpisah|
| [STYLE.md](saipen/STYLE.md) |Gaya komunikasi agen dan suara|
| [UI.md](saipen/UI.md) |Panduan desain UI Vintage Golden|
|Brochure|Brochure presentasi —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Bahasa Inggris](guides/GUIDE_EN.md) · 🇪🇪 [Eesti](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Bahasa Jerman](guides/GUIDE_DE.md) · 🇫🇷 [Bahasa Prancis](guides/GUIDE_FR.md) · 🇪🇸 [Bahasa Spanyol](guides/GUIDE_ES.md) · 🇮🇹 [Bahasa Italia](guides/GUIDE_IT.md)

🇵🇹 [Bahasa Portugis](guides/GUIDE_PT.md) · 🇳🇱 [Bahasa Belanda](guides/GUIDE_NL.md) · 🇵🇱 [Bahasa Polandia](guides/GUIDE_PL.md) · 🇸🇪 [Bahasa Swedia](guides/GUIDE_SV.md) · 🇩🇰 [Bahasa Denmark](guides/GUIDE_DA.md)

🇫🇮 [Finlandia](guides/GUIDE_FI.md) · 🇳🇴 [Norwegia](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Bahasa Vietnam](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Bahasa Turki](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Ceko](guides/GUIDE_CS.md) · 🇷🇴 [Bahasa Rumania](guides/GUIDE_RO.md) · 🇭🇺 [Bahasa Hongaria](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Bahasa Slovakia](guides/GUIDE_SK.md) · 🇭🇷 [Bahasa Kroasia](guides/GUIDE_HR.md)

</details>

## Catatan konfigurasi

**Bahasa balasan.**Agen menjawab dalam**Estonia**secara default — itu adalah sebuah
pengaturan, bukan kebutuhan protokol, dan tidak ada yang lain tentang SAIPEN yang berbahasa Estonia.
Protokol, kode, commit, dan setiap dokumen tetap berbahasa Inggris pada setiap
nilai. Ubahlah di satu tempat: baris`reply_language:`di bagian atas
[`saipen/STYLE.md`](saipen/STYLE.md). `et`Estonia,`en`Inggris,`ru`Rusia,
`auto`mengambil dari pesan yang Anda kirim.

**Adapters.**Platform yang tidak ditangani oleh injektor(DeepSeek, Qwen, standalone
OpenAI, dll.)? Catatan per-platform berada di`extensions/adapters/`.

## Screenshot

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
