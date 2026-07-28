# Contribuire a SAIPEN

SAIPEN è una specifica prima di tutto, un'implementazione in secondo luogo. La maggior parte dei contributi sono modifiche a `saipen/RFC.md`, a un file `phases/*.md`, o agli strumenti di conformità in `tests/` -- non codice applicativo.

## Prima di proporre una modifica

Esegui il [Test di Tornasole di SAIPEN](SPEC.md#the-saipen-litmus-test) contro la tua idea:
1. Rende la transizione tra agenti più affidabile?
2. Rende il comportamento di modelli diversi più uniforme?
3. Riduce la probabilità di perdita di contesto?

Se la risposta è "no" ad almeno due di queste domande, è fuori dall'ambito per questo protocollo, per quanto possa essere utile altrove.

## Segnalare una lacuna

Apri una issue descrivendo:
- in quale file/sezione si trova la lacuna (RFC.md, un documento di fase, uno schema, un test)
- l'evidenza concreta (una citazione, un comando e il suo output, uno scenario in cui il comportamento attuale si interrompe)
- cosa ti aspetteresti invece

Rapporti vaghi ("questo sembra sbagliato") sono più difficili da gestire rispetto a un `grep`/riproduzione specifici. Consulta il template della issue per le segnalazioni di bug per capire la forma che questo dovrebbe avere.

## Effettuare una modifica

1. Leggi interamente `saipen/RFC.md` e i file `phases/*.md` rilevanti prima di modificare -- la maggior parte delle lacune apparenti si rivelano essere già affrontate altrove, o deliberatamente limitate in un certo modo per un motivo documentato.
2. Controlla `CHANGELOG.md` e `.saipen/KNOWLEDGE/decisions.md` per i precedenti. Non riaprire silenziosamente una decisione che è già stata presa e respinta -- se hai nuove prove che un rifiuto passato era sbagliato, dillo esplicitamente nella descrizione della PR.
3. Ogni modifica normativa (un MUST/MUST NOT/SHOULD) necessita di una voce nel `CHANGELOG.md` e, ove pratico, di copertura in `tests/validate.sh` + `tests/validate.ps1` (entrambe le piattaforme) o di una fixture in `tests/scenarios/`.
4. Esegui il validatore canonico prima di aprire una PR:
   ```bash
   python tools/validate.py
   ```
   Questo è quello che conta -- controlla `STATE.md` rispetto a
   `extensions/schemas/state.schema.json`, percorre il grafo degli eventi `LOG.md`
   attraverso i segmenti sigillati e verifica il manifest di runtime e il cablaggio
   dell'iniettore. `tests/validate.sh` / `validate.ps1` sono il **pavimento portabile
   congelato** per host senza Python (lo dicono all'inizio di ogni file):
   meno controlli, mantenuti solo così un host senza Python non rimane con nulla.
   Eseguili anche se la tua modifica tocca uno di essi, ma mai *invece* --
   superare il pavimento da solo dimostra molto meno di quanto sembri.
   CI esegue il validatore canonico su ogni push e PR indipendentemente
   (`.github/workflows/validate.yml`).
5. Incrementa `VERSION` secondo lo schema in `phases/ship.md` (patch per chiarimenti solo documentali, minor per nuovi comportamenti normativi, major per modifiche al contratto che rompono la compatibilità) e mantieni sincronizzato il badge della versione in `README.md` -- `tests/validate.sh`/`.ps1` controllano questo automaticamente quando eseguiti da un clone di questo repository.

## Stile

- Documenti del protocollo e delle fasi: concisi, parole chiave RFC-2119 dove contano, nessun riempitivo. Vedi `saipen/STYLE.md`.
- Tutto in questo file, messaggi di commit, commenti al codice e il CHANGELOG: semplici e professionali. Le voci di chat/LOG del progetto stesso (`saipen/STYLE.md`) non si applicano agli artefatti.

## Cosa è fuori ambito

- Trasformare SAIPEN in un sistema di consenso distribuito. Vedi la sezione "Concurrency & Distribution Boundaries" in `SPEC.md`.
- Grammatica dei marcatori LOG analizzabile dalle macchine oltre lo scheletro esistente. `LOG.md` rimane testo discorsivo attorno a una forma fissa.
- Un comando `saipen doctor` o simili ridondanti con `saipen validate` + `saipen status`.

Questi sono stati proposti e valutati in precedenza; riaprirli richiede nuove prove, non solo il riproporre la domanda.
