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

**Fortsettelsesprotokoll for AI-kodingssystemer.**Prosjektminnet finnes i vanlig
Markdown-filer inne i prosjektet(`.saipen/`), slik at enhver kompatibel kald agent —
ingen samtalehistorikk, ingen sesjonsminne — kan kjøre`/saipen continue`, lese
lagret`next_action`, og fortsette arbeid uten å be brukeren om å forklare noe
nå. Tilstanden tilhører prosjektet, ikke til en modellleverandørs minne.

**En kommando for å fortsette. Vanligfiltilstand. Maskinkontrollerte kontrakter.**

Repository-validering skjer hver gang det pushes; install, state, checks, og
avinstallasjon er alle lokale — ingen skytjeneste, ingen daemon, ingen database.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.231.2** | [Spesifikasjon](SPEC.md) | [Veiledning](GUIDE.md) | [Kjerne](saipen/CORE.md) | [Vedlikehold](saipen/MAINTENANCE.md) | [Stil](saipen/STYLE.md) | [UI](saipen/UI.md) | [Konformitet](saipen/CONFORMANCE.md) |MIT

**Hurtigtaster:** `cc` fortsetter prosjektets kontekst til konvergens (gjenopptar et aktivt mål hvis et er satt), `sss` viser status uten å røre koden, og `ss` lagrer et sjekkpunkt og stopper. [Se hele 19-tasters kartet](saipen/RFC.md#110-command-surface). Kyrilliske tvillinger fungerer også: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## Hva som vedvarer

Live prosjektminne finnes i`.saipen/`— vanlige filer du kan lese, diff og
kommitter ved siden av koden. En kald agent svarer på fem spørsmål fra filene
alene:

|Fil / felt|Svar|
|---|---|
| `STATE.md` |Hva skjer akkurat nå?(fase, aktiv billett, driftsmodus, blokkerende faktor) |
| `BOARD.md` |Hva arbeid finnes / hva er aktivt?(billettgraf: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |Hvorfor har prosjektet nådd dette tilstanden?(append-only hendelsesgraf) |
| `KNOWLEDGE/` |Hva er de vedvarende prosjektinformasjonen som må overleve sesjoner?|
| `next_action` (i`STATE.md`) |Hva er den eksakte handlingen neste agent skal utføre?|

Dette er en checkpoint-kontrakt, ikke et designforslag:`saipen stop`og hver
billettovergang skriver filene i en fast rekkefølge, og resultatet sjekkes av
en validerer. Ingenting lagres i en vertshostet database, og ingenting går tapt når en
økt slutter.

## Snarstart

**1. Installer én gang per maskin**— lærer Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity, og hvilken som helst generisk`~/.agents/skills`leser(FreeBuff, osv.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`blokk til agentinstruksjonen
filer du allerede har(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— opprettholder en kopi av`.bak`først —
og kopierer protokollen til de tilsvarende ferdighetsmappene. Ingenting utenfor disse
stier, ingen daemon, ingen nettverkskall.</sub>

**2. Start et prosjekt**— åpne en agent i mappen din, skriv:

> `saipen set`

**Ingen installasjon?**Lim inn en linje til enhver agent:

> Les&lt;clone&gt;/saipen/BOOT.md først(kaldstart kernel), så&lt;clone&gt;/saipen/INDEX.md +&lt;klone&gt;/saipen/STYLE.md og følg dem.

**Har du endret deg?**En kommando setter det tilbake:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Det fjerner akkurat den markerte blokken(og lar resten av filen være alene), lagrer
a `.uninstalled.bak`kopier først, og fjerner ferdighetsmappene.

## Hvorfor ikke bare chat-historikk?

SAIPEN målretter en spesifikk feil: en AI-kodingagent som ikke husker noe
når økta slutter. Andre verktøy og vaner dekker delvis dette problemet:

|Tilnærming|Hva det er god til|Hva det ikke bærer|
|---|---|---|
|Chat historikk / modellminne|Kontant, null konfigurasjon|Avhengig av sesjon og leverandør; ikke lagret med prosjektet, så en kald agent ser aldri på det|
|Statiske`AGENTS.md`/instruksjonsfil|Holdbare stående regler og konvensjoner|Representerer ikke av seg selv live oppgavetilstand`next_action`, eller gjenopprettingshistorikk|
|Problem / TODO-sporet|Oppgave- og backloghåndtering|Definerer ikke av seg selv agentens fortsettelsessemantikk — hva en kald agent må lese og utføre når den fortsetter|
| **SAIPEN** |Live utførelsesstatus, arbeidskø, hendelseshistorikk, holdbar kunnskap og maskinverifiserte fortsettelsesregler — i vanlige filer ved siden av koden|Ingenting; det kombinerte er kontrakten|

Forskjellen er ikke noen enkelt fil. Den er at SAIPEN gjør fortsettelsessteg
maskinverifiserbart: den første handlingen en kald agent gjør etter`/saipen continue`er
bestemt av den lagrede`next_action`og verifisert av en validerer, ikke
rekonstruert fra minne.

## Ingeniørbevis

SAIPEN kombinerer en normativ vanlig-fil-protokoll med utførbare, feilorienterte
kontroller. Lagringsområdet viser protokoll/statemaskin design, Python
verktøy, skjema-gitt tilstand, gjenopprettingsresonering, regresjonstesting,
fleragent arbeidsflyt grenser, og spesifikasjonsskikkel.

- **Designet kontrakt.** [SPEC.md](SPEC.md)definerer filbasert
fortsettelsesmodell og den stabile på-disk kontrakten;[CORE.md](saipen/CORE.md)
og[MAINTENANCE.md](saipen/MAINTENANCE.md)har nåværende normative oppførsel.
- **Maskinkontrollert tilstand.**Den stdlib-only kanoniske
  [validerer](tools/validate.py)leser den live
  [STATESkjema](extensions/schemas/state.schema.json)og sjekker fase
overganger, billettavhengigheter, hendelsesgraf-lenker, tverrdokument
invarianter, evner og gjenopprettingsstatus.
- **Feildekning.** [CONFORMANCE.md](saipen/CONFORMANCE.md)kartlegger
krav til[scenario-fiksurer](tests/scenarios/); den
  [scenario runner](tools/run_scenarios.py)utfører strukturelle pass/fail-tilfeller
inkludert korrupt tilbakevinningsstatus, ugyldige overganger, avhengighetsløkker og
skrivebeskyttede restriksjoner.
- **Regresjonskontroller.** [audit_checks.py](tools/audit_checks.py)endrer
kjente gode kopier og viser at valideringskontrollene fortsatt kan bli røde, snarere enn
å behandle en permanent grønn kontroll som bevis.
- **Utførbare lag.** [saipen.py](tools/saipen.py)gir journalet tilstand
operasjoner;[bootstrap/](bootstrap/)holder install, uninstall og export
hjelpere med valgfri[pre-commit hook installer](tools/install_hook.py).
- **Eksplicitte avveklinger.**Kjerneprotokolltilstand er vanlige filer uten runtime
avhengighet. Kanonisk validering og CLI-verktøy krever Python, men bruker bare
dets standardbibliotek og trenger ingen`pip`install.

## Arkitektur

Tre lag, strengt énveis avhengigheter:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Kjerne avhenger ikke av vedlikehold: med autonomet evolusjon deaktivert, SAIPEN
er fortsatt en full kontinuerlig protokoll — en kald agent kan fortsatt opprettes.

- **Kjerne tilstandsmaskin** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Autonomt vedlikehold**— brett stoppet(ingenting fungerer i`## TODO`,
ingenting i`## DOING`)og ikke`BLOCKED`? Auto-overganger`HUNT` (skann feil)
  → `ADD` (utvikle funksjoner) → `HUNT`, ingen spørsmål stilt. En økt som sitter på
  `BLOCKED`aldri auto-jager
  ([Vedlikehold § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Målmodus** — `/saipen goal <objective>`snurrer om bordet og kjører
målet fremover gjennom VERIFY/REVIEW, og faller inn i autonomet vedlikehold
helt til fullføringsregelen utløses eller kjøringen når sin grense(3 bølger / 20 billetter,
deretter kontrollpunkter og rapporterer) ([Vedlikehold § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Forsterking**— batch-inndata blir parsert til kirurgiske en-etter-en-billetter
  (Kjerne § 1.8); dirty-tree-fortsettelse bevare ikke-kommittert arbeid(Kjerne § 1.5);
verdi som ligner på hemmelighet blir slettet fra loggene(`sk-***`) (Kjerne § 1.2).

## Vanlige kommandoer

Daglige inngangspunkter; den komplette nåværende overflaten finnes i
[Kjerne § 1.10](saipen/CORE.md#110-command-surface).

|Kommando|Gjør|
|---|---|
| `/saipen set` |Ta over et prosjekt: opprett`.saipen/`tilstand|
| `/saipen continue` |Gjenoppta fra lagret prosjekttilstand — ingen ny rebriefing|
| `/saipen plan` |Omdøm en forespørsel eller rå backlog til oppgaver|
| `/saipen goal <text>` |Autonom bølgeutførelse mot et nytt mål|
| `/saipen validate` |Kjør konformitetskontrollene|
| `/saipen status` |Skrivelås rapport: fase, oppgaver, blokkere, forstæring|
| `/saipen stop` |Merkpunkt og stopp|

<details>
<summary><b>More commands</b></summary>

|Kommando|Gjør|
|---|---|
| `/saipen hunt` |Tving defekten/forbedringsskanning nå|
| `/saipen markhunt` |Tørre, ubegrensede revisjoner — registrerer funn, gjør ikke noe rettelse|
| `/saipen ship` |Utgangsgater; kommitter, merk og push når tillatt|
| `/saipen clean` |Brett og tilstandsskanning|
| `/saipen translate` |Isolert oversettelsesfabrikk|
| `/saipen prepare` / `/saipen collect` |Pakkearbeid for overlevering / integrer en ferdig pakke|
| `/saipen test` |Kjør den deklarerte testsuiten, rapporter bare|
| `/saipen crew` |Fastrekkefølge eskorte sirkel(jakt → reproduksjon → inntak → bygg → oversett → dokumentér → send) |
| `/saipen improve` |Meta-styresystemaudit av protokollforbedringer|
| `/saipen sub ...` |Skap/adoptér skrivebeskyttede underagent|

**Pakk nøkler.** `ee`/`qq`forbered fullstendige oversettelses/wiki-pakker uten
integrering;`eee`/`qqq`aksepter bare ferdige pakker, deretter integrer, verifiser,
gjennomgå og send.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)går gjennom hele
innbygde crew i en fast orden — sensorer(saihunt, saitest, saipython, saiui),
produsenter(saitranslate, saiwiki)og Core som den eneste hovedtre-aksjonen —
før en ny frisk pass har ingenting virkelig igjen å endre. Den legger til nøyaktig én
mekanisme på egen hånd: den holdbare koordineringen av mål(«execution_intent:
konverger` with `konverger_mål: crew`)som gjør kretsen gjenopptattbar og
kollaps-deriverbar fra bevis.`saipen crew --dry-run --json`utleder
kretsen skrivebeskyttet;`bootstrap/saipen_crew.*`er et VALGFRI manuell
flervindu-hjelpemiddel, aldri hva`saipen crew`betyr. Se
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Hva SAIPEN ikke er

- **En LLM eller en modell**— det er et protokoll som agenter følger, ikke en intelligens.
- **Et IDE eller en vertshostet minnebasis**— tilstand er vanlige filer i prosjektet ditt;
— ingenting er vert;
- **En erstatning for Git**— Git eier fortsatt versjonshistorien; commit din
  `.saipen/`som noe annet kode.
- **Distribuert konsensus**— se på konkurransegrensen under.
- **En garanti for at en LLM vil gjøre korrekte ingeniørbeslutninger**— det
reduserer konteksttap og oppføringsdrift; det gjør ikke stokastiske agenter
ufeilbare.

SAIPENs jobb er en fortsettelse/tilstandskontrakt pluss validering og verktøy —
å gi neste agent en maskinkontrollert startpunkt, ikke magi.

**Konkurrerende grense.**Journaliserte tilstandsmuteringer(SAIOPS)bruke en
prosjektomfattende OS-lås og en gjenopprettingsjournal([OPS § 5](saipen/OPS.md#5-locks)).
Vanlige prosjektredigeringer og frakoblede skrivere er utenfor denne låsen. SAIPEN
er ikke fordelt konsensus, så frakoblede skrivere krever ekstern
koordinering([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ekosystem

|Prosjekt|Forhold til SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Lokalt Windows-kontrollsentral for SAIPEN-prosjekter — oppdager automatisk`.saipen/`arbeidsområder, visualiserer live tilstand og konformitetsverdicter, styrer billetter og starter AI CLIs. En tilleggsverktøy, ikke myndighet.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Nedstrøms CodeNomad-fork som integrerer SAIPEN: injiserer`BOOT.md`/`STYLE.md`i OpenCode-oppstartsprosesser, eksponerer SAIPEN-kortveier og prosjekttilstandsvisninger, og legger til en vedvarende prompt-kø.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Bærbar Windows-skissebok og snutterbehandler som automatisk oppdager`.saipen/`mapper og legger til en skrivebeskyttet STATE/BOARD/LOG-leser.|

## Dokumentasjon

|Dokument|Hva det er|
|---|---|
| [SPEC.md](SPEC.md) |Formell arkitektur, designmål, litmusprøve|
| [CORE.md](saipen/CORE.md) |Normativ fortsettelse, tilstandsmaskin og kommandekontrakt|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Autonom vedlikehold og Målmodus|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Utførbare/oppføringsmæssige krav og valideringsregler|
| [GUIDE.md](GUIDE.md) |Menneskelig tutoriale|
| [RFC.md](saipen/RFC.md) |Kompatibilitetsomdirigering til de splittede normative dokumentene|
| [STYLE.md](saipen/STYLE.md) |Agentkommunikasjonssstil og stemme|
| [UI.md](saipen/UI.md) |Vintage Golden UI designveiledninger|
|Brochure|Presentasjonsbrosjyre —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Engelsk](guides/GUIDE_EN.md) · 🇪🇪 [Estisk](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Tysk](guides/GUIDE_DE.md) · 🇫🇷 [Fransk](guides/GUIDE_FR.md) · 🇪🇸 [Spansk](guides/GUIDE_ES.md) · 🇮🇹 [Italiensk](guides/GUIDE_IT.md)

🇵🇹 [Portugisisk](guides/GUIDE_PT.md) · 🇳🇱 [Nederlandsk](guides/GUIDE_NL.md) · 🇵🇱 [Polsk](guides/GUIDE_PL.md) · 🇸🇪 [Svensk](guides/GUIDE_SV.md) · 🇩🇰 [Dansk](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Konfigurasjonsnotater

**Svar-språk.**Agenten svarer på**estisk**som standard — det er en
innstilling, ikke en protokolkrav, og ingenting annet ved SAIPEN er estisk.
Protokollen, koden, kommersene og alle dokumentene forblir engelske ved hver
verdi. Endre det i ett sted: linjen`reply_language:`på toppen av
[`saipen/STYLE.md`](saipen/STYLE.md). `et`estisk,`en`engelsk,`ru`russisk,
`auto`velger fra meldingen du sendte.

**Adaptere.**Plattform ikke dekvert av injektoren(DeepSeek, Qwen, standalone
OpenAI, osv.)? Per-platform notater finnes i`extensions/adapters/`.

## Skjermbilder

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
