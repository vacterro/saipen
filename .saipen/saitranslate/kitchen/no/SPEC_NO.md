# SAIPEN Spesifikasjon

## Abstrakt
**Designmål #1: En kald agent med null chathistorikk må kunne utføre `/saipen continue` og gjenoppta produktivt arbeid innen ett minutt, uten å be brukeren gjenta konteksten.**

SAIPEN garanterer at enhver kompatibel AI-agent trygt kan fortsette ethvert prosjekt uten å bli briefet på nytt. Det er et ABI (Application Binary Interface) for utvikling av AI-agenter – et kompatibilitetslag som løser hukommelsestapsproblemet. Enten du bruker Claude i dag, Gemini i morgen, og GPT dagen etter, vil de alle operere mot den samme prosjektstatusen uten at du må gjenta konteksten.

### Kjernefilosofi: Prosjektstatus > Modellminne
Minnet skal leve sammen med koden, ikke inne i hodet på en annen modell. SAIPEN flytter paradigmet fra `Prosjekt -> Minne -> LLM` til `Prosjekt -> SAIPEN Status -> LLM`. Minnet tilhører prosjektet.

Kjernen i SAIPEN bruker en portabel, filstøttet kontinuitetsprotokoll for LLM-agenter. Implementasjoner KAN variere. Kontrakten på disk MÅ forbli stabil. Alt i denne protokollen eksisterer for å tjene Kontinuitetstesten.

SAIPEN er evolusjonær, ikke kreativ. Dens formål er å fullføre programvare, ikke gjenoppfinne den. ADD utvider eksisterende designmønstre, bransjekonvensjoner, og åpenbar funksjonssymmetri.

- **`STATE`**: Eksisterer for å svare på *"Hva gjør jeg akkurat nå?"*
- **`BOARD`**: Eksisterer for å svare på *"Hvilken oppgave plukker jeg opp?"*
- **`LOG`**: Eksisterer for å svare på *"Hvorfor kom vi til dette punktet?"*
- **`KNOWLEDGE`**: Eksisterer for å svare på *"Hva er den varige sannheten i dette prosjektet?"*
- **`next_action`**: Hjertet av SAIPEN. Det svarer på *"Hvilken eksakt kommando utfører jeg akkurat nå for å gjenoppta arbeidet?"*

## SAIPEN Lakmustest

Ethvert foreslått endring eller ny idé for protokollen MÅ bestå følgende tre spørsmål:
1. Gjør det overgangen mellom agenter mer pålitelig?
2. Gjør det atferden til ulike modeller mer ensartet?
3. Reduserer det sannsynligheten for konteksttap?

Hvis svaret er "nei" på minst to av disse spørsmålene, avvises ideen. SAIPEN prioriterer disiplin, reproduserbarhet og pålitelighet over nyhet.

## Arkitektur

Protokollen er strengt normativ. SAIPEN deles konseptuelt inn i to lag: **Kjerne** og **Vedlikehold**.
- **Kjernelaget** garanterer trygg, leverandørnøytral oppgavekontinuitet.
- **Vedlikeholdslaget** er en autonom modell for programvareevolusjon bygget på toppen av Kjerne.

Under de to lagene, separerer SAIPEN tre bekymringer som aldri blandes:
**korrekthet og kontinuitet** (Kjerne -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, forhandling av funksjoner, sjekkpunkt), **uovervåket evolusjon** (Vedlikehold -- `HUNT`/`ADD`/`CLEAN`, fullt funksjonell under standard `saipen`/`saipen continue`), og **gjennomstrømming** (Målmodus, Subagenter -- begge eksplisitt valgfrie, §1.3/§2.4). Deaktiver Målmodus: protokollen er uendret, én oppgave om gangen. Deaktiver Subagenter: `HUNT` kjører de samme seks kategoriene sekvensielt, samme resultat. Bruk kun Kjerne, uten noe Vedlikeholdslag i det hele tatt: det holder fortsatt -- en kald agent gjenopptar fortsatt korrekt. Hvert lag bygger på det underliggende uten at det motsatte noen gang er sant; ingenting oppstrøms er avhengig av at en nedstrøms funksjon eksisterer.

