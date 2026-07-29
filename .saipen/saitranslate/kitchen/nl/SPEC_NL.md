# SAIPEN Specificatie

## Samenvatting
**Ontwerpdoel #1: Een koude agent zonder chatgeschiedenis moet in staat zijn `/saipen continue` uit te voeren en binnen één minuut productief werk te hervatten, zonder de gebruiker te vragen context te herhalen.**

SAIPEN garandeert dat elke compatibele AI-agent elk project veilig kan voortzetten zonder opnieuw te worden geïnstrueerd. Het is een ABI (Application Binary Interface) voor engineering AI-agenten — een compatibiliteitslaag die het geheugenverliesprobleem oplost. Of u nu vandaag Claude, morgen Gemini en overmorgen GPT gebruikt, ze zullen allemaal op dezelfde projectstatus werken zonder dat u de context hoeft te herhalen.

### Kernfilosofie: Project Status > Model Geheugen
Het geheugen hoort bij de code te leven, niet in het hoofd van een ander model. SAIPEN verschuift het paradigma van `Project -> Geheugen -> LLM` naar `Project -> SAIPEN Status -> LLM`. Het geheugen is eigendom van het project.

In de kern gebruikt SAIPEN een draagbaar, bestandsgestuurd voortzettingsprotocol voor LLM-agenten. Implementaties MOGEN variëren. Het on-disk contract MOET stabiel blijven. Alles in dit protocol bestaat om de Voortzettingstest te dienen.

SAIPEN is evolutionair, niet creatief. Het doel is software voltooien, niet opnieuw uitvinden. ADD breidt bestaande ontwerppatronen, industrieconventies en voor de hand liggende functiesymmetrie uit.

- **`STATE`**: Bestaat om de vraag *"Wat moet ik nu doen?"* te beantwoorden.
- **`BOARD`**: Bestaat om de vraag *"Welke taak pak ik op?"* te beantwoorden.
- **`LOG`**: Bestaat om de vraag *"Waarom zijn we op dit punt aangekomen?"* te beantwoorden.
- **`KNOWLEDGE`**: Bestaat om de vraag *"Wat is de blijvende waarheid van dit project?"* te beantwoorden.
- **`next_action`**: Het hart van SAIPEN. Het beantwoordt *"Welk exact commando voer ik op dit moment uit om het werk te hervatten?"*

## De SAIPEN Lakmoesproef

Elke voorgestelde wijziging of nieuw idee voor het protocol MOET de volgende drie vragen doorstaan:
1. Maakt het de overgang tussen agenten betrouwbaarder?
2. Maakt het het gedrag van verschillende modellen uniformer?
3. Vermindert het de kans op contextverlies?

Als het antwoord op ten minste twee van deze vragen "nee" is, wordt het idee afgewezen. SAIPEN geeft voorrang aan discipline, reproduceerbaarheid en betrouwbaarheid boven nieuwheid.

## Architectuur

Het protocol is strikt normatief. SAIPEN is conceptueel verdeeld in twee lagen: **Kern** en **Onderhoud**. 
- **De Kernlaag** garandeert veilige, leverancier-neutrale taakvoortzetting. 
- **De Onderhoudslaag** is een autonoom software-evolutiemodel gebouwd bovenop de Kern.

Onder de twee lagen scheidt SAIPEN drie zorgen die nooit verstrikt raken:
**correctheid en voortzetting** (Kern -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, capaciteitsonderhandeling, checkpointing), **onbeheerde evolutie** (Onderhoud -- `HUNT`/`ADD`/`CLEAN`, volledig functioneel onder de standaard `saipen`/`saipen continue`), en **doorvoercapaciteit** (Doel Modus, Subagenten -- beide expliciet opt-in, §1.3/§2.4). Schakel Doel Modus uit: het protocol is ongewijzigd, één ticket tegelijk. Schakel Subagenten uit: `HUNT` voert dezelfde zes categorieën opeenvolgend uit, hetzelfde resultaat. Gebruik alleen Kern, zonder enige Onderhoudslaag: het blijft overeind -- een koude agent hervat nog steeds correct. Elke laag bouwt voort op degene eronder zonder dat het omgekeerde ooit waar is; niets stroomopwaarts is afhankelijk van het bestaan van een stroomafwaartse functie.

