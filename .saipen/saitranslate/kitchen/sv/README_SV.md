<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Fortsättningsprotokoll för AI-kodningsagenter.** Beständigt projektminne i
ren markdown, så att en kall agent utan chatthistorik kör `/saipen continue`
och återupptar arbetet på under en minut -- ingen re-briefing, vilken leverantör som helst, vilken dag som helst.

**Ett kommando. Noll amnesi.**

**Snabbkommandon:** `cc` fortsätter en aktiv Goal Mode-körning, `sss` visar status utan att röra koden och `ss` sparar en kontrollpunkt och stannar. [Se hela 13-tangentkartan](saipen/RFC.md#110-command-surface). Kyrilliska tvillingar fungerar också: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Svarspråk.** Agenten svarar som standard **på estniska** — det är en inställning, inte en egenhet, och inget annat i SAIPEN är estniskt. Ändras på ett ställe: raden `reply_language:` överst i [`saipen/STYLE.md`](saipen/STYLE.md). `et` estniska, `en` engelska, `ru` ryska, `auto` väljer utifrån språket i ditt meddelande. Protokollet, koden, commits och alla dokument förblir engelska vid varje värde.

**v7.178.0** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [RFC](saipen/RFC.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) | ren markdown | noll beroenden | MIT

```text
User  ->  /saipen continue
Agent ->  läser STATE ("Vad gör jag just nu?")
Agent ->  läser BOARD ("Vilken uppgift tar jag upp?")
Agent ->  läser next_action (utför kommando)
Agent ->  Arbetar.
```

### Projektstatus > Modellminne
Minnet lever i projektet, inte i en modells huvud. `Projekt -> Minne -> LLM` blir `Projekt -> SAIPEN Tillstånd -> LLM`.

### Viktig protokolllogik & garantier
- **Kärntillståndsmaskin**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Noll-prompt autonomi**: Inga öppna att-göra kvar? Auto-övergår `HUNT` (skanna buggar) → `ADD` (utveckla funktioner) → `HUNT`-slinga. Noll frågor ställda.
- **Explicita utlösare**: `/saipen clean` (rensa repo), `/saipen translate` (isolerad `.saipen/saitranslate/`-fabrik), `/saipen markhunt` (torr obegränsad granskning, sparar endast fynd), `/saipen prepare` (paketera arbete för överlämning), `/saipen validate` (konformitetskontroll), `/saipen goal` (autonom våg-exekvering). Meta/kontroll: `/saipen status` (skrivskyddad rapport), `/saipen stop` (spara kontrollpunkt och stanna). Fullständig lista: RFC.md § 1.10.
- **Strikt tillförlitlighet**: Satsvis indataparsning (kirurgiska 1-och-1-ärenden), hantering av smutsiga träder (raderar aldrig ocommittat arbete), redaction av hemligheter (`sk-***`).

## Projekt som drivs av SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Högpresterande prompt-hanteringsverktyg nativt integrerat med SAIPEN-minnesprotokollet.

## Två lager

| Lager | Krävs | Syfte |
|---|---|---|
| **Kärna** | ✅ | Fortsätt arbetet säkert |
| **Underhåll** | Ovanpå kärna | Utveckla programvaran utan manuell uppdelning |

**Automatiskt åldrande/utveckling.** Inga öppna att-göra kvar, skriv `/saipen`: `HUNT` granskar efter buggar, död kod, misslyckade tester. Rent? `ADD` bygger nästa uppenbara saknade funktion, verifierar den, jagar igen. Produkten är mogen -> stannar graciöst.

**GOAL-läge.** `/saipen goal <vad du vill ha>` svänger brädan (gamla ärenden nedgraderade, aldrig raderade) och driver det nya målet framåt -- inget "ska jag fortsätta?" mellan ärenden, VERIFY/REVIEW hoppas aldrig över. SHIP auto-pushar till en befintlig remote; ett helt nytt repo frågar fortfarande en gång. Att skicka målet är inte heller slutpunkten -- det faller direkt in i autonomt HUNT/ADD-underhåll tills produkten är mogen, blockerad, eller körningen når sin gräns (3 vågor / 20 ärenden, därefter kontrollpunkt och rapport).

## Snabbstart

**1. Installera en gång per maskin** -- lär Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex och alla generiska ~/.agents/skills-lasare (FreeBuff, etc.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Starta ett projekt** -- öppna en agent i din mapp, skriv:
> `saipen set`

Ingen installation? Klistra in en rad till valfri agent:
> Läs <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md och följ dem.

Plattformen finns inte i listan ovan (DeepSeek, Qwen, fristående OpenAI, etc.)?
Plattformsspecifika anteckningar finns i `extensions/adapters/`.

## Dokumentation & specifikationslänkar
- **[SPEC.md](SPEC.md)** -- formell arkitektur, designmål, lakmustest.
- **[RFC.md](saipen/RFC.md)** -- normativ specifikation som utförs av agenter.
- **[GUIDE.md](GUIDE.md)** -- mänsklig handledning & ELI5-guider:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- agentens kommunikationsstil & röstdefinition.
- **[UI.md](saipen/UI.md)** -- Mörkguldiga Win95 UI-designriktlinjer.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- beteendetestfall & valideringsregler.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

## ## Skärmbilder

<details>
<summary>Klicka för att expandera</summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff-agentinstruktioner" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set i nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen-skärmbild 2026-08-01" width="600"/>

</details>