```text
saipen/
  RFC.md                    normativ spesifikasjon (delt i Kjerne og Vedlikehold)
  CONFORMANCE.md             selvsjekk vektorer + scenariedekningstabell
  SKILL.md                  tynt inngangspunkt for ferdighetslesende plattformer
  STYLE.md                  stemmer: chat, LOG.md, gjenstander
  UI.md                     Vintage Golden UI spesifikasjon (obligatorisk for UI-arbeid)
  BOOT.md                   ~cold-start kjerne: den raske stien en bar
                             `continue` trenger, før noen av ovenstående er lastet
  phases/                   streng tilstandsmaskinlogikk -- 16 docs, én per
                             RFC § 1.6 enum-verdi (maskin-sjekket begge
                             veier av tools/validate.py)
    [Kjernefaser]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Vedlikeholdsfaser]
    hunt.md / markhunt.md / add.md / clean.md / translate.md

    [Infrastruktur]
    prepare.md              pakke arbeid for overlevering til neste agent
    validate.md             samsvarstesting

extensions/                 <- DET ADAPTIVE LAGET
  adapters/                 instruksjonsbroer per modell, for plattformer injektoren
                             ikke automatisk oppdager (README.md peker hit)
  schemas/                  state.schema.json leses av maskin via tools/validate.py
                             (eneste sannhetskilde for STATEs form); board/log
                             skjemaer forblir kun for referanse (se schemas/README.md)
  templates/                fersk .saipen/ boilerplate
  security/                 EKSEMPEL-hook til å kopiere inn i et prosjekt (RFC § 1.9, festes til VERIFY)
  performance/              EKSEMPEL-hook til å kopiere inn i et prosjekt (RFC § 1.9, festes til REVIEW)
  subs/                     EKSEMPEL skrivebeskyttede forskningssubagenter (RFC § 1.9) -- egen
                             STATE/BOARD/LOG per subagent, funn kun via OUTBOX,
                             aldri en andre skrivevei inn i prosjektet

bootstrap/                  <- INSTALLER/EKSPORTER/AVINSTALLER, én maskin om gangen
  inject.ps1 / .sh          installerer SAIPEN-blokk + ferdighetskopier (README Hurtigstart)
  uninstall.ps1 / .sh       reverserer inject -- fjerner blokker + ferdighetskopier
  export.ps1 / .sh          arkiverer et prosjekts .saipen/ for sikkerhetskopiering
  saipen_crew.bat / .sh     åpner 3-vinduets crew-oppsett (bonus, extensions/subs/crew.md)

tools/                      <- KANONISK VALIDATOR & REPO VERKTØY
  validate.py               kanonisk samsvarsvalidator (stdlib Python, null
                             installasjoner; validerer STATE direkte mot state.schema.json,
                             pluss grafsjekker som shell-paret ikke kan gjøre)
  install_hook.py           installerer en pre-commit hook som kjører validate.py
  uninstall_hook.py         fjerner nøyaktig den hooken (gjenoppretter evt. tidligere)

tests/                      <- SAMSVARSLAG
  validate.ps1 / .sh        fryst bærbar base for verter uten Python --
                             nye sjekker lander bare i tools/validate.py
  scenarios/                mock-tilstander (krasj-gjenoppretting, krav-konflikter, etc.)
```

## Toveis Funksjonsforhandling
Agenter erklærer ikke bare hva de kan gjøre; protokollen krever hva som er nødvendig.
Prosjektet definerer `requires: [filesystem, git, shell, python]` i sin tilstand. Agenten kryssrefererer sine vertsegenskaper mot kravene og låser seg i en `mode` (f.eks. `full`, `read-only`).

## Grafbasert Hendelseslogging
Logger i SAIPEN er ikke lineære strenger. De danner en asyklisk graf av beslutninger ved bruk av Hendelses-IDer (`E-001`). Dette tillater kompleks forgrening, sammenslåing av agenter, og presise revisjonsspor.

## Arkitekturbeslutningsposter (ADR)
Forbigående hendelseslogger inneholder ikke permanent kunnskap. SAIPEN krever at strukturelle arkitektoniske beslutninger bevares som ADRer (f.eks. `KNOWLEDGE/ADR-001-use-sqlite.md`).

## Samtidighet & Distribusjonsgrenser
SAIPEN sikrer tilstandsintegritet via filbaserte krav (`owner`, `claim_time`) og sekvensielle grafer (`LOG.md`). Imidlertid er **SAIPEN en tilstandsprotokoll, ikke en distribuert konsensusalgoritme.**
- **Lokalt/Delt Filsystem**: Konfliktløsning er avhengig av atomiske filsystemskrivinger ("første commit vinner").
- **Nettverks-/Distribuerte Miljøer**: Hvis agenter opererer på tvers av frakoblede maskiner uten sanntids filsynkronisering, vil kappløpssituasjoner (race conditions) på `BOARD.md`-krav oppstå. I svært distribuerte oppsett MÅ SAIPEN-kontrakten på disk forbli stabil -- selve prosjekttilstanden muterer fortsatt kontinuerlig, gjennom SAIPENs egne regler (§ 1.5 sjekkpunkt), aldri protokollformen de reglene følger.

<p align="center">
  <img src="../../assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
