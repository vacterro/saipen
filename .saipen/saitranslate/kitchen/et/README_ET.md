<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Jätkuvusprotokoll AI koodimisagentidele.** SAIPEN hoiab projekti mälu tavalises markdown-vormingus, nii et külm agent ilma vestlusajaloota käivitab `/saipen continue`, loeb `STATE`, `BOARD` ja `next_action` ning jätkab tööd alla minutiga — ilma uuesti juhendamata, mis tahes tarnija, mis tahes päeval.

**Üks käsk. Null amneesiat.**

**v7.131.0** | [Spetsifikatsioon](SPEC.md) | [Juhend](GUIDE.md) | [RFC](saipen/RFC.md) | [Stiil](saipen/STYLE.md) | [Kasutajaliides](saipen/UI.md) | [Vastavus](saipen/CONFORMANCE.md) | tavaline markdown | null sõltuvust | MIT

[![Venekeelne juhend](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![Ingliskeelne juhend](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eestikeelne juhend](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Jaapanikeelne juhend](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Vanaisa versiooni juhend](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Kasutaja -> /saipen continue
Agent    -> loeb STATE-faili ("Mida ma praegu teen?")
Agent    -> loeb BOARD-faili ("Mis ülesande ma ette võtan?")
Agent    -> loeb next_action (käivitab käsu)
Agent    -> Töötab.
```

### Projekti olek > Mudeli mälu
Mälu elab projektis, mitte mudeli peas. `Projekt -> Mälu -> LLM` muutub vormi `Projekt -> SAIPENi olek -> LLM`.

### Protokolli põhiloogika ja garantiid
- **Olekumasina tuum**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Autonoomia ilma viibadeta**: Avatud ülesandeid pole? Automaatne üleminek `HUNT` (vigade skaneerimine) → `ADD` (funktsioonide arendus) → `HUNT` tsükkel. Küsimusi ei esitata.
- **Sõnaselged päästikud**: `/saipen plan` (muuda päring või tööloend piletiteks), `/saipen ship` (versioonimine, muudatuste logi, märgis, tõuge), `/saipen clean` (hoidla puhastus), `/saipen translate` (isoleeritud `.saipen/saitranslate/` tehas), `/saipen markhunt` (kuiv piiramatu audit, ainult kirjed), `/saipen prepare` (töö pakendamine üleandmiseks), `/saipen validate` (vastavuskontroll), `/saipen goal` (autonoomne lainerünnak). Meta/juhtimine: `/saipen status` (kirjutuskaitstud aruanne), `/saipen stop` (kontrollpunkt ja peatus). Lisaks `saipen set` ja `saipen continue` — kokku kaksteist käsku, täielik loend: RFC.md § 1.10.
- **Range töökindlus**: Partii sisendi parsimine (kirurgilised 1-kaupa piletid), määrdunud puu omaksvõtt (ei kustuta kunagi salvestamata tööd), saladuste redigeerimine (`sk-***`).
- **Eksperimentaalne -- saicrew**: valikuline boonuskiht (`extensions/subs/`, Core'i muudatusteta) mitme agendiga meeskonna käivitamiseks — üks Core'i kirjutaja pluss kirjutuskaitstud `saihunt`/`saipython` töötajad, kes aruandlevad oma `OUTBOX.md` kaudu. Aktiivse reaalajas testimise all, lõpuni kinnitamata — vaata `extensions/subs/crew.md`.

## Projektid, mida käitab SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Kõrge jõudlusega viipade haldamise tööriist, mis on ehitatud SAIPENi mäluprotokolli ümber.

## Kaks kihti

| Kiht | Nõutav | Eesmärk |
|---|---|---|
| **Tuum** | ✅ | Jätka tööd turvaliselt |
| **Hooldus** | Tuuma peal | Arenda tarkvara edasi ilma ülesanneteta |

**Automatiseeritud evolutsioon.** Avatud ülesandeid ei ole järel, trüki `/saipen`: `HUNT` auditeerib vigade, surnud koodi ja ebaõnnestunud testide suhtes. Puhas? `ADD` ehitab järgmise ilmse puuduva võimekuse, kontrollib seda ja jahib uuesti. Toode on valmis -> peatub sujuvalt.

**GOAL-režiim.** `/saipen goal <mida soovid>` pöörab tahvlit (vanad piletid viiakse madalamale prioriteedile, aga ei kustutata kunagi) ja viib uue eesmärgi edasi — ilma piletite vahel "kas ma peaksin jätkama?" küsimata, VERIFY/REVIEW ei jäeta kunagi vahele. SHIP teeb automaatse push-i olemasolevasse kaughoidlasse; täiesti uus hoidla küsib siiski ühe korra. Eesmärgi tarnimine pole samuti lõpp-punkt — see läheb otse autonoomse HUNT/ADD hoolduse alla, kuni toode on küps, blokeeritud või käivitus jõuab oma piirini (3 lainet / 20 piletit, seejärel teeb kontrollpunkti ja aruande).

## Kiire alustus

**1. Paigalda üks kord masina kohta** — õpetab Claude Code'i, Codex'i, Geminit, OpenCode'i, Aiderit, Antigravityt ja iga üldine `~/.agents/skills`-lugeja (FreeBuff, jne.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>Mida see puudutab, et üllatusi poleks: skript lisab märgistatud ploki `<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->` teie agendi juhendfailidesse (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`, `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`) — tehes enne varukoopia `.bak` — ja kopeerib protokolli vastavatesse oskuste kaustadesse. Mitte midagi väljaspool neid teid, ei deemonit, ei võrgukutseid.</sub>

**Kahetsed otsust?** Üks käsk võtab tagasi:
```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```
See eemaldab täpselt märgistatud ploki (jättes ülejäänud faili puutumata), salvestab enne koopia `.uninstalled.bak` ja eemaldab oskuste kaustad.

**2. Alusta projekti** — ava agent oma kaustas ja trüki:
> `saipen set`

Pole paigaldatud? Kleebi üks rida mis tahes agendile:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Platvormi pole ülaltoodud loendis (DeepSeek, Qwen, eraldiseisev OpenAI jne)?
Platvormipõhised märkused asuvad kaustas `extensions/adapters/`.

## Dokumentatsiooni ja spetsifikatsiooni lingid
- **[SPEC.md](SPEC.md)** — ametlik arhitektuur, disainieesmärgid, lakmustest.
- **[RFC.md](saipen/RFC.md)** — normatiivne spetsifikatsioon, mida agendid täidavad.
- **[GUIDE.md](GUIDE.md)** — inimetuutor ja ELI5 juhendid:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** — agendi suhtlusstiil ja hääle määratlus.
- **[UI.md](saipen/UI.md)** — Tume Kuldne Win95 UI disainijuhised.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** — käitumuslikud testistsenaariumid ja validaatori reeglid.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>


