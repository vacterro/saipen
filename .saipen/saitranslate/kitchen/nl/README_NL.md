<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Continuïteitsprotocol voor AI-coderingsagenten.** Permanent projectgeheugen in
plat markdown, zodat een koude agent zonder chatgeschiedenis `/saipen continue` uitvoert
en het werk in minder dan een minuut hervat -- geen herbriefing, elke leverancier, elke dag.

**Eén commando. Nul amnesie.**

**v7.145.0** | [Spec](SPEC.md) | [Gids](GUIDE.md) | [RFC](saipen/RFC.md) | [Stijl](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformiteit](saipen/CONFORMANCE.md) | plat markdown | nul afhankelijkheden | MIT

[![Russische Gids](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![Engelse Gids](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Estse Gids](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanse Gids](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Opa Stem](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Gebruiker ->  /saipen continue
Agent     ->  leest STATE ("Wat doe ik nu?")
Agent     ->  leest BOARD ("Welke taak pak ik op?")
Agent     ->  leest next_action (voert commando uit)
Agent     ->  Werkt.
```

### Projectstatus > Modelgeheugen
Geheugen leeft in het project, niet in het hoofd van een model. `Project -> Geheugen -> LLM` wordt `Project -> SAIPEN Status -> LLM`.

### Kernprotocollogica & Garanties
- **Kern Statusmachine**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Nul-Prompt Autonomie**: Geen open to-do's meer? Automatische overgang `HUNT` (scant op bugs) → `ADD` (ontwikkelt functies) → `HUNT` lus. Nul vragen gesteld.
- **Expliciete Triggers**: `/saipen clean` (repo opschonen), `/saipen translate` (geïsoleerde `.saipen/saitranslate/` fabriek), `/saipen markhunt` (droge onbegrensde audit, legt alleen vast), `/saipen prepare` (verpak werk voor overdracht), `/saipen validate` (conformiteitscontrole), `/saipen goal` (autonome golfuitvoering). Meta/besturing: `/saipen status` (alleen-lezen rapport), `/saipen stop` (checkpoint en stop). Volledige lijst: RFC.md § 1.10.
- **Strikte Betrouwbaarheid**: Batch-invoerparsing (chirurgische 1-voor-1 tickets), dirty-tree adoptie (wist nooit niet-gecommitteerd werk), redactie van geheimen (`sk-***`).
- **In ontwikkeling -- saicrew**: een optionele bonuslaag (`extensions/subs/`, zonder wijzigingen aan Core) voor het draaien van een multi-agent crew -- één Core-schrijver plus read-only workers `saihunt`/`saipython`, die rapporteren via hun eigen `OUTBOX.md`. Momenteel actief live getest, nog niet end-to-end geverifieerd -- zie `extensions/subs/crew.md`.

## Projecten Aangedreven door SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Hoogwaardige promptbeheertool die native is geïntegreerd met het SAIPEN-geheugenprotocol.

## Twee Lagen

| Laag | Vereist | Doel |
|---|---|---|
| **Kern** | ✅ | Werk veilig hervatten |
| **Onderhoud** | Bovenop Kern | De software verder ontwikkelen zonder taaktoewijzing |

**Geautomatiseerde Evolutie.** Geen open to-do's meer, typ `/saipen`: `HUNT` auditeert op bugs, dode code, mislukte tests. Schoon? `ADD` bouwt de volgende logische ontbrekende functionaliteit, verifieert deze en voert opnieuw een hunt uit. Product is volwassen -> stopt netjes.

**GOAL-modus.** `/saipen goal <wat je wilt>` verplaatst het bord (oude tickets worden gedegradeerd, nooit verwijderd) en leidt het nieuwe doel voorwaarts -- geen "zal ik doorgaan?" tussen tickets, VERIFY/REVIEW wordt nooit overgeslagen. SHIP pusht automatisch naar een bestaande remote; een gloednieuwe repo vraagt één keer. Het doel verzenden is ook niet het eindpunt -- het gaat direct over in autonoom HUNT/ADD-onderhoud totdat het product volwassen is, geblokkeerd raakt, of de run zijn limiet bereikt (3 golven / 20 tickets, daarna checkpoints en rapportage).

## Snelle Start

**1. Eenmalig installeren per machine** -- leert Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex en elke generieke ~/.agents/skills-lezer (FreeBuff, etc.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Start een project** -- open een agent in je map, typ:
> `saipen set`

Geen installatie? Plak één regel in elke agent:
> Lees <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md en volg ze op.

Platform niet in de bovenstaande lijst (DeepSeek, Qwen, standalone OpenAI, enz.)?
Notities per platform zijn te vinden in `extensions/adapters/`.

## Documentatie & Specificatielinks
- **[SPEC.md](SPEC.md)** -- formele architectuur, ontwerpdoelen, lakmoestest.
- **[RFC.md](saipen/RFC.md)** -- normatieve specificatie uitgevoerd door agenten.
- **[GUIDE.md](GUIDE.md)** -- menselijke handleiding & ELI5-gidsen:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- communicatiestijl & stemdefinitie van agent.
- **[UI.md](saipen/UI.md)** -- Vintage Golden UI-ontwerprichtlijnen.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- gedragstestscenario's & validatorregels.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>


