<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Jätkamisprotokoll AI kodeerimisagentidele.** Püsiv projekti mälu lihtsas markdownis, nii et külm agent ilma vestlusajaloota käivitab `/saipen continue` ja jätkab tööd vähem kui minutiga -- pole vaja uut briifingut, sõltumata tarnijast või päevast.

**Üks käsk. Null amneesiat.**

**v7.41.0** | [Spetsifikatsioon](SPEC_EE.md) | [Juhend](GUIDE.md) | [RFC](saipen/RFC_EE.md) | [Stiil](saipen/STYLE_EE.md) | [UI](saipen/UI.md) | [Vastavus](saipen/CONFORMANCE.md) | lihtne markdown | null sõltuvust | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Kasutaja  ->  /saipen continue
Agent ->  loeb STATE ("Mida ma praegu teen?")
Agent ->  loeb BOARD ("Millise ülesande ma võtan?")
Agent ->  loeb next_action (käivitab käsu)
Agent ->  Töötab.
```

### Projekti Olek > Mudeli Mälu
Mälu elab projektis, mitte mudeli peas. `Projekt -> Mälu -> LLM` muutub `Projekt -> SAIPEN Olek -> LLM`.

### Võtmeprotokolli Loogika & Garantiid
- **Tuumikolekumasin**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Null-viiba Autonoomia**: Töölaud tühi? Automaatne üleminek `HUNT` (otsi vigu) → `ADD` (arenda funktsioone) → `HUNT` tsükkel. Ühtegi küsimust ei küsita.
- **Selged Päästikud**: `/saipen clean` (repositooriumi puhastus), `/saipen translate` (isoleeritud `.saipen/saitranslate/` tehas), `/saipen validate` (vastavuskontroll), `/saipen goal` (autonoomne laine täitmine).
- **Range Töökindlus**: Partii sisendi parsimine (kirurgilised 1-haaval piletid), räpase puu omaksvõtt (ei kustuta kunagi salvestamata tööd), saladuste eemaldamine (`sk-***`).

## Projektid, millel on SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Kõrge jõudlusega viipade haldamise tööriist, mis on integreeritud SAIPEN-i mäluprotokolliga.

## Kaks Kihti

| Kiht | Nõutud | Eesmärk |
|---|---|---|
| **Tuumik** | ✅ | Töö turvaline jätkamine |
| **Hooldus** | Tuumiku peal | Tarkvara arendamine ilma ülesannete andmiseta |

**Automaatne Areng.** Töölaud tühi, trüki `/saipen`: `HUNT` auditeerib vigu, surnud koodi, ebaõnnestunud teste. Puhas? `ADD` ehitab järgmise ilmselge puuduva võimekuse, kontrollib seda, otsib uuesti. Toode on küps -> peatub graatsiliselt.

**GOAL Režiim.** `/saipen goal <mida soovid>` pöörab töölauda (vanad piletid degradeeritakse, ei kustutata kunagi) ja viib uue eesmärgi edasi -- piletite vahel pole "kas jätkan?", VERIFY/REVIEW ei jäeta kunagi vahele. SHIP lükkab automaatselt olemasolevasse kaugreposse; täiesti uus repo küsib siiski ühe korra. Eesmärgi kohaletoimetamine ei ole samuti peatumispunkt -- see langeb otse autonoomsesse HUNT/ADD hooldusesse, kuni toode on küps, blokeeritud või jooks saavutab oma piiri (3 lainet / 20 piletit, siis teeb kontrollpunkti ja raporteerib).

## Kiirjuhend

**1. Paigalda üks kord masina kohta** -- õpetab Claude Code'i, Geminit, OpenCode'i, Aiderit, Antigravityt:
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Alusta projekti** -- ava agent oma kaustas, trüki:
> `saipen set`

Pole installitud? Kleebi üks rida mis tahes agendile:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Platvormi pole ülaltoodud nimekirjas (DeepSeek, Qwen, eraldiseisev OpenAI jne)?
Platvormipõhised märkused asuvad kaustas `extensions/adapters/`.

## Dokumentatsiooni & Spetsifikatsiooni Lingid
- **[SPEC.md](SPEC_EE.md)** -- formaalne arhitektuur, disaini eesmärgid, lakmuspaber.
- **[RFC.md](saipen/RFC_EE.md)** -- normatiivne spetsifikatsioon agentide täitmiseks.
- **[GUIDE.md](GUIDE.md)** -- inimeste õpetus & ELI5 juhendid:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE_EE.md)** -- agendi suhtlusstiili & hääle definitsioon.
- **[UI.md](saipen/UI.md)** -- Dark Golden Win95 kasutajaliidese disainijuhised.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- käitumuslikud testistsenaariumid & validaatori reeglid.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
