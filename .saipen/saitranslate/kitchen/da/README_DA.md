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

**Fortsættelsesprotokol for AI-kodingssystemer.**Projektminde findes i klartekst
Markdown-filer inden for projektet(`.saipen/`), så enhver kompatibel kold agent —
ingen chat-historik, ingen sessionshukommelse — kan køre`/saipen continue`, læs
opbevaret`next_action`, og genoptage arbejdet uden at spørge brugeren om at forklare noget
nogen. Tilstand tilhører projektet, ikke en enkelt modells leverandørs hukommelse.

**En kommando til at genoptage. Klartekstfil-tilstand. Maskinerapporteret kontrakter.**

Repository validerer sig selv ved hver push; install, tilstand, kontroller og
afinstallation er alle lokale — ingen skytjeneste, ingen daemon, ingen database.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.238.2** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [Core](saipen/CORE.md) | [Maintenance](saipen/MAINTENANCE.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) |MIT

**Hurtigtaster:** `cc` fortsætter projektets kontekst til konvergens (genoptager et aktivt mål, hvis et er sat), `sss` viser status uden at røre koden, og `ss` gemmer et kontrolpunkt og stopper. [Se hele 19-tasters kortet](saipen/RFC.md#110-command-surface). Kyrilliske tvillinger virker også: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## Hvad vedbliver

Live projektminde findes i`.saipen/`— almindelige filer, du kan læse, sammenligne og
committe ved siden af koden. En kold agent svarer fem spørgsmål fra filerne
alene:

|Fil / felt|Svar|
|---|---|
| `STATE.md` |Hvad sker der lige nu?(fase, aktiv ticket, driftsmodus, blokering) |
| `BOARD.md` |Hvad arbejde findes der / hvad er aktivt?(ticket graf: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |Hvorfor har projektet nået dette tilstand?(append-only hændelsesgraf) |
| `KNOWLEDGE/` |Hvad varige projekt-fakta skal overleve sessioner?|
| `next_action` (i`STATE.md`) |Hvad præcis handling skal den næste agent udføre?|

Dette er en checkpoint kontrakt, ikke et designforslag:`saipen stop`og hver
ticket overgang skriv filerne i en fast rækkefølge, og resultatet kontrolleres af
en validator. Intet lagres i en vært database, og intet går tabt, når en
session slutter.

## Hurtig start

**1. Installer én gang per maskine**— lærer Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity, og enhver generisk`~/.agents/skills`læser(FreeBuff, osv.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`blok til agentinstruktionen
filer, du allerede har(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— backer hver op til`.bak`først —
og kopierer protokollen ind i de tilsvarende færdighedsmappe. Intet uden for dem
stier, ingen daemon, ingen netværkskald.</sub>

**2. Start et projekt**— åbn en agent i din mappe, skriv:

> `saipen set`

**Ingen installation?**Kopier én linje til enhver agent:

> Læs&lt;klon&gt;/saipen/BOOT.md først(koldstart kernel), derefter&lt;klon&gt;/saipen/INDEX.md +&lt;klon&gt;/saipen/STYLE.md og følg dem.

**Har du ændret tanke?**En kommando sætter det tilbage:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Det fjerner netop den markerede blok(og efterlader resten af din fil uændret), gemmer
a `.uninstalled.bak`lav en kopi først, og fjerner de færdighedsmappe.

## Hvorfor ikke bare chat-historikken?

SAIPEN målretter en bestemt fejl: en AI-kodingagent, der ikke husker noget
når sessionen slutter. Andre værktøjer og vaner dækker en del af dette problem:

|Metode|Hvad det er godt til|Hvad det ikke bærer|
|---|---|---|
|Chat historik / model hukommelse|Praktisk, ingen opsætning|Afhængigt af session og leverandør; ikke gemt sammen med projektet, så en kold agent aldrig ser det|
|Statiske`AGENTS.md`/instruksionsfil|Holdbare stående regler og konventioner|Repræsenterer ikke af sig selv det live opgave tilstand`next_action`, eller genopretningshistorik|
|Problem / TODO sporer|Opgave- og backlogstyring|Definerer ikke af sig selv agentens fortsætningssemantik — hvad en kold agent skal læse og udføre, når den genoptager|
| **SAIPEN** |Live udførelsesstatus, arbejdsfil, begivenhedshistorik, holdbar viden og maskinbaserede regler for fortsættelse — i almindelige filer ved siden af koden|Ingenting; den kombination er kontrakten|

Forskellen er ikke en enkelt fil. Det er, at SAIPEN gør genoptagelsessticket
maskinbaseret: den første handling, en kold agent udfører efter`/saipen continue`er
bestemt af den opbevarede`next_action`og verificeret af en validator, ikke
rekonstrueret fra hukommelsen.

## Ingeniørbevis

SAIPEN parret en normativ almindelig-fil-protokol med udførlige, fejlrettede
kontroller. Repository'et demonstrerer protokol/tilstandsmaskine design, Python
værktøjsudvikling, skemadrivne tilstande, genopretningsskøn, regressionstestning,
multi-agent arbejdsgrenser og specifikationsdisciplin.

- **Designet kontrakt.** [SPEC.md](SPEC.md)definerer den filbaserede
fortsætningsmodel og den stabile på-disk kontrakt;[CORE.md](saipen/CORE.md)
og[MAINTENANCE.md](saipen/MAINTENANCE.md)beskriver den nuværende normative adfærd.
- **Maskinbaseret tilstand.**Den stdlib-only kanoniske
  [validerer](tools/validate.py)læser den live
  [STATE skema](extensions/schemas/state.schema.json)og tjekker fase
overgange, billetafhængigheder, event-graph links, cross-document
invarianter, evner og genoprettningsstatus.
- **Fejldekning.** [CONFORMANCE.md](saipen/CONFORMANCE.md)karterer
krav til[scenario fixtures](tests/scenarios/); den
  [scenario runner](tools/run_scenarios.py)udfører strukturelle pass/fail tilfælde
herunder korrupt genopretningstilstand, ugyldige overgange, afhængigheds-cykler og
skrivebeskyttede begrænsninger.
- **Regressionstestkontroller.** [audit_checks.py](tools/audit_checks.py)ændrer
kendte god kopier og beviser, at validerens kontroller stadig kan blive røde, snarere end
at behandle en permanent grøn kontrol som bevis.
- **Udførlig lag.** [saipen.py](tools/saipen.py)fører journaliseret tilstand
operationer;[bootstrap/](bootstrap/)holder install, uninstall og export
hjælper, med en valgfri[pre-commit hook installer](tools/install_hook.py).
- **Eksplicitte kompromiser.**Kerneprotokoltilstand er almindelige filer uden runtime
afhængighed. Kanonisk validering og CLI værktøjsprogrammer kræver Python, men bruger kun
dets standardbibliotek og har ikke brug for`pip`installation.

## Arkitektur

Tre lag, strengt én vej afhængigheder:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Kernen afhænger ikke af vedligeholdelse: med autonom evolution deaktiveret, SAIPEN
er stadig et fuldt forlængelseprotokol — en kold agent genoptager stadig.

- **Kernens tilstandsmaskine** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Autonom vedligeholdelse**— bræt stoppet(intet brugbart i`## TODO`,
intet i`## DOING`)og ikke`BLOCKED`? Auto-overgange`HUNT` (scannet fejl)
  → `ADD` (udvikl features) → `HUNT`, ingen spørgsmål stillet. En session, der sidder ved
  `BLOCKED`aldrig auto-jager
  ([Vedligeholdelse § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Måltilstand** — `/saipen goal <objective>`drejer spillebrættet og kører
målet fremad gennem VERIFY/REVIEW, og falder i autonom vedligeholdelse
indtil kompletteringsreglen udløses eller køreren når sin grænse(3 bølger / 20 billetter,
derefter kontrolpunkter og rapporterer) ([Vedligeholdelse § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Styrkelse**— batch-inddata analyseres til kirurgiske en-efter-ens billetter
  (KÆRNE § 1.8); dirty-tree-fortsatte bevare ikke-afviklede arbejde(KÆRNE § 1.5);
hemmelighed-liknende værdier er censureret fra logfiler(`sk-***`) (KÆRNE § 1.2).

## Almindelige kommandoer

Daglige indgangspunkter; den komplette nuværende overflade findes i
[KÆRNE § 1.10](saipen/CORE.md#110-command-surface).

|Kommando|Gør|
|---|---|
| `/saipen set` |Overtag et projekt: opret`.saipen/`tilstand|
| `/saipen continue` |Genoptag fra opbevaret projektstatus — ingen geninstruering|
| `/saipen plan` |Omdan en anmodning eller rå backlog til tickets|
| `/saipen goal <text>` |Autonom udførelse af bølge mod et nyt mål|
| `/saipen validate` |Kør konformitetskontroller|
| `/saipen status` |Læsebare rapport: fase, tickets, blokeringer, forældethed|
| `/saipen stop` |Checkpoint og stop|

<details>
<summary><b>More commands</b></summary>

|Kommando|Gør|
|---|---|
| `/saipen hunt` |Tving defekt/forbedringsrengøring nu|
| `/saipen markhunt` |Tør, ubegrænset audit — registrerer fund, retter intet|
| `/saipen ship` |Udgangsgates; commit, tag og push, når det er tilladt|
| `/saipen clean` |Bræt og tilstandsskylning|
| `/saipen translate` |Isolerede oversætningsfabrikker|
| `/saipen prepare` / `/saipen collect` |Pakkearbejde til overdræt / integrér en klar pakke|
| `/saipen test` |Kør den deklarerede testsuite, rapportér kun|
| `/saipen crew` |Fastrækkefølge-kreds for besætning(jag → genskab → optag → byg → oversæt → dokumentér → send) |
| `/saipen improve` |Meta-styrelsesrevison af protokolforbedringer|
| `/saipen sub ...` |Skab/adoptér læsebare underagenters|

**Pakke nøgler.** `ee`/`qq`forbered fuldstændige oversætnings/wiki-pakker uden
integrering;`eee`/`qqq`acceptér kun klar pakker, derefter integrér, verificér,
gennemgå og push.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)går hele vejen
indbygget hold i en fast rækkefølge — sensorer(saihunt, saitest, saipython, saiui),
producenter(saitranslate, saiwiki)og Core som den eneste hovedtrædskrivere —
indtil en ny frisk passering ikke har noget virkeligt tilbage, der kan ændres. Det tilføjer præcis én
mekanisme til sin egen: den vedholdende orkestreringsmål(``execution_intent:
konvergerer` with `konvergeringsmål: hold`)der gør kredsløbet genoptageligt og
kollapser fra bevis.`saipen crew --dry-run --json`deriverer den
kredsløbet skrivebeskyttet;`bootstrap/saipen_crew.*`er et VALGFRI manuel
flervinduSHjælpeprogram, aldrig hvad`saipen crew`betyder. Se
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Hvad SAIPEN ikke er

- **En LLM eller en model**— det er et protokol, agenter følger, ikke en intelligens.
- **En IDE eller en vært database**— tilstand er almindelige filer i din projekt;
intet er vært;
- **En erstatning for Git**— Git ejer stadig versionshistorikken; commit din
  `.saipen/`som enhver anden kode.
- **Distribueret konsensus**— se koncurrentgrænsen nedenfor.
- **En garanti for, at en LLM vil træffe korrekte ingeniørbeslutninger**— det
reducerer konteksttab og adfærdsdrift; det gør ikke stokastiske agenter
fejlfrie.

SAIPEN's opgave er en fortsættelses/tilstands kontrakt plus validering og værktøjer —
at give den næste agent en maskinekontrolleret startpunkt, ikke magi.

**Konkurrencegrænse.**Journaliserede tilstandsmutationer(SAIOPS)brug en
projektomfattende OS lås og en genoprettningsjournal([OPS § 5](saipen/OPS.md#5-locks)).
Almindelige projektredigeringer og adskilte skribenter er uden for denne lås. SAIPEN
er ikke fordelt konsensus, så adskilte skribenter kræver ekstern
koordination([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ecosystem

|Projekt|Forhold til SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Lokal Windows kontrolcenter for SAIPEN-projekter — opdager automatisk`.saipen/`arbejdsområder, visualiserer live tilstand og konformitetsafgørelser, styrer tickets og starter AI CLIs. En tilhører, ikke myndigheden.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Nedstrøms CodeNomad-afgørelse, der integrerer SAIPEN: indsætter`BOOT.md`/`STYLE.md`i OpenCode-start, gør SAIPEN-genveje og projekttilstandsvisninger tilgængelige og tilføjer en vedvarende prompt-kø.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Bærbar Windows skitseblok og snitmanager, der automatisk opdager`.saipen/`mapper og tilføjer en skrivebeskyttet STATE/BOARD/LOG-visualisering.|

## Dokumentation

|Dokument|Hvad det er|
|---|---|
| [SPEC.md](SPEC.md) |Formal arkitektur, designmål, litmus test|
| [CORE.md](saipen/CORE.md) |Normativ fortsættelse, tilstandsmaskine og kommandokontrakt|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Autonom vedligeholdelse og Goal Mode|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Udførlige/gedragsmæssige krav og validatorregler|
| [GUIDE.md](GUIDE.md) |Menneskelig tutorial|
| [RFC.md](saipen/RFC.md) |Kompatibilitet omdirigeres til de splittede normative dokumenter|
| [STYLE.md](saipen/STYLE.md) |Agent kommunikationsstil og stemme|
| [UI.md](saipen/UI.md) |Vintage Golden UI designvejledning|
|Brochure|Præsentationsbrochure —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Engelsk](guides/GUIDE_EN.md) · 🇪🇪 [Estisk](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Tysk](guides/GUIDE_DE.md) · 🇫🇷 [Fransk](guides/GUIDE_FR.md) · 🇪🇸 [Spansk](guides/GUIDE_ES.md) · 🇮🇹 [Italiensk](guides/GUIDE_IT.md)

🇵🇹 [Portugisisk](guides/GUIDE_PT.md) · 🇳🇱 [Nederlandsk](guides/GUIDE_NL.md) · 🇵🇱 [Polsk](guides/GUIDE_PL.md) · 🇸🇪 [Svensk](guides/GUIDE_SV.md) · 🇩🇰 [Dansk](guides/GUIDE_DA.md)

🇫🇮 [Finsk](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Tyrkisk](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Indonesisk](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Tjekkisk](guides/GUIDE_CS.md) · 🇷🇴 [Românește](guides/GUIDE_RO.md) · 🇭🇺 [Ungarisch](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenský](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Konfigurationsnoter

**Sprog for svar.**Agenten svarer på**estnisk**som standard — det er en
indstilling, ikke en protokolkrav, og intet andet ved SAIPEN er estnisk.
Protokollen, koden, commit'erne og alle dokumenter forbliver engelske ved hver
værdi. Ændr det i ét sted: den`reply_language:`linje i toppen af
[`saipen/STYLE.md`](saipen/STYLE.md). `et`estnisk,`en`engelsk,`ru`russisk,
`auto`vælger fra beskeden, du sendte.

**Adaptere.**Platform ikke dækket af injektoren(DeepSeek, Qwen, standalone
OpenAI, osv.)? Per-platform noter findes i`extensions/adapters/`.

## Skærmbilleder

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