```text
saipen/
  RFC.md                    normatieve specificatie (verdeeld in Kern en Onderhoud)
  CONFORMANCE.md             zelftestvectoren + scenariodekkingstabel
  SKILL.md                  dunne ingang voor vaardigheid-lezende platformen
  STYLE.md                  stemmen: chat, LOG.md, artefacten
  UI.md                     Vintage Golden UI specificatie (verplicht voor UI werk)
  BOOT.md                   ~cold-start kernel: het snelle pad dat een kale
                             `continue` nodig heeft, voordat bovenstaande wordt geladen
  phases/                   strikte statusmachinelogica -- 16 docs, één per
                             RFC § 1.6 enumwaarde (machine-gecontroleerd beide
                             richtingen door tools/validate.py)
    [Kern Fasen]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Onderhouds Fasen]
    hunt.md / markhunt.md / add.md / clean.md / translate.md

    [Infrastructuur]
    prepare.md              werk verpakken voor overdracht aan de volgende agent
    validate.md             conformiteitstesten

extensions/                 <- DE ADAPTIEVE LAAG
  adapters/                 per-model instructiebruggen, voor platformen die de injector niet automatisch detecteert (README.md wijst hiernaar)
  schemas/                  state.schema.json wordt machinaal gelezen door tools/validate.py (enkele bron van waarheid voor de vorm van STATE); board/log schema's blijven alleen ter referentie (zie schemas/README.md)
  templates/                verse .saipen/ boilerplate
  security/                 VOORBEELD hook om te kopiëren naar een project (RFC § 1.9, hecht aan VERIFY)
  performance/              VOORBEELD hook om te kopiëren naar een project (RFC § 1.9, hecht aan REVIEW)
  subs/                     VOORBEELD alleen-lezen onderzoeks-subagenten (RFC § 1.9) -- eigen STATE/BOARD/LOG per subagent, bevindingen alleen via OUTBOX, nooit een tweede schrijfpad het project in

bootstrap/                  <- INSTALLATIE/EXPORT/DE-INSTALLATIE, één machine tegelijk
  inject.ps1 / .sh          installeert het SAIPEN blok + vaardigheidskopieën (README Snelstart)
  uninstall.ps1 / .sh       draait inject om -- verwijdert blokken + vaardigheidskopieën
  export.ps1 / .sh          archiveert een project's .saipen/ voor back-up
  saipen_crew.bat / .sh     opent de 3-venster crew lay-out (bonus, extensions/subs/crew.md)

tools/                      <- CANONIEKE VALIDATOR & REPO UTILITIES
  validate.py               canonieke conformiteitsvalidator (stdlib Python, nul installaties; valideert STATE direct tegen state.schema.json, plus grafiekcontroles die het shell-paar niet kan doen)
  install_hook.py           installeert een pre-commit hook die validate.py uitvoert
  uninstall_hook.py         verwijdert exact die hook (herstelt eventuele vorige)

tests/                      <- CONFORMITEITSLAAG
  validate.ps1 / .sh        bevroren draagbare basis voor hosts zonder Python -- nieuwe controles landen alleen in tools/validate.py
  scenarios/                nepstatussen (crash-herstel, claim-conflicten, enz.)
```

## Tweerichtings Capaciteitsonderhandeling
Agenten verklaren niet simpelweg wat ze kunnen doen; het protocol eist wat vereist is.
Het project definieert `requires: [filesystem, git, shell, python]` in zijn status. De agent vergelijkt zijn hostcapaciteiten met de vereisten en vergrendelt in een `mode` (bijv. `full`, `read-only`).

## Grafiekgebaseerde Gebeurtenisregistratie
Logs in SAIPEN zijn geen lineaire strings. Ze vormen een acyclische grafiek van beslissingen met behulp van Gebeurtenis-ID's (`E-001`). Dit maakt complexe vertakkingen, agent-samenvoeging en nauwkeurige audit trails mogelijk.

## Architectuur Beslissingsrecords (ADR)
Tijdelijke gebeurtenislogboeken bevatten geen permanente kennis. SAIPEN vereist dat structurele architecturale beslissingen worden bewaard als ADR's (bijv. `KNOWLEDGE/ADR-001-use-sqlite.md`).

## Gelijktijdigheid & Distributiegrenzen
SAIPEN zorgt voor statusintegriteit via bestandsgebaseerde claims (`owner`, `claim_time`) en sequentiële grafieken (`LOG.md`). Echter, **SAIPEN is een statusprotocol, geen gedistribueerd consensusalgoritme.**
- **Lokaal/Gedeeld Bestandssysteem**: Conflictresolutie is afhankelijk van atomaire bestandssysteem-schrijfacties ("eerste commit wint").
- **Genetwerkte/Gedistribueerde Omgevingen**: Als agenten over losgekoppelde machines opereren zonder real-time bestandssynchronisatie, zullen racecondities op `BOARD.md` claims optreden. In sterk gedistribueerde opstellingen MOET het SAIPEN on-disk protocol contract stabiel blijven -- de projectstatus zelf muteert voortdurend door SAIPEN's eigen regels (§ 1.5 checkpointing), nooit de protocolvorm die die regels volgen.


<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
