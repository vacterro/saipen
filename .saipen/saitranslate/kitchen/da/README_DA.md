<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Kontinuitetsprotokol til AI-kodeagenter.** Vedvarende projekthukommelse i ren markdown, så en kold agent uden chathistorik kører `/saipen continue` og genoptager arbejdet på under et minut -- ingen ny instruktion, enhver udbyder, enhver dag.

**Én kommando. Nul amnesi.**

**v7.84.0** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [RFC](saipen/RFC.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) | ren markdown | nul afhængigheder | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Bruger ->  /saipen continue
Agent  ->  læser STATE ("Hvad gør jeg lige nu?")
Agent  ->  læser BOARD ("Hvilken opgave tager jeg op?")
Agent  ->  læser next_action (udfører kommando)
Agent  ->  Arbejder.
```

### Projekttilstand > Modelhukommelse
Hukommelse lever i projektet, ikke i en models hoved. `Projekt -> Hukommelse -> LLM` bliver til `Projekt -> SAIPEN-tilstand -> LLM`.

### Nøgleprotokollogik og garantier
- **Kernetilstandsmaskine**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Nul-prompt autonomi**: Ingen åbne to-dos tilbage? Automatisk overgang `HUNT` (skan fejl) → `ADD` (udvikl funktioner) → `HUNT` løkke. Nul spørgsmål stillet.
- **Eksplicitte udløsere**: `/saipen clean` (repo-oprydning), `/saipen translate` (isoleret `.saipen/saitranslate/`-fabrik), `/saipen markhunt` (tør ubegrænset audit, registrerer kun), `/saipen prepare` (pak arbejdet til overdragelse), `/saipen validate` (overholdelseskontrol), `/saipen goal` (autonom bølgeeksekvering). Meta/kontrol: `/saipen status` (skrivebeskyttet rapport), `/saipen stop` (kontrolpunkt og stop). Fuld liste: RFC.md § 1.10.
- **Streng pålidelighed**: Batch-inputparsing (kirurgiske 1-til-1 opgaver), adoptiv håndtering af snavset træ (sletter aldrig u-committed arbejde), hemmelighedscensur (`sk-***`).

## Projekter drevet af SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Højtydende prompt-styringsværktøj indbygget integreret med SAIPEN-hukommelsesprotokollen.

## To lag

| Lag | Påkrævet | Formål |
|---|---|---|
| **Kerne** | ✅ | Fortsæt arbejde sikkert |
| **Vedligeholdelse** | Ovenpå Kernen | Udvikl softwaren uden opgaveangivelse |

**Automatiseret evolution.** Ingen åbne to-dos tilbage, skriv `/saipen`: `HUNT` auditerer for fejl, død kode, fejlende tests. Rent? `ADD` bygger den næste oplagte manglende funktion, verificerer den, og jagter igen. Produktet er modent -> stopper graciøst.

**GOAL-tilstand.** `/saipen goal <hvad du ønsker>` drejer kortet (gamle opgaver nedgraderes, slettes aldrig) og driver det nye mål fremad -- intet "skal jeg fortsætte?" mellem opgaver, VERIFY/REVIEW springes aldrig over. SHIP auto-pusher til en eksisterende remote; et helt nyt repo spørger stadig én gang. Levering af målet er heller ikke stoppestedet -- det falder direkte over i autonom HUNT/ADD-vedligeholdelse, indtil produktet er modent, blokeret, eller kørslen når sin grænse (3 bølger / 20 opgaver, derefter kontrolpunkt og rapportering).

## Hurtig start

**1. Installer én gang pr. maskine** -- lærer Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex og enhver generisk ~/.agents/skills-l?ser (FreeBuff, etc.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Start et projekt** -- åbn en agent i din mappe, skriv:
> `saipen set`

Ingen installation? Indsæt én linje til enhver agent:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Platform ikke på listen ovenfor (DeepSeek, Qwen, fritstående OpenAI, osv.)?
Platformsspecifikke noter findes i `extensions/adapters/`.

## Dokumentations- og specifikationslinks
- **[SPEC.md](SPEC.md)** -- formel arkitektur, designmål, lakmustest.
- **[RFC.md](saipen/RFC.md)** -- normativ specifikation udført af agenter.
- **[GUIDE.md](GUIDE.md)** -- menneskelig vejledning & ELI5-guider:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- agentens kommunikationsstil og stemmedefinition.
- **[UI.md](saipen/UI.md)** -- retningslinjer for Mørk Gylden Win95 UI-design.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- adfærdstestscenarier og valideringsregler.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>


