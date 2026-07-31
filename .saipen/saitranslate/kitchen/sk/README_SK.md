<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Protokol pokračovania pre AI kódovacích agentov.** Kontinuálna pamäť projektu v čistom markdown, takže studený agent bez histórie chatu spustí `/saipen continue` a pokračuje v práci za menej ako minútu -- žiadne opätovné inštruovanie, akýkoľvek dodávateľ, akýkoľvek deň.

**Jeden príkaz. Nulová amnézia.**

**v7.144.0** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [RFC](saipen/RFC.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) | čistý markdown | nulové závislosti | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
User  ->  /saipen continue
Agent ->  reads STATE ("What do I do right now?")
Agent ->  reads BOARD ("What task am I picking up?")
Agent ->  reads next_action (executes command)
Agent ->  Works.
```

### Stav projektu > Pamäť modelu
Pamäť žije v projekte, nie v hlave modelu. `Projekt -> Pamäť -> LLM` sa mení na `Projekt -> SAIPEN Stav -> LLM`.

### Kľúčová logika protokolu a záruky
- **Jadrový stavový stroj**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Autonómia bez výziev**: Neostali žiadne otvorené úlohy? Automatický prechod `HUNT` (skenovanie chýb) → `ADD` (rozvoj funkcií) → `HUNT` slučka. Žiadne otázky.
- **Explicitné spúšťače**: `/saipen clean` (vyčistenie repozitára), `/saipen translate` (izolovaná `.saipen/saitranslate/` továreň), `/saipen markhunt` (suchý neobmedzený audit, iba záznamy), `/saipen prepare` (zabaliť prácu na odovzdanie), `/saipen validate` (kontrola zhody), `/saipen goal` (autonómne vykonanie vlny). Meta/riadenie: `/saipen status` (správa len na čítanie), `/saipen stop` (uloženie stavu a zastavenie). Úplný zoznam: RFC.md § 1.10.
- **Prísna spoľahlivosť**: Dávkové spracovanie vstupov (chirurgické tikety po 1), prevzatie špinavého stromu (nikdy nezmaže neuloženú prácu), redakcia tajomstiev (`sk-***`).

## Projekty poháňané SAIPENom
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Vysoko výkonný nástroj na správu promptov natívne integrovaný s pamäťovým protokolom SAIPEN.

## Dve vrstvy

| Vrstva | Vyžadovaná | Účel |
|---|---|---|
| **Jadro (Core)** | ✅ | Bezpečné pokračovanie v práci |
| **Údržba (Maintenance)** | Nad Jadrom | Rozvoj softvéru bez zadávania úloh |

**Automatizovaná evolúcia.** Neostali žiadne otvorené úlohy, napíšte `/saipen`: `HUNT` vykoná audit chýb, mŕtveho kódu, zlyhávajúcich testov. Čisto? `ADD` vybuduje ďalšiu očividne chýbajúcu schopnosť, overí ju a znova spustí hunt. Keď je produkt zrelý -> elegantne sa zastaví.

**Režim GOAL.** `/saipen goal <čo chcete>` presmeruje nástenku (staré tikety sú odsunuté, nikdy nezmazané) a posúva nový cieľ vpred -- žiadne "mám pokračovať?" medzi tiketmi, VERIFY/REVIEW sa nikdy nevysadia. SHIP automaticky odosiela do existujúceho vzdialeného repozitára; úplne nový repozitár sa stále raz opýta. Odoslanie cieľa však nie je konečným bodom -- prechádza priamo do autonómnej údržby HUNT/ADD, kým nie je produkt zrelý, zablokovaný, alebo kým beh nedosiahne svoj limit (3 vlny / 20 tiketov, potom uloží stav a podá správu).

## Rýchly štart

**1. Inštalácia raz na zariadenie** -- naučí Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex a akykolvek vseobecny citac ~/.agents/skills (FreeBuff, atd.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Spustenie projektu** -- otvorte agenta vo svojom priečinku a napíšte:
> `saipen set`

Bez inštalácie? Vložte jeden riadok akémukoľvek agentovi:
> Prečítaj <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md a riaď sa jimi.

Platforma nie je v zozname vyššie (DeepSeek, Qwen, samostatné OpenAI atď.)?
Poznámky pre jednotlivé platformy sa nachádzajú v `extensions/adapters/`.

## Odkazy na dokumentáciu a špecifikáciu
- **[SPEC.md](SPEC.md)** -- formálna architektúra, dizajnové ciele, lakmusový test.
- **[RFC.md](saipen/RFC.md)** -- normatívna špecifikácia vykonávaná agentmi.
- **[GUIDE.md](GUIDE.md)** -- ľudský návod & ELI5 príručky:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- komunikačný štýl agenta & definícia hlasu.
- **[UI.md](saipen/UI.md)** -- pravidlá UI dizajnu Tmavé Zlato Win95.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- testovacie scenáre správania & pravidlá validátora.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>


