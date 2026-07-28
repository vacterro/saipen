# SAIPEN Specifikation

## Abstrakt
**Designmål #1: En kold agent uden chathistorik skal kunne udføre `/saipen continue` og genoptage produktivt arbejde inden for et minut uden at bede brugeren om at gentage kontekst.**

SAIPEN garanterer, at enhver kompatibel AI-agent sikkert kan fortsætte ethvert projekt uden at blive briefet på ny. Det er en ABI (Application Binary Interface) for AI-ingeniøragenter - et kompatibilitetslag, der løser problemet med hukommelsestab. Uanset om du bruger Claude i dag, Gemini i morgen og GPT i overmorgen, vil de alle operere mod den samme projekttilstand uden at kræve, at du gentager konteksten.

### Kernefilosofi: Projekttilstand > Modelhukommelse
Hukommelsen bør leve ved siden af koden, ikke inde i hovedet på en anden model. SAIPEN ændrer paradigmet fra `Projekt -> Hukommelse -> LLM` til `Projekt -> SAIPEN State -> LLM`. Hukommelsen tilhører projektet.

I sin kerne bruger SAIPEN en portabel, filstøttet fortsættelsesprotokol for LLM-agenter. Implementeringer KAN variere. On-disk kontrakten SKAL forblive stabil. Alt i denne protokol eksisterer for at tjene Fortsættelsestesten (Continuation Test).

SAIPEN er evolutionær, ikke kreativ. Dens formål er at færdiggøre software, ikke genopfinde den. ADD udvider eksisterende designmønstre, branchekonventioner og åbenlys funktionssymmetri.

- **`STATE`**: Eksisterer for at besvare *"Hvad gør jeg lige nu?"*
- **`BOARD`**: Eksisterer for at besvare *"Hvilken opgave tager jeg fat på?"*
- **`LOG`**: Eksisterer for at besvare *"Hvorfor er vi nået til dette punkt?"*
- **`KNOWLEDGE`**: Eksisterer for at besvare *"Hvad er den varige sandhed i dette projekt?"*
- **`next_action`**: Hjertet i SAIPEN. Det besvarer *"Hvilken præcis kommando udfører jeg lige i dette sekund for at genoptage arbejdet?"*

## SAIPEN Lakmustesten

Enhver foreslået ændring eller ny idé til protokollen SKAL bestå følgende tre spørgsmål:
1. Gør den overgangen mellem agenter mere pålidelig?
2. Gør den adfærden for forskellige modeller mere ensartet?
3. Reducerer den sandsynligheden for tab af kontekst?

Hvis svaret er "nej" til mindst to af disse spørgsmål, afvises ideen. SAIPEN prioriterer disciplin, reproducerbarhed og pålidelighed over nyhedsværdi.

## Arkitektur

Protokollen er strengt normativ. SAIPEN opdeles konceptuelt i to lag: **Kerne (Core)** og **Vedligeholdelse (Maintenance)**. 
- **Kerne-laget** garanterer sikker, leverandørneutral opgavefortsættelse. 
- **Vedligeholdelses-laget** er en autonom softwareevolutionsmodel bygget oven på Kernen.

Nedenunder de to lag adskiller SAIPEN tre ansvarsområder, der aldrig flettes sammen:
**korrekthed og fortsættelse** (Kerne -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, evneforhandling, tjekpunkter), **ubemandet evolution** (Vedligeholdelse -- `HUNT`/`ADD`/`CLEAN`, fuldt funktionel under den rene `saipen`/`saipen continue` standard), og **gennemløb** (Goal Mode, Subagents -- begge udtrykkeligt tilvalg, §1.3/§2.4). Deaktiver Goal Mode: protokollen er uændret, én billet ad gangen. Deaktiver Subagents: `HUNT` kører de samme seks kategorier sekventielt, samme resultat. Brug Kernen alene, uden noget Vedligeholdelseslag overhovedet: det holder stadig -- en kold agent genoptager stadig korrekt. Hvert lag bygger på det underliggende uden at det omvendte nogensinde er sandt; intet opstrøms afhænger af at en nedstrømsfunktion eksisterer.

