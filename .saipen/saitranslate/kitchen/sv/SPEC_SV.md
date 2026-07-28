# SAIPEN-specifikation

## Sammanfattning
**Designmål #1: En kall agent utan chatthistorik måste kunna köra `/saipen continue` och återuppta produktivt arbete inom en minut, utan att be användaren att upprepa kontexten.**

SAIPEN garanterar att varje kompatibel AI-agent säkert kan fortsätta vilket projekt som helst utan att behöva briefas om. Det är ett ABI (Application Binary Interface) för AI-teknikagenter — ett kompatibilitetslager som löser minnesförlustproblemet. Oavsett om du använder Claude idag, Gemini imorgon, och GPT i övermorgon, kommer de alla att arbeta mot samma projektstatus utan att kräva att du upprepar kontexten.

### Kärnfilosofi: Projektstatus > Modellens minne
Minnet bör leva nära koden, inte inuti huvudet på en annan modell. SAIPEN skiftar paradigmet från `Projekt -> Minne -> LLM` till `Projekt -> SAIPEN-status -> LLM`. Minnet tillhör projektet.

I grund och botten använder SAIPEN ett bärbart, filbaserat fortsättningsprotokoll för LLM-agenter. Implementationer KAN variera. Kontraktet på disken MÅSTE förbli stabilt. Allt i detta protokoll finns till för att tjäna Fortsättningstestet (Continuation Test).

SAIPEN är evolutionärt, inte kreativt. Dess syfte är att slutföra mjukvara, inte att uppfinna den på nytt. ADD utökar befintliga designmönster, branschkonventioner och uppenbar funktionssymmetri.

- **`STATE`**: Finns till för att svara på *"Vad ska jag göra exakt nu?"*
- **`BOARD`**: Finns till för att svara på *"Vilken uppgift tar jag upp?"*
- **`LOG`**: Finns till för att svara på *"Varför kom vi till denna punkt?"*
- **`KNOWLEDGE`**: Finns till för att svara på *"Vad är den varaktiga sanningen i detta projekt?"*
- **`next_action`**: SAIPEN:s hjärta. Det svarar på *"Vilket exakt kommando kör jag exakt i denna sekund för att återuppta arbetet?"*

## SAIPEN-lackmustestet

Varje föreslagen ändring eller ny idé för protokollet MÅSTE klara följande tre frågor:
1. Gör det övergången mellan agenter mer tillförlitlig?
2. Gör det beteendet hos olika modeller mer enhetligt?
3. Minskar det sannolikheten för kontextförlust?

Om svaret är "nej" på minst två av dessa frågor, förkastas idén. SAIPEN prioriterar disciplin, reproducerbarhet och tillförlitlighet framför nyhet.

## Arkitektur

Protokollet är strikt normativt. SAIPEN delas konceptuellt in i två lager: **Kärna (Core)** och **Underhåll (Maintenance)**. 
- **Kärnlagret** garanterar säker, leverantörsoberoende uppgiftsfortsättning. 
- **Underhållslagret** är en autonom mjukvaruevolutionsmodell byggd ovanpå Kärnan.

Under de två lagren skiljer SAIPEN på tre ansvarsområden som aldrig trasslas samman:
**korrekthet och fortsättning** (Kärna -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, kapabilitetsförhandling, checkpointing), **oövervakad utveckling** (Underhåll -- `HUNT`/`ADD`/`CLEAN`, fullt funktionell under det vanliga `saipen`/`saipen continue`-standardläget), och **genomströmning** (Målläge (Goal Mode), Subagenter -- båda uttryckligen valfria (opt-in), §1.3/§2.4). Inaktivera Målläge: protokollet är oförändrat, ett ärende i taget. Inaktivera Subagenter: `HUNT` kör samma sex kategorier sekventiellt, med samma resultat. Använd enbart Kärnan, utan något Underhållslager alls: den håller fortfarande -- en kall agent återupptar ändå korrekt. Varje lager bygger på det underliggande utan att det omvända någonsin är sant; ingenting uppströms är beroende av att en funktion nedströms existerar.

