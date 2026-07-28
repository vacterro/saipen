# Bidrag til SAIPEN

SAIPEN er først og fremmest en specifikation, sekundært en implementering. De fleste bidrag er ændringer til `saipen/RFC.md`, en `phases/*.md` fil, eller overensstemmelsesværktøjerne i `tests/` -- ikke applikationskode.

## Før du foreslår en ændring

Kør [SAIPEN Lakmustesten](SPEC.md#the-saipen-litmus-test) mod din idé:
1. Gør den overgangen mellem agenter mere pålidelig?
2. Gør den adfærden for forskellige modeller mere ensartet?
3. Reducerer den sandsynligheden for tab af kontekst?

Hvis svaret er "nej" til mindst to af disse, falder det uden for denne protokols omfang, uanset hvor nyttigt det måtte være andetsteds.

## Rapportering af en mangel

Åbn et issue der beskriver:
- hvilken fil/sektion manglen er i (RFC.md, et fasedokument, et skema, en test)
- det konkrete bevis (et citat, en kommando og dens output, et scenarie hvor den nuværende adfærd går i stykker)
- hvad du i stedet ville forvente

Vage rapporter ("dette føles forkert") er sværere at handle på end et specifikt `grep`/reproduktion. Se skabelonen til fejlrapporter for, hvilken form dette skal have.

## Sådan foretager du en ændring

1. Læs `saipen/RFC.md` og de(n) relevante `phases/*.md` fil(er) fuldstændigt, før du redigerer -- de fleste tilsyneladende mangler viser sig allerede at være behandlet andre steder, eller bevidst afgrænset på en bestemt måde af en dokumenteret årsag.
2. Tjek `CHANGELOG.md` og `.saipen/KNOWLEDGE/decisions.md` for tidligere arbejde. Genåbn ikke stiltiende en beslutning, der allerede blev truffet og afvist -- hvis du har nye beviser for at en tidligere afvisning var forkert, så sig det udtrykkeligt i PR-beskrivelsen.
3. Enhver normativ ændring (et SKAL/SKAL IKKE/BØR) kræver en indtastning i `CHANGELOG.md` og, hvor det er praktisk muligt, dækning i `tests/validate.sh` + `tests/validate.ps1` (begge platforme) eller en fixtur under `tests/scenarios/`.
4. Kør den kanoniske validator før du åbner en PR:
   ```bash
   python tools/validate.py
   ```
   Det er denne, der betyder noget -- den tjekker STATE.md mod extensions/schemas/state.schema.json, gennemgår LOG.md hændelsesgrafen på tværs af forseglede segmenter og verificerer runtime-manifestet og injector-forbindelsen. tests/validate.sh / validate.ps1 er det frosne bærbare gulv for værter uden Python (de siger det i toppen af hver fil): færre kontroller, kun bevaret så en vært uden Python ikke efterlades uden noget. Kør dem også, hvis din ændring berører nogen af dem, men aldrig i stedet for -- at bestå gulvet alene beviser meget mindre, end det ser ud til. CI kører den kanoniske validator ved hvert push og PR uanset (.github/workflows/validate.yml).
5. Opdater `VERSION` i henhold til skemaet i `phases/ship.md` (patch for kun dokumentationsafklaringer, minor for ny normativ adfærd, major for ændringer der bryder kontrakten) og hold versionsbadgen i `README.md` synkroniseret -- `tests/validate.sh`/`.ps1` tjekker dette automatisk, når de køres fra en klon af dette repo.

## Stil

- Protokol og fasedokumenter: kortfattet, RFC-2119 nøgleord hvor de betyder noget, ingen fyldord. Se `saipen/STYLE.md`.
- Alt i denne fil, commit-beskeder, kodekommentarer og CHANGELOG: enkelt og professionelt. Projektets egne chat-/LOG-stemmer (`saipen/STYLE.md`) gælder ikke for artefakter.

## Hvad der falder udenfor rammerne

- At gøre SAIPEN til et distribueret konsensussystem. Se afsnittet 'Samtidighed & Distributionsgrænser' i `SPEC.md`.
- Maskin-parsbar LOG-markørgrammatik udover det eksisterende skelet. `LOG.md` forbliver prosa omkring en fast form.
- En `saipen doctor` kommando eller lignende, der er overflødig ift. `saipen validate` + `saipen status`.

Disse er alle blevet foreslået og evalueret før; for at genåbne dem kræves nye beviser, ikke bare at spørge igen.

