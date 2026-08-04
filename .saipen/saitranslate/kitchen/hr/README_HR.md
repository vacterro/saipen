<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Protokol nastavka za AI agente za kodiranje.** Trajna memorija projekta u
čistom markdownu, tako da hladni agent bez povijesti razgovora pokreće `/saipen continue`
i nastavlja rad za manje od minute -- bez ponovnog brifiranja, bilo koji pružatelj, bilo koji dan.

**Jedna naredba. Nula amnezije.**

**Brzi prečaci:** `cc` nastavlja aktivni Goal Mode, `sss` prikazuje status bez diranja koda, a `ss` sprema kontrolnu točku i zaustavlja se. [Pogledaj punu kartu od 13 tipki](saipen/RFC.md#110-command-surface). Ćirilični blizanci također rade: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Jezik odgovora.** Agent prema zadanim postavkama odgovara **na estonskom** — to je postavka, a ne hir, i ništa drugo u SAIPEN-u nije estonsko. Mijenja se na jednom mjestu: redak `reply_language:` na vrhu [`saipen/STYLE.md`](saipen/STYLE.md). `et` estonski, `en` engleski, `ru` ruski, `auto` bira prema jeziku tvoje poruke. Protokol, kod, commitovi i svi dokumenti ostaju na engleskom pri svakoj vrijednosti.

**v7.179.0** | [Spec](SPEC.md) | [Vodič](GUIDE.md) | [RFC](saipen/RFC.md) | [Stil](saipen/STYLE.md) | [Korisničko sučelje](saipen/UI.md) | [Sukladnost](saipen/CONFORMANCE.md) | čist markdown | nula ovisnosti | MIT

```text
Korisnik ->  /saipen continue
Agent    ->  čita STATE ("Što radim upravo sada?")
Agent    ->  čita BOARD ("Koji zadatak preuzimam?")
Agent    ->  čita next_action (izvršava naredbu)
Agent    ->  Radi.
```

### Stanje projekta > Memorija modela
Memorija živi u projektu, a ne u glavi modela. `Projekt -> Memorija -> LLM` postaje `Projekt -> SAIPEN Stanje -> LLM`.

### Ključna logika protokola i jamstva
- **Jezgreni automat stanja**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Autonomija bez uputa**: Nema otvorenih zadataka? Automatski prijelaz u `HUNT` (skeniranje bugova) → `ADD` (razvoj značajki) → `HUNT` petlju. Bez postavljanja pitanja.
- **Eksplicitni okidači**: `/saipen clean` (čišćenje repozitorija), `/saipen translate` (izolirana `.saipen/saitranslate/` tvornica), `/saipen markhunt` (suhi neograničeni auditi, samo bilježi), `/saipen prepare` (pakiranje rada za predaju), `/saipen validate` (provjera sukladnosti), `/saipen goal` (autonomno valno izvršavanje). Meta/kontrola: `/saipen status` (izvješće samo za čitanje), `/saipen stop` (točka provjere i zaustavljanje). Puni popis: RFC.md § 1.10.
- **Stroga pouzdanost**: Skupno raščlanjivanje unosa (kirurški 1-po-1 zadaci), prihvaćanje nečistog stabla (nikada ne briše nepredani rad), redakcija tajni (`sk-***`).

## Projekti pokretani SAIPEN-om
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Alat za upravljanje promptovima visokih performansi izvorno integriran sa SAIPEN memorijskim protokolom.

## Dva sloja

| Sloj | Obavezno | Svrha |
|---|---|---|
| **Jezgra (Core)** | ✅ | Siguran nastavak rada |
| **Održavanje** | Povrh Jezgre | Razvoj softvera bez zadavanja zadataka |

**Automatizirani razvoj.** Nema preostalih otvorenih zadataka, upišite `/saipen`: `HUNT` auditira bugove, mrtvi kod, neuspjele testove. Čisto? `ADD` gradi sljedeću očitu nedostajuću mogućnost, verificira je, ponovno lovi. Proizvod je zreo -> dostojanstveno se zaustavlja.

**GOAL Način.** `/saipen goal <što želite>` zakreće ploču (stari zadaci degradirani, nikada izbrisani) i gura novi cilj naprijed -- bez "trebam li nastaviti?" između zadataka, VERIFY/REVIEW se nikada ne preskaču. SHIP automatski gura na postojeći udaljeni repozitorij; potpuno novi repozitorij i dalje pita jednom. Slanje cilja također nije točka zaustavljanja -- prelazi izravno u autonomno HUNT/ADD održavanje dok proizvod ne postane zreo, blokiran ili dok pokretanje ne dostigne svoje ograničenje (3 vala / 20 zadataka, zatim stvara točku provjere i izvještava).

## Brzi početak

**1. Instalirajte jednom po računalu** -- uči Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex i bilo koji genericki citac ~/.agents/skills (FreeBuff, itd.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Pokrenite projekt** -- otvorite agenta u svojoj mapi, upišite:
> `saipen set`

Nema instalacije? Zalijepite jedan redak bilo kojem agentu:
> Čitaj <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md i slijedi ih.

Platforma nije na gornjem popisu (DeepSeek, Qwen, samostalni OpenAI, itd.)?
Bilješke po platformi nalaze se u `extensions/adapters/`.

## Veze na dokumentaciju i specifikacije
- **[SPEC.md](SPEC.md)** -- formalna arhitektura, ciljevi dizajna, lakmus test.
- **[RFC.md](saipen/RFC.md)** -- normativna specifikacija koju izvršavaju agenti.
- **[GUIDE.md](GUIDE.md)** -- ljudski tutorijal i ELI5 vodiči:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- stil komunikacije agenta i definicija glasa.
- **[UI.md](saipen/UI.md)** -- smjernice za dizajn Vintage Golden korisničkog sučelja.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- scenariji ispitivanja ponašanja i pravila validatora.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

## ## Snimke zaslona

<details>
<summary>Klikni za proširivanje</summary>

<img src="assets/screenshot-freebuff.png" alt="Upute za FreeBuff agenta" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set u nomadcodeu" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="Snimka zaslona saipen 2026-08-01" width="600"/>

</details>
