# Politica di Sicurezza

## Ambito

SAIPEN è una specifica oltre a un piccolo set di script locali di installazione/esportazione (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`, `export.ps1`/`.sh`). Non esegue un server, non raccoglie telemetria e non trasmette alcun dato da nessuna parte. Tutto ciò che gli script fanno sono scritture sul filesystem locale in file che tu già controlli (i tuoi `~/.claude`, `~/.gemini`, `.saipen/` del progetto, ecc.).

Due diversi livelli di attenzione si applicano qui, e vale la pena essere precisi
piuttosto che rivendicare una sicurezza generale:

- **I tuoi file di configurazione** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
  `.aider.conf.yml`) vengono modificati solo aggiungendo o rimuovendo un
  blocco delimitato `SAIPEN:BEGIN`/`END`, e l'originale viene copiato in
  `<file>.bak` prima della prima modifica. La disinstallazione scrive inoltre
  `<file>.uninstalled.bak` prima della rimozione.
- **Le directory delle skill** che l'iniettore crea (`~/.claude/skills/saipen`
  e simili) sono copie di proprietà di SAIPEN e **non** vengono backup:
  l'installazione le sovrascrive completamente e la disinstallazione le rimuove
  ricorsivamente. È intenzionale -- contengono solo copie dei file di questo
  repository -- ma se modifichi manualmente una copia di skill locale, quelle
  modifiche vengono perse al successivo `inject`/`uninstall`. Tieni le
  personalizzazioni nel tuo blocco di configurazione o in un fork, non nella
  cartella della skill copiata.

Le due cose che vale davvero la pena segnalare per la sicurezza:
1. Uno script di bootstrap che fa qualcosa al tuo filesystem o alla cronologia git oltre a ciò che i suoi stessi commenti/README descrivono.
2. La regola di igiene dei segreti del protocollo stesso (RFC.md § 1.1 -- non scrivere mai chiavi API, token, password in `STATE.md`/`BOARD.md`/`LOG.md`/`KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/`recovery/`/`logs/`) che ha una reale lacuna che causerebbe la perdita di un segreto in un file committato da parte di un agente che segue SAIPEN. Le ultime due sono le sottili: Recovery copia una `STATE.md` corrotta parola per parola in `.saipen/recovery/`, e la sigillatura LOG sposta le righe parola per parola in `.saipen/logs/`, quindi tutto ciò che ha raggiunto l'originale viene archiviato da macchinari il cui intero lavoro è non alterare il contenuto.

## Versioni Supportate

Solo l'ultima release taggata su `main` è supportata. Questa è una specifica di protocollo, non un servizio a lunga durata -- non esiste un ramo LTS.

## Segnalare una Vulnerabilità

Apri una issue su GitHub. Se la segnalazione riguarda un problema reale, attualmente sfruttabile (non ipotetico), contrassegnala come advisory privato/di sicurezza tramite la scheda **Security** di questo repository ("Report a vulnerability") invece di una issue pubblica, in modo che non sia visibile pubblicamente prima del rilascio di un fix.

Includi: quale script o regola RFC, lo scenario concreto e cosa succede effettivamente rispetto a cosa dovrebbe succedere. Lo stesso standard di prova di qualsiasi altra segnalazione di bug (vedi `CONTRIBUTING.md`).
