<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

<div align="center">
  <h3>🔥 <a href="README.ee.md">🇪🇪 LOE SEDA EESTI KEELES / ESTONIAN 🇪🇪</a> 🔥</h3>
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp; 
  <a href="README.ded.md">👴 Дед-Версия (Russian)</a> &nbsp;|&nbsp; 
  <a href="README.ja.md">🇯🇵 日本語 (Japanese)</a>
</div>

# SAIPEN

**Jätkamisprotokoll tehisintellektist programmeerimisagentidele.** SAIPEN hoiab projekti mälu lihtsas markdown-vormingus, nii et "külm" agent (ilma vestlusajaloota) saab käivitada `/saipen continue`, lugeda `STATE.md` -> `BOARD.md` -> aktiivse `LOG.md` lõppu -> `human_note` (kui on määratud), käivitada `next_action` ja jätkata tööd vähem kui minutiga -- ilma uuesti briifimata, suvalise teenusepakkujaga, mis tahes päeval.

**Üks käsk. Null sõltuvust. Null amneesiat.**

**v7.153.0** | [Spetsifikatsioon](SPEC.md) | [Juhend](GUIDE.md) | [RFC](saipen/RFC.md) | [Stiil](saipen/STYLE.md) | [UI](saipen/UI.md) | [Vastavus](saipen/CONFORMANCE.md) | MIT | [![CI](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)

[![Vene Juhend](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![Inglise Juhend](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Juhend](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Jaapani Juhend](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Vanaisa Hääl](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Kasutaja ->  /saipen continue
Agent    ->  loeb STATE.md (faas, ülesanne, next_action, režiim, human_note)
Agent    ->  loeb BOARD.md (DOING / TODO / DONE / BLOCKED piletid)
Agent    ->  loeb aktiivse LOG.md lõppu (hiljutised sündmused)
Agent    ->  loeb human_note (kui on määratud, ühekordne juhis)
Agent    ->  käivitab koheselt next_action (käsk)
Agent    ->  laeb faasi dokumendi ainult siis, kui reegleid on vaja
Agent    ->  Töötab.
```

### Projekti Olek > Mudeli Mälu
Mälu elab projektis, mitte mudeli peas. `Projekt -> Mälu -> LLM` muutub `Projekt -> SAIPEN Olek -> LLM`.

### Protokolli Põhiloogika ja Garantiid
- **Tuuma Olekumasin**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Ilma-Viipeta Autonoomia**: tahvel peatatud (ühtegi teostatavat `TODO`-d pole, `DOING` on tühi) **ja ei ole `BLOCKED`**? Automaatne üleminek `HUNT` (otsib vigu) → `ADD` (arendab funktsioone) → `HUNT`, ühtegi küsimust esitamata. `BLOCKED` olekus olev sessioon ei käivita kunagi automaatset jahti -- ta ootab, kuni inimene lahendab blokaadi (RFC § 2.1).
- **Selgesõnalised Päästikud**: `/saipen plan` (muuda palve või toores tööjärg piletiteks), `/saipen ship` (versiooni tõstmine, muutuste logi, sildistamine, üleslaadimine), `/saipen clean` (repo puhastamine), `/saipen translate` (isoleeritud `.saipen/saitranslate/` tehas), `/saipen markhunt` (kuiv auditeerimine ilma piiranguteta, salvestab ainult kirjeid), `/saipen prepare` (paki töö üleandmiseks kokku), `/saipen validate` (vastavuskontroll), `/saipen goal` (autonoomne laine käivitamine). Meta/juhtimine: `/saipen status` (ainult lugemiseks mõeldud aruanne), `/saipen stop` (kontrollpunkt ja peatus). See koos `saipen set` ja `saipen continue` moodustab kogu pinna -- kaksteist käsku, täielikud detailid RFC.md § 1.10 all.
- **Range Töökindlus**: Partii sisendi parsimine (kirurgilised 1-haaval piletid), musta puu ülevõtmine (ei pühi kunagi tegemata tööd ära), saladuste redigeerimine (`sk-***`).
- **Eksperimentaalne -- saicrew**: valikuline lisakiht (`extensions/subs/`, tuuma muudatusi pole) mitme agendiga meeskonna käivitamiseks -- üks Tuuma kirjutaja pluss ainult loetavad `saihunt`/`saipython` töötajad, kes annavad aru omaenda `OUTBOX.md` kaudu. Aktiivse otsetestimise all, pole veel otsast-lõpuni kontrollitud -- vaata `extensions/subs/crew.md`.

## SAIPEN-i Poolt Juhitud Projektid
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Suure jõudlusega viipade haldamise tööriist, mis on ehitatud SAIPEN mäluprotokolli ümber.

## Kaks Kihti

| Kiht | Nõutav | Eesmärk |
|---|---|---|
| **Tuum** | ✅ | Jätka tööd turvaliselt |
| **Hooldus** | Tuuma peal | Arenda tarkvara edasi ilma ülesanneteta |

**Automaatne Evolutsioon.** Kui ühtegi avatud tööülesannet pole järel, kirjuta `/saipen`: `HUNT` auditeerib vigu, surnud koodi, ebaõnnestunud teste. Puhas? `ADD` ehitab järgmise ilmselge puuduva võimekuse, kontrollib seda, ja peab taas jahti. Toode on küps -> peatub graatsiliselt.

**GOAL (EESMÄRK) Režiim.** `/saipen goal <mida sa soovid>` pöörab tahvli (vanad piletid alandatakse, neid ei kustutata kunagi) ja käivitab uue eesmärgi -- pole mingit "kas ma tohin jätkata?" piletite vahel, VERIFY/REVIEW ei jäeta kunagi vahele. SHIP lükkab automaatselt olemasolevasse repoisse; täiesti uus repo küsib siiski korra. Eesmärgi kohaletoimetamine ei ole samuti lõpp-punkt -- see langeb otse autonoomsesse HUNT/ADD hooldusesse, kuni toode on küps, blokeeritud või jooks tabab oma piiri (3 lainet / 20 piletit, seejärel salvestab ja raporteerib).

## Kiire Algus

**1. Paigalda kord iga masina peale** -- õpetab Claude Code'i, Codexit, Geminit, OpenCode'i, Aiderit, Antigravity't ja mis tahes üldist `~/.agents/skills` lugejat (FreeBuff jne):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>Mida see puudutab, nii et miski pole üllatus: see lisab tähistatud
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->` ploki sinu juba olemasolevatele agendi juhendfailidele (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`) -- varundades igaühe esmalt `.bak` failina -- ja kopeerib protokolli vastavatesse oskuste (skills) kaustadesse. Väljaspool neid teekondi pole midagi, ühtegi deemonit, ühtegi võrgupäringut.</sub>

**Muutsid meelt?** Üks käsk paneb kõik tagasi:
```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```
See eemaldab täpselt tähistatud ploki (jättes ülejäänud faili rahule), salvestab esmalt `.uninstalled.bak` koopia ja eemaldab oskuste kaustad.

**2. Alusta projekti** -- ava agent oma kaustas ja kirjuta:
> `saipen set`

Paigaldamata? Kopeeri ja kleebi üks rida suvalisele agendile:
> Read <clone>/saipen/BOOT.md first (cold-start kernel), then <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Platform ei ole ülalolevas nimekirjas (DeepSeek, Qwen, eraldiseisev OpenAI jne)?
Platvormi-põhised märkmed asuvad `extensions/adapters/`.

## Dokumentatsioon & Spetsifikatsioonide Lingid
- **[SPEC.md](SPEC.md)** -- formaalne arhitektuur, disainieesmärgid, lakmuspaber.
- **[RFC.md](saipen/RFC.md)** -- normatiivne spetsifikatsioon, mida agendid täidavad.
- **[GUIDE.md](GUIDE.md)** -- inimeste õpetused & ELI5 juhendid:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- agendi suhtlusstiil ja hääle defineerimine.
- **[UI.md](saipen/UI.md)** -- Vintage Golden UI disaini suunised.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- käitumuslikud testistsenaariumid ja valiveerija reeglid.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

## Ekraanitõmmised

<details>
<summary>Vajuta avamiseks</summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>
