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

**Continuatieprotocol voor AI-coderingsagenten.**Projectgeheugen bevindt zich in platte
Markdown-bestanden binnen het project(`.saipen/`), dus elke compatibele koude agent —
geen chatgeschiedenis, geen sessiegeheugen — kan uitvoeren`/saipen continue`, lezen de
opgeslagen`next_action`, en de werkzaamheden hervatten zonder de gebruiker te vragen om alles opnieuw uit te leggen
anything. State behoort tot het project, niet tot het geheugen van één modelleverancier.

**Eén opdracht om te hervatten. Plattebestandsstatus. Machinegecontroleerde contracten.**

Het opslagplaats valideert zichzelf bij elke push; install, state, checks, en
oninstall zijn allemaal lokaal — geen cloud-service, geen daemon, geen database.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.238.0** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [Core](saipen/CORE.md) | [Maintenance](saipen/MAINTENANCE.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) |MIT

**Sneltoetsen:** `cc` zet de projectcontext voort tot convergentie (hervat een actief doel als er een is ingesteld), `sss` meldt status zonder code aan te raken en `ss` slaat een checkpoint op en stopt. [Bekijk de volledige 19-toetsenkaart](saipen/RFC.md#110-command-surface). Cyrillische tweelingen werken ook: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## Wat blijft hangen

Live projectgeheugen leeft in`.saipen/`— gewone bestanden die je kunt lezen, diff'en en
commit naast de code. Een koud agent beantwoordt vijf vragen uit de bestanden
alleen:

|Bestand / veld|Antwoorden|
|---|---|
| `STATE.md` |Wat gebeurt er op dit moment?(fase, actieve ticket, bedieningsmodus, blokkade) |
| `BOARD.md` |Wat voor werk bestaat / wat is actief?(ticketgrafiek: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |Waarom heeft het project deze toestand bereikt?(append-only gebeurtenisgrafiek) |
| `KNOWLEDGE/` |Welke duurzame projectfeiten moeten sessies overleven?|
| `next_action` (in`STATE.md`) |Welke exacte actie moet de volgende agent uitvoeren?|

Dit is een checkpointcontract, geen ontwerpsuggestie:`saipen stop`en elke
ticketovergang schrijft de bestanden in een vaste volgorde, en het resultaat wordt gecontroleerd door
een validator. Niets wordt opgeslagen in een gehoste database, en niets gaat verloren wanneer een
de sessie eindigt.

## Snelstart

**1. Installeer één keer per machine**— leert Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity, en elk generiek`~/.agents/skills`lezer(FreeBuff, enz.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`blok naar de agent instructie
bestanden die je al hebt(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— back-uppen naar`.bak`eerst —
en kopieert het protocol naar de overeenkomstige vaardigheidsmap. Niets buiten die
paden, geen daemon, geen netwerkoproepen.</sub>

**2. Start een project**— open een agent in je map, typ:

> `saipen set`

**Geen installatie?**Plak één regel in elke agent:

> Lees&lt;clone&gt;/saipen/BOOT.md eerst(koudstart kernel), dan&lt;clone&gt;/saipen/INDEX.md +&lt;kloon&gt;/saipen/STYLE.md en volg ze.

**Gewijzigd van gedachten?**Eén opdracht zet het terug:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Het verwijdert precies het gemarkeerde blok(en laat de rest van je bestand onaangeraakt), slaat op
a `.uninstalled.bak`maak eerst een kopie en verwijder de vaardigheidsmapjes.

## Waarom niet gewoon chatgeschiedenis?

SAIPEN richt zich op een specifieke fout: een AI-coderingsagent die niets onthoudt
zodra de sessie is afgelopen. Andere tools en gewoonten dekken een deel van dat probleem:

|Aanpak|Wat het goed voor is|Wat het niet draagt|
|---|---|---|
|Chatgeschiedenis / modelgeheugen|Handig, geen opzet vereist|Afhankelijk van sessie en leverancier; niet opgeslagen met het project, dus een koud agent ziet het nooit|
|Statisch`AGENTS.md`/instructief bestand|Duurzame standaardregels en conventies|Stelt niet vanzelf het live taakproces voor,`next_action`, of herstelgeschiedenis|
|Probleem / TODO tracker|Taak- en backlogbeheer|Definieert niet vanzelf de agentcontinuïteitssemantiek — wat een koude agent moet lezen en uitvoeren bij hervatting|
| **SAIPEN** |Live uitvoeringsstatus, werkwachtrij, gebevenhistorie, duurzame kennis en machinecontroleerbare continuïteitsregels — in gewone bestanden naast de code|Niets; die combinatie is het contract|

Het verschil is geen enkel bestand. Het is dat SAIPEN het hervatstap uitvoert
machinecontroleerbaar: de eerste actie van een koude agent na`/saipen continue`is
gedictueerd door de opgeslagen`next_action`en gecontroleerd door een validator, niet
hersteld uit het geheugen.

## Engineering evidence

SAIPEN combineert een normatieve gewone bestandsprotocollering met uitvoerbare, foutgerichte
controlepunten. Het opslagplaats demonstratie protocol/state-machine ontwerp, Python
tooling, schema-gestuurd staat, herstel redenering, regressie testen,
multi-agent werkstroom grenzen, en specificatie discipline.

- **Gedesigneerde contract.** [SPEC.md](SPEC.md)definieert het bestand ondersteunde
voortzetting model en de stabiele op schijf contract;[CORE.md](saipen/CORE.md)
en[MAINTENANCE.md](saipen/MAINTENANCE.md)hebben huidige normatieve gedrag.
- **Machine-gecontroleerde staat.**De stdlib-only canonische
  [valideraar](tools/validate.py)leest de live
  [STATE schema](extensions/schemas/state.schema.json)en controleert fase
overgangen, ticket-afhankelijkheden, event-grafiek-koppelingen, cross-document
invarianten, mogelijkheden en herstelstatus.
- **Foutdekkingsomvang.** [CONFORMANCE.md](saipen/CONFORMANCE.md)kaart
vereisten af[scenario fixtures](tests/scenarios/); de
  [scenario runner](tools/run_scenarios.py)voert structurele pass/fail gevallen uit
met inbegrip van beschadigde herstelstatus, ongeldige overgangen, afhankelijkheidscycli en
alleen-lezen beperkingen.
- **Regressiecontroles.** [audit_checks.py](tools/audit_checks.py)wijzigt
bekende goede kopieën en bewijst dat de validatiecontroles nog steeds rood kunnen worden, in plaats van
een permanent groene controle als bewijs te beschouwen.
- **Uitvoerbaar laag.** [saipen.py](tools/saipen.py)bevat journaled state
bewerkingen;[bootstrap/](bootstrap/)bevat install, uninstall en export
hulp programma's met een optionele[pre-commit hook installer](tools/install_hook.py).
- **Explicitieke keuzes.**Het kernprotocol is gewone bestanden zonder runtime
afhankelijkheid. Canonieke validatie en CLI-tools vereisen Python, maar gebruiken alleen
de standaardbibliotheek en vereisen geen`pip`installatie.

## Architectuur

Drie lagen, strikt enkelzijdige afhankelijkheden:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Core hangt niet af van Maintenance: met autonome evolutie uitgeschakeld, SAIPEN
is nog steeds een volledig voortzettingprotocol — een koud agent blijft nog steeds hervatten.

- **Core state machine** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Autonome onderhoud**— bord gestopt(niets bruikbaars in`## TODO`,
niets in`## DOING`)en niet`BLOCKED`? Auto-overgangen`HUNT` (scan bugs)
  → `ADD` (evolve features) → `HUNT`, geen vragen gesteld. Een sessie zit aan
  `BLOCKED`nooit automatisch jacht
  ([Onderhoud § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Doelmodus** — `/saipen goal <objective>`draait het bord om en voert de
doel vooruit via VERIFY/REVIEW, waarna het in autonomie onderhoud valt
totdat de voltooiingsregel afvalt of de run zijn limiet bereikt(3 golven / 20 tickets,
dan checkpoints en rapporteert) ([Onderhoud § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Versterking**— batch invoer wordt verwerkt in chirurgische één-één tickets
  (CORE § 1.8); vuil-bomen voortzetting behoudt ongecommiteerde werk(CORE § 1.5);
geheim-achtige waarden worden uit logbestanden verwijderd(`sk-***`) (CORE § 1.2).

## Alledaagse opdrachten

Alledaagse ingangspunten; het volledige huidige oppervlak bevindt zich in
[Core § 1.10](saipen/CORE.md#110-command-surface).

|Opdracht|Doet|
|---|---|
| `/saipen set` |Een project adopteren: aanmaken`.saipen/`staat|
| `/saipen continue` |Herstart vanuit het bijgehouden projectstatus — geen herinstructie|
| `/saipen plan` |Zet een aanvraag of ruwe backlog om in tickets|
| `/saipen goal <text>` |Autonome golfuitvoering tegenover een nieuw doel|
| `/saipen validate` |Voer de conformiteitscontroles uit|
| `/saipen status` |Alleen-lezen rapport: fase, tickets, blokkades, veroudering|
| `/saipen stop` |Checkpoint en stoppen|

<details>
<summary><b>More commands</b></summary>

|Commando|Doet|
|---|---|
| `/saipen hunt` |Forceer de defect/improvement scan nu|
| `/saipen markhunt` |Droge, onbeperkte audit — registreert bevindingen, verandert niets|
| `/saipen ship` |Release gates; commit, tag en push wanneer toegestaan|
| `/saipen clean` |Boord en status reiniging|
| `/saipen translate` |Isolatie vertaalfabriek|
| `/saipen prepare` / `/saipen collect` |Pakketwerk voor overdracht / integreer een klaar pakket|
| `/saipen test` |Voer de verklaarde testreeks uit, rapporteer alleen|
| `/saipen crew` |Vastvolgorde bemanningscircuit(jacht → reproduceren → opname → bouwen → vertalen → documenteren → versturen) |
| `/saipen improve` |Metacontrole-audit van protocoolverbeteringen|
| `/saipen sub ...` |Spawn/adopt alleen-lezen subagenten|

**Pakket sleutels.** `ee`/`qq`voorbereiden volledige vertaling/wiki pakketten zonder
integreren;`eee`/`qqq`accepteer alleen klaar pakketten, dan integreren, verifiëren,
beoordelen en pushen.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)loopt het hele
ingebouwde crew in een vaste volgorde — sensoren(saihunt, saitest, saipython, saiui),
producers(saitranslate, saiwiki)en Core als de enige main-tree schrijver —
totdat een andere frisse pass niets reëels over heeft om te veranderen. Het voegt precies één
mechanisme van zichzelf toe: de duurzame orkestratie doelwit(``execution_intent:
converge` with `converge_target: crew`)dat de schakeling herneembaar maakt en
crash-afleidbaar is uit bewijs.`saipen crew --dry-run --json`leidt af de
schakeling alleen-lezen;`bootstrap/saipen_crew.*`is een OPTIONELE handmatige
multi-venster helper, nooit wat`saipen crew`betekent. Zie
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Wat SAIPEN niet is

- **Een LLM of een model**— het is een protocol dat agents volgen, niet een intelligentie.
- **Een IDE of een gehoste geheugendatabase**— de staat bestaat uit gewone bestanden in je project;
niets wordt gehost.
- **Een vervanging voor Git**— Git blijft de versiegeschiedenis beheren; commit je
  `.saipen/`zoals elke andere code.
- **Gedelegeerde consensus**— zie de grens van gelijktijdigheid hieronder.
- **Een garantie dat een LLM correcte ingenieursbeslissingen zal nemen**— het
vermindert contextverlies en gedragsafwijking; het maakt stochastische agenten niet onfeilbaar.
De taak van SAIPEN is een voortzetting/state contract plus validatie en tools —


het volgende agent een machinegecontroleerd startpunt geven, niet magie.

**Concurrentie grens.**Geloggde toestandsmutaties(SAIOPS)gebruik een
projectgebonden OS lock en een herstellogboek([OPS § 5](saipen/OPS.md#5-locks)).
Normale projectbewerkingen en ongekoppelde schrijvers zijn buiten die lock. SAIPEN
is geen gedistribueerde consensus, dus ongekoppelde schrijvers vereisen externe
coördinatie([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ecosysteem

|Project|Relatie tot SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Lokale Windows controlecentrale voor SAIPEN-projecten — ontdekt automatisch`.saipen/`werkruimtes, visualiseert live status en conformiteitsbesluiten, beheert tickets en start AI-CLIs. Een partner, niet de autoriteit.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Downstream CodeNomad-fork die SAIPEN integreert: injecteert`BOOT.md`/`STYLE.md`in OpenCode-starten, maakt SAIPEN-sneltoetsen en projectstatusweergaven beschikbaar, en voegt een blijvende promptwachtrij toe.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Draagbare Windows schetsblok en snippetbeheerder die automatisch detecteert`.saipen/`mappen en een alleen-lezen STATE/BOARD/LOG-weergave toevoegt.|

## Documentatie

|Document|Wat het is|
|---|---|
| [SPEC.md](SPEC.md) |Formele architectuur, ontwerpdoelen, litmus test|
| [CORE.md](saipen/CORE.md) |Normatieve voortzetting, toestandsmachine en commandocontract|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Autonome onderhoud en Goal Mode|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Uitvoerbare/gedragaansprakelijke eisen en validatierichtlijnen|
| [GUIDE.md](GUIDE.md) |Menselijke handleiding|
| [RFC.md](saipen/RFC.md) |Compatibiliteitsomleiding naar de gesplitste normatieve documenten|
| [STYLE.md](saipen/STYLE.md) |Agent communicatiestijl en stem|
| [UI.md](saipen/UI.md) |Vintage Golden UI ontwerpgidsen|
|Brochure|Presentatiebrochure —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Engels](guides/GUIDE_EN.md) · 🇪🇪 [Estisch](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Duits](guides/GUIDE_DE.md) · 🇫🇷 [Frans](guides/GUIDE_FR.md) · 🇪🇸 [Spaans](guides/GUIDE_ES.md) · 🇮🇹 [Italiaans](guides/GUIDE_IT.md)

🇵🇹 [Portugees](guides/GUIDE_PT.md) · 🇳🇱 [Nederlands](guides/GUIDE_NL.md) · 🇵🇱 [Pools](guides/GUIDE_PL.md) · 🇸🇪 [Zweeds](guides/GUIDE_SV.md) · 🇩🇰 [Deens](guides/GUIDE_DA.md)

🇫🇮 [Finnisch](guides/GUIDE_FI.md) · 🇳🇴 [Noors](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Vietnamees](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Turks](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Tsjechisch](guides/GUIDE_CS.md) · 🇷🇴 [Roemeens](guides/GUIDE_RO.md) · 🇭🇺 [Hongaars](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovaaks](guides/GUIDE_SK.md) · 🇭🇷 [Kroatisch](guides/GUIDE_HR.md)

</details>

## Configuratie notities

**Antwoordtaal.**De agent antwoordt in**Estisch**standaard — dat is een
instelling, niet een protocolvereiste, en niets anders over SAIPEN is Estisch.
Het protocol, de code, de commits en elk document blijven Engels bij elke
waarde. Verander het in één plek: de`reply_language:`regel aan de bovenkant van
[`saipen/STYLE.md`](saipen/STYLE.md). `et`Estisch,`en`Engels,`ru`Russisch,
`auto`kiest uit het bericht dat je hebt gestuurd.

**Adapters.**Platform niet bedekt door de injecteur(DeepSeek, Qwen, standalone
OpenAI, enz.)? Per-platform notities bevinden zich in`extensions/adapters/`.

## Schermafdrukken

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
