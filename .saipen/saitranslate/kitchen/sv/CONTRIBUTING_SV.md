# Bidra till SAIPEN

SAIPEN är en specifikation i första hand, en implementation i andra hand. De flesta bidrag är ändringar i `saipen/RFC.md`, en `phases/*.md`-fil, eller överensstämmelseverktygen i `tests/` -- inte applikationskod.

## Innan du föreslår en ändring

Kör [SAIPEN-lackmustestet](SPEC.md#the-saipen-litmus-test) mot din idé:
1. Gör den övergången mellan agenter mer tillförlitlig?
2. Gör den beteendet hos olika modeller mer enhetligt?
3. Minskar den sannolikheten för kontextförlust?

Om svaret är "nej" på minst två av dessa, ligger det utanför ramen för detta protokoll, oavsett hur användbart det kan vara någon annanstans.

## Rapportera en lucka

Öppna ett ärende som beskriver:
- vilken fil/sektion luckan finns i (RFC.md, ett fasdokument, ett schema, ett test)
- det konkreta beviset (ett citat, ett kommando och dess utdata, ett scenario där nuvarande beteende går sönder)
- vad du förväntar dig istället

Vaga rapporter ("detta känns fel") är svårare att agera på än en specifik `grep`/reproduktion. Se mallen för felrapporter för vilken form detta bör ha.

## Göra en ändring

1. Läs `saipen/RFC.md` och relevanta `phases/*.md`-filer helt innan du redigerar -- de flesta uppenbara luckor visar sig redan vara hanterade någon annanstans, eller medvetet avgränsade på ett visst sätt av en dokumenterad anledning.
2. Kontrollera `CHANGELOG.md` och `.saipen/KNOWLEDGE/decisions.md` för tidigare arbete. Återuppta inte tyst ett beslut som redan fattats och avslagits -- om du har nya bevis för att ett tidigare avslag var fel, säg det uttryckligen i PR-beskrivningen.
3. Varje normativ ändring (ett MÅSTE/FÅR INTE/BÖR) behöver en post i `CHANGELOG.md` och, där det är praktiskt, täckning i `tests/validate.sh` + `tests/validate.ps1` (båda plattformarna) eller en fixtur under `tests/scenarios/`.
4. Kör den kanoniska valideraren innan du öppnar en PR:
   ```bash
   python tools/validate.py
   ```
   Detta är den som räknas – den kontrollerar `STATE.md` mot
   `extensions/schemas/state.schema.json`, går igenom `LOG.md` händelsegrafen
   över förseglade segment och verifierar runtime-manifestet samt
   injectorkopplingar. `tests/validate.sh` / `validate.ps1` är **frusna
   portabla golv** för värdar utan Python (det står överst i varje fil):
   färre kontroller, behålls bara så att en värd utan Python inte lämnas
   utan något. Kör dem också om din ändring påverkar någon av dem, men aldrig
   *istället* – att klara enbart golvet bevisar mycket mindre än det ser ut
   att göra. CI kör den kanoniska valideraren vid varje push och PR oavsett
   (`.github/workflows/validate.yml`).
5. Uppdatera `VERSION` enligt schemat i `phases/ship.md` (patch för förtydliganden av enbart dokumentation, minor för nytt normativt beteende, major för brytande kontraktsändringar) och håll `README.md`:s versionsbricka synkroniserad -- `tests/validate.sh`/`.ps1` kontrollerar detta automatiskt när de körs från en klon av detta repo.

## Stil

- Protokoll- och fasdokument: korta, RFC-2119-nyckelord där de spelar roll, ingen utfyllnad. Se `saipen/STYLE.md`.
- Allt i denna fil, incheckningsmeddelanden, kodkommentarer och CHANGELOG: enkelt och professionellt. Projektets egna chatt-/LOG-röster (`saipen/STYLE.md`) gäller inte för artefakter.

## Vad som ligger utanför ramen

- Att göra SAIPEN till ett distribuerat konsensussystem. Se sektionen Concurrency & Distribution Boundaries i `SPEC.md`.
- Maskinläsbar LOG-markörgrammatik utöver den befintliga stommen. `LOG.md` förblir prosa runt en fast form.
- Ett `saipen doctor`-kommando eller liknande som är redundant med `saipen validate` + `saipen status`.

Dessa har alla föreslagits och utvärderats tidigare; att ta upp dem igen kräver nya bevis, inte bara att man frågar om.