```text
saipen/
  RFC.md                    normativ specifikation (uppdelad i Kärna och Underhåll)
  CONFORMANCE.md             självkontrollvektorer + tabell för scenariotäckning
  SKILL.md                  tunn ingångspunkt för kompetensläsande (skill-reading) plattformar
  STYLE.md                  röster: chatt, LOG.md, artefakter
  UI.md                     Mörkt Gyllene Win95 UI-spec (obligatorisk för UI-arbete)
  BOOT.md                   ~cold-startkärna: snabbvägen en bar `continue`
                             behöver, innan något av ovanstående laddats
  phases/                   strikt tillståndsmaskinlogik -- 16 dokument, ett per
                             RFC § 1.6 enum-värde (maskinkontrollerad båda vägar
                             av tools/validate.py)
    [Core Phases]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Maintenance Phases]
    hunt.md / markhunt.md / add.md / clean.md / translate.md

    [Infrastructure]
    prepare.md              paketerar arbete för överlämning till nästa agent
    validate.md             konformitetstestning

extensions/                 <- DET ADAPTIVA LAGRET
  adapters/                 instruktionsbryggor per modell, för plattformar som injektorn inte upptäcker automatiskt (README.md pekar hit)
  schemas/                  state.schema.json maskinläses av tools/validate.py (enda sanningen för STATE:s form); board/log-scheman förblir endast referens (se schemas/README.md)
  templates/                färsk .saipen/ standardkod (boilerplate)
  security/                 EXEMPEL-hook att kopiera in i ett projekt (RFC § 1.9, fäster till VERIFY)
  performance/              EXEMPEL-hook att kopiera in i ett projekt (RFC § 1.9, fäster till REVIEW)
  subs/                     EXEMPEL skrivskyddade forsknings-subagenter (RFC § 1.9) -- egen STATE/BOARD/LOG per subagent, resultat endast via OUTBOX, aldrig en andra skrivväg in i projektet

bootstrap/                  <- INSTALLERA/EXPORTERA/AVINSTALLERA, en maskin i taget
  inject.ps1 / .sh          installerar SAIPEN-blocket + skill-kopior (README Snabbstart)
  uninstall.ps1 / .sh       återställer injektion -- tar bort block + skill-kopior
  export.ps1 / .sh          arkiverar ett projekts .saipen/ för säkerhetskopiering
  saipen_crew.bat / .sh     öppnar 3-fönsters crew-layouten (bonus, extensions/subs/crew.md)

tools/                      <- KANONISK VALIDATOR & REPO-VERKTYG
  validate.py               kanonisk konformitetsvalidator (stdlib Python, noll installationer; validerar STATE mot state.schema.json direkt, plus grafkontroller som skal-paret inte kan göra)
  install_hook.py           installerar en pre-commit hook som kör validate.py
  uninstall_hook.py         tar bort exakt den hooken (återställer eventuell tidigare)

tests/                      <- KONFORMITETSLAGRET
  validate.ps1 / .sh        fryst portabel golvnivå för värdar utan Python -- nya kontroller landar endast i tools/validate.py
  scenarios/                fejkade tillstånd (mock states) (kraschåterställning, anspråkskonflikter, etc.)
```

## Tvåvägs Kapabilitetsförhandling
Agenter deklarerar inte bara vad de kan göra; protokollet kräver vad som behövs.
Projektet definierar `requires: [filesystem, git, shell, python]` i sin status. Agenten korsrefererar sina värdkapaciteter och låser sig i ett `mode` (t.ex. `full`, `read-only`).

## Grafbaserad Händelseloggning
Loggar i SAIPEN är inte linjära strängar. De bildar en acyklisk graf av beslut med hjälp av Händelse-ID:n (Event IDs, `E-001`). Detta möjliggör komplex förgrening, sammanslagning av agenter och exakta revisionsspår (audit trails).

## Arkitekturbeslutsposter (ADR)
Övergående händelseloggar rymmer inte permanent kunskap. SAIPEN kräver att strukturella arkitektoniska beslut lagras som ADR:er (t.ex. `KNOWLEDGE/ADR-001-use-sqlite.md`).

## Samtidighet & Distributionsgränser
SAIPEN säkerställer tillståndsintegritet via filbaserade anspråk (`owner`, `claim_time`) och sekventiella grafer (`LOG.md`). Emellertid är **SAIPEN ett tillståndsprotokoll, inte en distribuerad konsensusalgoritm.**
- **Lokalt/Delat Filsystem**: Konfliktlösning förlitar sig på atomiska filsystemskrivningar ("första incheckningen vinner").
- **Nätverksanslutna/Distribuerade Miljöer**: Om agenter arbetar över frånkopplade maskiner utan filsynkronisering i realtid, kommer kapplöpningsförhållanden (race conditions) på `BOARD.md`-anspråk att uppstå. I starkt distribuerade uppsättningar MÅSTE SAIPEN:s on-disk-protokollkontrakt förbli stabilt -- projektstatus i sig förändras ständigt, genom SAIPEN:s egna regler (§ 1.5 checkpointing), men formen på protokollet som de reglerna följer förändras aldrig.


<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stämpel" width="120"/>
</p>