```text
saipen/
  RFC.md                    normativ specifikation (opdelt i Kerne og Vedligeholdelse)
  CONFORMANCE.md             selv-tjek vektorer + scenariedækningstabel
  SKILL.md                  tyndt indgangspunkt for platforme der læser skills
  STYLE.md                  stemmer: chat, LOG.md, artefakter
  UI.md                     Mørk Gylden Win95 UI specifikation (obligatorisk for UI-arbejde)
  BOOT.md                   boot-sekvens / koldstartsorkestrering
  phases/                   16 docs, one per RFC § 1.6 enum value (machine-checked both ways by tools/validate.py)
    [Core Phases]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Maintenance Phases]
    hunt.md / add.md / clean.md / translate.md / markhunt.md

  [Infrastructure]
  prepare.md                workspace-forberedelse
  validate.md               overordnet overensstemmelsestest

extensions/                 <- DET ADAPTIVE LAG
  adapters/                 model-specifikke instruktionsbroer, for platforme injektoren
                             ikke autodetekterer (README.md peger hertil)
  schemas/                  state.schema.json læses af maskine af tools/validate.py
                             (eneste kilde til sandhed for STATE's form); board/log
                             skemaer forbliver kun til reference (se schemas/README.md)
  templates/                frisk .saipen/ boilerplate
  security/                 EKSEMPEL hook til at kopiere ind i et projekt (RFC § 1.9, knyttes til VERIFY)
  performance/              EKSEMPEL hook til at kopiere ind i et projekt (RFC § 1.9, knyttes til REVIEW)
  subs/                     EKSEMPEL read-only forsknings-subagenter (RFC § 1.9) -- egen
                             STATE/BOARD/LOG pr. subagent, resultater kun via OUTBOX,
                             aldrig en anden skrivevej ind i projektet

bootstrap/                  <- INSTALLER/EKSPORTER/AFINSTALLER, én maskine ad gangen
  inject.ps1 / .sh          installerer SAIPEN-blokken + skill kopier (README Hurtig Start)
  uninstall.ps1 / .sh       omvender inject -- fjerner blokke + skill kopier
  export.ps1 / .sh          arkiverer et projekts .saipen/ for backup
  saipen_crew.bat / .sh     starter SAIPEN crew-værktøjet

tools/                      <- KANONISK VALIDATOR & REPO VÆRKTØJER
  validate.py               kanonisk overensstemmelsesvalidator (stdlib Python, nul
                             installationer; validerer STATE mod state.schema.json
                             direkte, plus graf-tjek som shell-parret ikke kan gøre)
  install_hook.py           installerer en pre-commit hook der kører validate.py
  uninstall_hook.py         fjerner præcis den hook (gendanner evt. tidligere hook)

tests/                      <- OVERENSSTEMMELSESLAG
  validate.ps1 / .sh        frosset bærbar bund for værter uden Python --
                             nye tjek lander kun i tools/validate.py
  scenarios/                mock-tilstande (nedbrudsgendannelse, kravkonflikter, osv.)
```

## To-Vejs Evneforhandling
Agenter erklærer ikke bare, hvad de kan gøre; protokollen kræver, hvad der er nødvendigt.
Projektet definerer `requires: [filesystem, git, shell, python]` i sin tilstand. Agenten krydsrefererer sine værtskapaciteter og låser sig fast i en `mode` (f.eks. `full`, `read-only`).

## Graf-Baseret Hændelseslogning
Logs i SAIPEN er ikke lineære strenge. De danner en acyklisk graf af beslutninger ved hjælp af Hændelses-ID'er (Event IDs - `E-001`). Dette tillader kompleks forgrening, sammensmeltning af agenter og præcise revisionsspor.

## Architecture Decision Records (ADR)
Forbigående hændelseslogs huser ikke permanent viden. SAIPEN kræver, at strukturelle arkitektoniske beslutninger bevares som ADR'er (f.eks. `KNOWLEDGE/ADR-001-use-sqlite.md`).

## Samtidighed & Distributionsgrænser
SAIPEN sikrer tilstandsintegritet via filbaserede krav (`owner`, `claim_time`) og sekventielle grafer (`LOG.md`). Men, **SAIPEN er en tilstandsprotokol, ikke en distribueret konsensusalgoritme.**
- **Lokal/Delt Filsystem**: Konfliktløsning afhænger af atomiske filsystemskrivninger ("første commit vinder").
- **Netværks-/Distribuerede Miljøer**: Hvis agenter opererer på tværs af afbrudte maskiner uden filsynkronisering i realtid, vil der opstå race conditions på `BOARD.md` krav. I stærkt distribuerede opsætninger SKAL SAIPEN's on-disk protokolkontrakt forblive stabil -- selve projekttilstanden muterer stadig konstant, gennem SAIPEN's egne regler (§ 1.5 tjekpunkter), men aldrig protokolformen som disse regler følger.


<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
