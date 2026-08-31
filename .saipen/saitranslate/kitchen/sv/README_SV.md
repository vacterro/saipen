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

**Fortsättningsskikt för AI-kodningsagenter.**Projektminnet finns i vanlig text
Markdown-filer inuti projektet(`.saipen/`), så någon kompatibel kall agent —
ingen chatthistorik, ingen sessionsminne — kan köras`/saipen continue`, läs
pålagrad`next_action`, och fortsätta arbeta utan att behöva fråga användaren om att förklara om
något. Tillstånd tillhör projektet, inte till en modellleverantörs minne.

**En kommando för att återuppta. Vanlig filtillstånd. Maskinkontrollerade kontrakt.**

Repositoryt validerar sig självt vid varje push; install, state, checks, och
avinstallation är all lokal — ingen molntjänst, ingen daemon, ingen databas.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.233.3** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [Core](saipen/CORE.md) | [Maintenance](saipen/MAINTENANCE.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) |MIT

**Snabbkommandon:** `cc` fortsätter projektets kontext till konvergens (återupptar ett aktivt mål om ett är satt), `sss` visar status utan att röra koden och `ss` sparar en kontrollpunkt och stannar. [Se hela 19-tangentkartan](saipen/RFC.md#110-command-surface). Kyrilliska tvillingar fungerar också: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## Vad som förblir

Live projektminne finns i`.saipen/`— enkla filer du kan läsa, jämföra och
commita bredvid koden. En kall agent svarar på fem frågor från filerna
ensam:

|Fil / fält|Svar|
|---|---|
| `STATE.md` |Vad händer just nu?(fasa, aktiv supportticket, driftläge, blockering) |
| `BOARD.md` |Vad finns för arbete / vad är aktivt?(supportticket-diagram: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |Varför har projektet nått detta tillstånd?(endast-tilläggs händelsediagram) |
| `KNOWLEDGE/` |Vilka beständiga projektfakta måste överleva sessioner?|
| `next_action` (i`STATE.md`) |Vilken exakt åtgärd bör nästa agent utföra?|

Detta är en kontrollkontrakt, inte ett designförslag:`saipen stop`och varje
supportticketövergång skrivs filerna i en fast ordning, och resultatet kontrolleras av
en validerare. Inget lagras i en värd-databas, och inget förloras när en
sessionen slutar.

## Snabbstart

**1. Installera en gång per dator**— lär Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity, och någon generisk`~/.agents/skills`läsare(FreeBuff, osv.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`block till agentinstruktionen
filer du redan har(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— säkerhetskopiera varje en till`.bak`först —
och kopierar protokollet till de matchande färdighetsmapparna. Inget utanför dessa
sökvägar, ingen daemon, inga nätverksanrop.</sub>

**2. Starta ett projekt**— öppna en agent i din mapp, skriv:

> `saipen set`

**Ingen installation?**Klistra in en rad i någon agent:

> Läs&lt;klona&gt;/saipen/BOOT.md först(kalla startkernel), sedan&lt;klona&gt;/saipen/INDEX.md +&lt;klona&gt;/saipen/STYLE.md och följ dem.

**Ändrade du åsikten?**En kommando återställer det:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Det tar bort exakt den markerade blocken(och lämnar resten av din fil oförändrad), sparar
a `.uninstalled.bak`kopierar först, och tar bort färdighetsmapparna.

## Varför inte bara chatthistorik?

SAIPEN riktar sig mot en specifik brist: en AI-kodningsagent som glömmer allt
när sessionen är slut. andra verktyg och vanor täcker delvis det problemet:

|Metod|Vad det är bra för|Vad det inte bär|
|---|---|---|
|Chathistoria / modellminne|Bekvämt, inga inställningar krävs|Session- och leverantörsberoende; inte lagras med projektet, så en kall agent ser aldrig det|
|Statisk`AGENTS.md`/ instruktionsfil|Hållbara ståndpunkter och konventioner|Representerar inte av sig själv det levande uppgiftstillståndet`next_action`, eller återställningshistoria|
|Problem / TODO-spårare|Uppgiftshantering och backloghantering|Definierar inte av sig själv agentens fortsättningssemantik — vad en kall agent måste läsa och exekvera vid återupptagande|
| **SAIPEN** |Livekörningsstatus, arbetskö, händelsehistorik, hållbar kunskap och maskinkontrollerade fortsättningssregler — i vanliga filer bredvid koden|Inget; den kombinationen är kontraktet|

Skillnaden är inte någon enskild fil. Den är att SAIPEN gör återupptagningsskicket
maskinkontrollerbar: en kall agents första åtgärd efter`/saipen continue`är
bestämd av den sparade`next_action`och verifierad av en validerare, inte
rekonstruerad från minnet.

## Ingénjörsbevis

SAIPEN kombinerar en normativ vanlig-fil-protokoll med exekverbar, felorienterad
kontroller. Lagringsplatsen visar protokoll/tillstånds-maskin design, Python
verktyg, schema-drivna tillstånd, återställningslogik, regressionstest,
fleragentarbetsflödesgränser och specificeringsdisciplin.

- **Designad kontrakt.** [SPEC.md](SPEC.md)definierar filbaserad
kontinuerlig modell och den stabila kontrakt på disken;[CORE.md](saipen/CORE.md)
och[MAINTENANCE.md](saipen/MAINTENANCE.md)har nu normativt beteende.
- **Maskinbaserat tillstånd.**Den stdlib-only kanoniska
  [valideraren](tools/validate.py)läser den live
  [STATE-schemat](extensions/schemas/state.schema.json)och kontrollerar fas
övergångar, biljettberoenden, händelsegrafslänkar, tvärdokument
invarianter, förmågor och återställningsstatus.
- **Felomfattning.** [CONFORMANCE.md](saipen/CONFORMANCE.md)mappar
krav till[scenariobaser](tests/scenarios/); den
  [scenario runner](tools/run_scenarios.py)utför strukturella pass/fail-testfall
inkluderar skadad återställningsstatus, ogiltiga övergångar, beroendecykler och
endast-läs-restrictions.
- **Regression kontroller.** [audit_checks.py](tools/audit_checks.py)ändrar
kända goda kopior och visar att validerarens kontroller fortfarande kan visa röd, snarare än
att behandla en permanent grön kontroll som bevis.
- **Körbar lager.** [saipen.py](tools/saipen.py)ger journaled state
operationer;[bootstrap/](bootstrap/)håller install, uninstall och export
hjälpmedel med ett valfritt[pre-commit hook installer](tools/install_hook.py).
- **Explicita kompromisser.**Kärnprotokollstatus är vanliga filer utan runtime
beroende. Kanonisk validering och CLI-verktyg kräver Python, men använder endast
dess standardbibliotek och behöver ingen`pip`installation.

## Arkitektur

Tre lager, strikt enkelriktiga beroenden:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Kärna beroende på Underhåll: med autonom evolution inaktiverad, SAIPEN
är fortfarande ett komplett fortsättningsprotokoll — en kall agent återupptas fortfarande.

- **Kärnans tillståndsautomat** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Autonom underhåll**— bräda stoppad(ingenting användbart i`## TODO`,
ingenting i`## DOING`)och inte`BLOCKED`? Autoövergångar`HUNT` (skanna fel)
  → `ADD` (utveckla funktioner) → `HUNT`, ingen fråga ställs. En session sittande vid
  `BLOCKED`aldrig auto-hjälper
  ([Underhåll § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Mål-läge** — `/saipen goal <objective>`vrider om brädet och kör
målet framåt genom VERIFY/REVIEW, vilket leder till autonom underhåll
tills kompletteringsregeln utlöses eller körningen når sitt tak(3 vågor / 20 biljetter,
sedan kontrollerpunkter och rapporterar) ([Underhåll § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Härdat**— batch-ingång tolkas till kirurgiska en-och-ett-biljetter
  (Kärna § 1.8); förorenad trädfortsättning bevarar ogenomförda arbeten(Kärna § 1.5);
hemlighetsliknande värden tas bort från loggar(`sk-***`) (Kärna § 1.2).

## Vanliga kommandon

Varje dagliga ingångspunkter; den fullständiga nuvarande ytan finns i
[Kärna § 1.10](saipen/CORE.md#110-command-surface).

|Kommando|Gör|
|---|---|
| `/saipen set` |Adoptera ett projekt: skapa`.saipen/`tillstånd|
| `/saipen continue` |Återuppta från sparad projektstatus — ingen omorientering|
| `/saipen plan` |Konvertera en begäran eller råa bakloggar till tickets|
| `/saipen goal <text>` |Autonom vågutförande mot ett nytt mål|
| `/saipen validate` |Kör konformitetskontroller|
| `/saipen status` |Skrivelåst rapport: fas, tickets, blockeringar, föråldring|
| `/saipen stop` |Checkpunkt och stanna|

<details>
<summary><b>More commands</b></summary>

|Kommando|Gör|
|---|---|
| `/saipen hunt` |Tvinga fel/förbättringsundersökning nu|
| `/saipen markhunt` |Torka, obegränsad revision — dokumenterar resultat, gör inga åtgärder|
| `/saipen ship` |Utgångsgates; commit, tagga och push när tillåtet|
| `/saipen clean` |Bräda och tillståndsskrap|
| `/saipen translate` |Isolerad översättningsfabrik|
| `/saipen prepare` / `/saipen collect` |Paketera arbete för överföring / integrera ett redo paket|
| `/saipen test` |Kör den deklarera testuppsättningen, rapportera endast|
| `/saipen crew` |Fastordningsbesättningsslinga(jaga → återproducera → intag → bygg → översätt → dokumentera → skicka) |
| `/saipen improve` |Metakontrollgranskning av protokollförbättringar|
| `/saipen sub ...` |Skapa/adoptera skrivskyddade underagenters|

**Paketera nycklar.** `ee`/`qq`Förbered fullständiga översättning/wiki-paket utan
integrering;`eee`/`qqq`acceptera endast redo paket, sedan integrera, verifiera,
granska och push.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)går igenom hela
inbyggd besättning i en fast ordning — sensorer(saihunt, saitest, saipython, saiui),
tillverkare(saitranslate, saiwiki)och Core som den enda huvudträdsskrivaren —
tills en ny ren passering inte har något verkligt kvar att ändra. Den lägger till exakt en
mekanism av sin egen: den hållbara orchestreringen mål(execution_intent:
konvergera` with `konvergera_mål: crew`)som gör kretsen återupptäckbar och
kollapsbar från bevis.`saipen crew --dry-run --json`härleder
kretsen skrivskyddad;`bootstrap/saipen_crew.*`är ett VALFRITT manuellt
flervindugets hjälpmedel, aldrig vad`saipen crew`betyder. Se
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Vad SAIPEN inte är

- **En LLM eller en modell**— det är ett protokoll som agenter följer, inte en intelligens.
- **Ett IDE eller en värdmemodatabas**— tillstånd är vanliga filer i ditt projekt;
ingenting är värd;
- **En ersättning för Git**— Git äger fortfarande versionshistoriken; commita din
  `.saipen/`som någon annan kod.
- **Distribuerad samförståelse**— se sammanhangsgränsen nedan.
- **En garanti att en LLM kommer att göra korrekta ingenjörsbeslut**— den
minskar kontextförlust och beteendevridning; den gör inte stokastiska agenter
ofelbara.

SAIPEN:s jobb är en fortsättning/tillståndsavtal plus validering och verktyg —
att ge nästa agent en maskinkontrollerad startpunkt, inte magi.

**Konkurrensgräns.**Journaliserade tillståndsändringar(SAIOPS)använd en
projektomfattande OS-lås och en återställningsjournal([OPS § 5](saipen/OPS.md#5-locks)).
Vanliga projektredigeringar och kopplade skrivare är utanför det låset. SAIPEN
är inte distribuerad konsensus, så kopplade skrivare kräver extern
koordination([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ecosystem

|Projekt|Relation till SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Lokalt Windows-kontrollcenter för SAIPEN-projekt — upptäcker automatiskt`.saipen/`arbetsområden, visualiserar live-tillstånd och konformitetsbedömningar, hanterar biljetter och startar AI-CLIs. En kompanjon, inte myndigheten.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Nedströms CodeNomad-klon som integrerar SAIPEN: injicerar`BOOT.md`/`STYLE.md`i OpenCode-startar, exponerar SAIPEN-genvägar och projekt-tillståndsvisningar, och lägger till en bestående promptkö.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Bärbar Windows-skissblock och snippetshanterare som automatiskt upptäcker`.saipen/`mappar och lägger till en skrivskyddad STATE/BOARD/LOG-visare.|

## Dokumentation

|Dokument|Vad det är|
|---|---|
| [SPEC.md](SPEC.md) |Formell arkitektur, designmål, litmusprov|
| [CORE.md](saipen/CORE.md) |Normativ fortsättning, tillståndsautomat och kommandokontrakt|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Autonom underhåll och Goal Mode|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Körbara/åtgärdsbaserade krav och valideringsregler|
| [GUIDE.md](GUIDE.md) |Mänsklig handledning|
| [RFC.md](saipen/RFC.md) |Kompatibilitetsomdirigering till de uppdelade normativa dokumenten|
| [STYLE.md](saipen/STYLE.md) |Agentkommunikationsstil och röst|
| [UI.md](saipen/UI.md) |Vintage Golden UI-designriktlinjer|
|Brochure|Presentation brochure —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Engelska](guides/GUIDE_EN.md) · 🇪🇪 [Estniska](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Tyska](guides/GUIDE_DE.md) · 🇫🇷 [Franska](guides/GUIDE_FR.md) · 🇪🇸 [Spanska](guides/GUIDE_ES.md) · 🇮🇹 [Italienska](guides/GUIDE_IT.md)

🇵🇹 [Portugisiska](guides/GUIDE_PT.md) · 🇳🇱 [Nederländska](guides/GUIDE_NL.md) · 🇵🇱 [Polska](guides/GUIDE_PL.md) · 🇸🇪 [Svenska](guides/GUIDE_SV.md) · 🇩🇰 [Danska](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Konfigurationsanteckningar

**Svarspråk.**Agenten svarar på**estniska**som standard — det är en
inställning, inte en protokollierad krav, och inget annat med SAIPEN är estniska.
Protokollet, koden, commitarna och alla dokument förblir engelska vid varje
värde. Ändra det i ett ställe: raden`reply_language:`till toppen av
[`saipen/STYLE.md`](saipen/STYLE.md). `et`estniska,`en`engelska,`ru`ryska,
`auto`väljer ut meddelandet du skickade.

**Anpassare.**Plattformen täcks inte av injektorn(DeepSeek, Qwen, standalone
OpenAI, etc.)? Per-plattformsnoter finns i`extensions/adapters/`.

## Skärmbilder

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
