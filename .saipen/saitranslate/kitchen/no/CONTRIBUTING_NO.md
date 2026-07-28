# Bidra til SAIPEN

SAIPEN er først og fremst en spesifikasjon, deretter en implementasjon. De fleste bidrag
er endringer i `saipen/RFC.md`, en `phases/*.md`-fil, eller samsvarsverktøyene i `tests/` -- ikke applikasjonskode.

## Før du foreslår en endring

Kjør [SAIPEN Lakmustest](SPEC.md#the-saipen-litmus-test) mot din idé:
1. Gjør det overgangen mellom agenter mer pålitelig?
2. Gjør det atferden til ulike modeller mer ensartet?
3. Reduserer det sannsynligheten for konteksttap?

Hvis svaret er "nei" på minst to av disse, er det utenfor omfanget for denne
protokollen, uansett hvor nyttig det måtte være andre steder.

## Rapportere et gap

Åpne en sak (issue) som beskriver:
- hvilken fil/seksjon gapet er i (RFC.md, et fasedokument, et skjema, en test)
- konkrete bevis (et sitat, en kommando og dens utdata, et scenario hvor nåværende atferd feiler)
- hva du forventet i stedet

Vage rapporter ("dette føles feil") er vanskeligere å agere på enn en spesifikk
`grep`/reproduksjon. Se malen for feilrapportering for formen dette bør ha.

## Gjøre en endring

1. Les `saipen/RFC.md` og relevant(e) `phases/*.md`-fil(er) i sin helhet før
   du redigerer -- de fleste tilsynelatende gap viser seg å allerede være adressert andre steder,
   eller er bevisst avgrenset på en bestemt måte av en dokumentert grunn.
2. Sjekk `CHANGELOG.md` og `.saipen/KNOWLEDGE/decisions.md` for tidligere arbeid (prior art).
   Ikke gjenåpne en beslutning som allerede er tatt og avvist i stillhet --
   hvis du har nye bevis på at en tidligere avvisning var feil, si det eksplisitt
   i PR-beskrivelsen.
3. Hver normativ endring (et MÅ/MÅ IKKE/BØR) trenger en oppføring i `CHANGELOG.md`
   og, der det er praktisk mulig, dekning i `tests/validate.sh` +
   `tests/validate.ps1` (begge plattformer) eller en fixture under
   `tests/scenarios/`.
4. Kjør den kanoniske validatoren før du åpner en PR:
   ```bash
   python tools/validate.py
   ```
   Dette er den som teller -- den sjekker `STATE.md` mot `extensions/schemas/state.schema.json`, går gjennom `LOG.md` hendelsesgrafen over forseglede segmenter, og verifiserer kjøretidsmanifestet og injektortilkoblingene. `tests/validate.sh` / `validate.ps1` er den **frosne portable bunnlinjen** for verter uten Python (det står øverst i hver fil): færre sjekker, beholdt kun så en vert uten Python ikke står igjen med ingenting. Kjør dem også hvis endringen din påvirker en av dem, men aldri *istedenfor* -- å bestå bunnlinjen alene beviser mye mindre enn det ser ut til. CI kjører den kanoniske validatoren på hver push og PR uansett (`.github/workflows/validate.yml`).
5. Oppdater `VERSION` i henhold til skjemaet i `phases/ship.md` (patch for kun dokumentasjonsklargjøringer, minor for ny normativ atferd, major for kontraktbrytende endringer) og hold `README.md`s versjonsmerke synkronisert --
   `tests/validate.sh`/`.ps1` sjekker dette automatisk når det kjøres fra en
   klon av dette repoet.

## Stil

- Protokoll- og fasedokumenter: kortfattet, RFC-2119 nøkkelord der de betyr noe, ingen
  fyllord. Se `saipen/STYLE.md`.
- Alt i denne filen, commit-meldinger, kodekommentarer og CHANGELOG:
  enkelt og profesjonelt. Prosjektets egne chat-/LOGG-stemmer
  (`saipen/STYLE.md`) gjelder ikke for gjenstander (artifacts).

## Hva som er utenfor omfang

- Å gjøre SAIPEN om til et distribuert konsensussystem. Se
  `SPEC.md`s seksjon om Samtidighet & Distribusjonsgrenser.
- Maskinlesbar LOGG-markørgrammatikk utover det eksisterende skjelettet.
  `LOG.md` forblir prosa rundt en fast form.
- En `saipen doctor`-kommando eller lignende som er overflødig sammenlignet med `saipen validate` +
  `saipen status`.

Disse har hver blitt foreslått og evaluert før; gjenåpning av dem krever
nye bevis, ikke bare å spørre på nytt.
