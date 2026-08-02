<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Kontinueringsprotokoll for AI-kodingagenter.** Vedvarende prosjektminne i
ren markdown, slik at en kald agent uten prathistorikk kjører `/saipen continue`
og gjenopptar arbeidet på under ett minutt -- ingen ny brifing, hvilken som helst leverandør, hvilken som helst dag.

**Én kommando. Null hukommelsestap.**

**Hurtigtaster:** `cc` fortsetter en aktiv Goal Mode-kjøring, `sss` viser status uten å røre koden, og `ss` lagrer et sjekkpunkt og stopper. [Se hele 13-tasters kartet](saipen/RFC.md#110-command-surface). Kyrilliske tvillinger fungerer også: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**v7.170.0** | [Spesifikasjon](SPEC.md) | [Guide](GUIDE.md) | [RFC](saipen/RFC.md) | [Stil](saipen/STYLE.md) | [UI](saipen/UI.md) | [Samsvar](saipen/CONFORMANCE.md) | ren markdown | null avhengigheter | MIT

[![Russisk guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![Engelsk guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Estisk guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japansk guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Bestefarsstemme](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Bruker ->  /saipen continue
Agent  ->  leser STATE ("Hva gjør jeg akkurat nå?")
Agent  ->  leser BOARD ("Hvilken oppgave henter jeg?")
Agent  ->  leser next_action (utfører kommando)
Agent  ->  Jobber.
```

### Prosjettilstand > Modellminne
Minnet lever i prosjektet, ikke i hodet til en modell. `Prosjekt -> Minne -> LLM` blir `Prosjekt -> SAIPEN-tilstand -> LLM`.

### Sentral protokolllogikk og garantier
- **Kjernetilstandsmaskin**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Autonomi uten instruksjoner**: Ingen åpne oppgaver igjen? Automatisk overgang `HUNT` (skann feil) → `ADD` (utvikle funksjoner) → `HUNT`-sløyfe. Null spørsmål stilt.
- **Eksplisitte utløsere**: `/saipen clean` (opprydding i arkiv), `/saipen translate` (isolert `.saipen/saitranslate/`-fabrikk), `/saipen markhunt` (tørr ubegrenset revisjon, kun registrering), `/saipen prepare` (pakk arbeid for overlevering), `/saipen validate` (samsvarskontroll), `/saipen goal` (autonom bølgeutførelse). Meta/kontroll: `/saipen status` (skrivebeskyttet rapport), `/saipen stop` (sjekkpunkt og stans). Fullstendig liste: RFC.md § 1.10.
- **Strenget pålitelighet**: Batch-inndataparsing (kirurgiske 1-og-1 oppgaver), adopsjon av skittent tre (sletter aldri uendret arbeid), hemmelighetsredigering (`sk-***`).

## Prosjekter drevet av SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Høytytelses verktøy for prompt-håndtering sømløst integrert med SAIPEN sin minneprotokoll.

## To lag

| Lag | Påkrevd | Formål |
|---|---|---|
| **Kjerne** | ✅ | Fortsett arbeidet trygt |
| **Vedlikehold** | Oppå kjernen | Videreutvikle programvaren uten oppgaver |

**Automatisert utvikling.** Ingen åpne oppgaver igjen, skriv `/saipen`: `HUNT` reviderer for feil, død kode, feilende tester. Rent? `ADD` bygger neste åpenbare manglende funksjonalitet, verifiserer den, og jakter igjen. Produktet er modent -> stopper grasiøst.

**GOAL-modus.** `/saipen goal <hva du vil>` omstrukturerer brettet (gamle oppgaver nedprioriteres, aldri slettes) og driver det nye målet fremover -- ingen "skal jeg fortsette?" mellom oppgaver, VERIFY/REVIEW hoppes aldri over. SHIP automatisk skyver til et eksisterende eksternt arkiv; et helt nytt arkiv spør fremdeles én gang. Å levere målet er heller ikke sluttpunktet -- det går rett over i autonomt HUNT/ADD-vedlikehold til produktet er modent, blokkert, eller kjøringen når sin grense (3 bølger / 20 oppgaver, deretter sjekkpunkter og rapporter).

## Hurtigstart

**1. Installer én gang per maskin** -- lærer Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex og enhver generisk ~/.agents/skills-leser (FreeBuff, etc.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Start et prosjekt** -- åpne en agent i mappen din, skriv:
> `saipen set`

Ingen installasjon? Lim inn én linje til hvilken som helst agent:
> Les <klon>/saipen/RFC.md + <klon>/saipen/STYLE.md og følg dem.

Plattform ikke i listen ovenfor (DeepSeek, Qwen, frittstående OpenAI, osv.)?
Plattformspesifikke notater finnes i `extensions/adapters/`.

## Dokumentasjon og spesifikasjonslenker
- **[SPEC.md](SPEC.md)** -- formell arkitektur, designmål, lakmustest.
- **[RFC.md](saipen/RFC.md)** -- normativ spesifikasjon utført av agenter.
- **[GUIDE.md](GUIDE.md)** -- menneskelig veiledning og ELI5-guider:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- kommunikasjonsstil og stemmedefinisjon for agenter.
- **[UI.md](saipen/UI.md)** -- retningslinjer for Mørk Gylden Win95 UI-design.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- atferdsmessige testscenarier og valideringsregler.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

