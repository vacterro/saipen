# Specifica SAIPEN

## Riepilogo
**Obiettivo di Design #1: Un agente a freddo con zero cronologia chat deve essere in grado di eseguire `/saipen continue` e riprendere il lavoro produttivo entro un minuto, senza chiedere all'utente di ripetere il contesto.**

SAIPEN garantisce che qualsiasi agente IA compatibile possa continuare in sicurezza qualsiasi progetto senza dover essere ri-istruito. È un'ABI (Application Binary Interface) per agenti ingegneristici IA: un livello di compatibilità che risolve il problema dell'amnesia. Che tu usi Claude oggi, Gemini domani, e GPT il giorno dopo, tutti opereranno contro lo stesso stato del progetto senza richiederti di ripetere il contesto.

### Filosofia di Base: Stato del Progetto > Memoria del Modello
La memoria dovrebbe vivere accanto al codice, non dentro la testa di un altro modello. SAIPEN sposta il paradigma da `Progetto -> Memoria -> LLM` a `Progetto -> Stato SAIPEN -> LLM`. La memoria appartiene al progetto.

Al suo nucleo, SAIPEN utilizza un protocollo di continuazione portabile e basato su file per gli agenti LLM. Le implementazioni POSSONO variare. Il contratto su disco DEVE rimanere stabile. Tutto in questo protocollo esiste per servire il Test di Continuazione.

SAIPEN è evolutivo, non creativo. Il suo scopo è completare il software, non reinventarlo. ADD estende pattern di progettazione esistenti, convenzioni industriali e palesi simmetrie di funzionalità.

- **`STATE`**: Esiste per rispondere a *"Cosa devo fare in questo momento?"*
- **`BOARD`**: Esiste per rispondere a *"Quale task sto prendendo in carico?"*
- **`LOG`**: Esiste per rispondere a *"Perché siamo arrivati a questo punto?"*
- **`KNOWLEDGE`**: Esiste per rispondere a *"Qual è la verità duratura di questo progetto?"*
- **`next_action`**: Il cuore di SAIPEN. Risponde a *"Quale comando esatto devo eseguire proprio in questo secondo per riprendere il lavoro?"*

## Il Test di Tornasole di SAIPEN

Qualsiasi modifica proposta o nuova idea per il protocollo DEVE superare le seguenti tre domande:
1. Rende la transizione tra agenti più affidabile?
2. Rende il comportamento di modelli diversi più uniforme?
3. Riduce la probabilità di perdita di contesto?

Se la risposta è "no" ad almeno due di queste domande, l'idea viene respinta. SAIPEN privilegia disciplina, riproducibilità e affidabilità rispetto alla novità.

## Architettura

Il protocollo è strettamente normativo. Concettualmente SAIPEN si divide in due livelli: **Base (Core)** e **Manutenzione (Maintenance)**. 
- **Il livello Base (Core)** garantisce una continuazione sicura del task in modo neutrale rispetto al fornitore. 
- **Il livello Manutenzione (Maintenance)** è un modello di evoluzione autonoma del software costruito sopra al livello Base.

Al di sotto dei due livelli, SAIPEN separa tre aspetti che non si aggrovigliano mai:
**correttezza e continuazione** (Core -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, negoziazione delle capacità, checkpointing), **evoluzione non presidiata** (Manutenzione -- `HUNT`/`ADD`/`CLEAN`, completamente funzionale sotto il default `saipen`/`saipen continue`), e **produttività (throughput)** (Modalità Goal, Sottoagenti -- entrambi esplicitamente opt-in, §1.3/§2.4). Disabilita la Modalità Goal: il protocollo rimane invariato, un ticket alla volta. Disabilita i Sottoagenti: `HUNT` esegue le stesse sei categorie sequenzialmente, stesso risultato. Usa solo il livello Base, senza affatto il livello di Manutenzione: regge comunque -- un agente a freddo riprende il lavoro correttamente. Ogni livello si basa su quello sottostante senza che si verifichi mai il contrario; nulla a monte dipende dall'esistenza di una funzionalità a valle.

```text
saipen/
  RFC.md                    specifica normativa (divisa in Core e Manutenzione)
  CONFORMANCE.md             vettori di auto-verifica + tabella copertura scenari
  SKILL.md                  punto di ingresso sottile per piattaforme skill-reading
  STYLE.md                  voci: chat, LOG.md, artefatti
  UI.md                     specifica UI Dark Golden Win95 (obbligatoria per lavoro UI)
  BOOT.md                   ~kernel di avvio a freddo: il percorso rapido di cui un
                             `continue` nudo ha bisogno, prima che uno dei suddetti sia caricato
  phases/                   rigorosa logica a macchina a stati -- 16 documenti, uno per
                             valore enum RFC § 1.6 (controllato a macchina in entrambi i sensi
                             da tools/validate.py)
    [Fasi Core]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Fasi di Manutenzione]
    hunt.md / markhunt.md / add.md / clean.md / translate.md

    [Infrastruttura]
    prepare.md              prepara il lavoro per la consegna al prossimo agente
    validate.md             test di conformità

extensions/                 <- IL LIVELLO ADATTIVO
  adapters/                 bridge di istruzioni per modello, per piattaforme che l'iniettore non rileva automaticamente (il README.md punta qui)
  schemas/                  state.schema.json è letto dalla macchina da tools/validate.py (unica fonte di verità per la forma dello STATE); gli schemi di board/log rimangono solo come riferimento (vedi schemas/README.md)
  templates/                boilerplate fresco di .saipen/
  security/                 hook di ESEMPIO da copiare in un progetto (RFC § 1.9, si attacca a VERIFY)
  performance/              hook di ESEMPIO da copiare in un progetto (RFC § 1.9, si attacca a REVIEW)
  subs/                     sottoagenti di ricerca read-only di ESEMPIO (RFC § 1.9) -- propri STATE/BOARD/LOG per sottoagente, risultati solo via OUTBOX, mai un secondo percorso di scrittura nel progetto

bootstrap/                  <- INSTALLA/ESPORTA/DISINSTALLA, una macchina alla volta
  inject.ps1 / .sh          installa il blocco SAIPEN + copie skill (Avvio Rapido nel README)
  uninstall.ps1 / .sh       inverte inject -- rimuove i blocchi + le copie skill
  export.ps1 / .sh          archivia la .saipen/ di un progetto per backup
  saipen_crew.bat / .sh     apre il layout crew a 3 finestre (bonus, extensions/subs/crew.md)

tools/                      <- VALIDATORE CANONICO E UTILITY DI REPO
  validate.py               validatore di conformità canonico (stdlib Python, zero installazioni; valida STATE contro state.schema.json direttamente, più controlli del grafo che la coppia di shell non può fare)
  install_hook.py           installa un hook pre-commit che esegue validate.py
  uninstall_hook.py         rimuove esattamente quell'hook (ripristina qualsiasi hook precedente)

tests/                      <- LIVELLO DI CONFORMITÀ
  validate.ps1 / .sh        base portabile congelata per host senza Python -- i nuovi controlli atterrano solo in tools/validate.py
  scenarios/                stati mock (crash-recovery, conflitti-claim, ecc.)
```

## Negoziazione a Due Vie delle Capacità
Gli agenti non dichiarano semplicemente cosa possono fare; il protocollo richiede ciò che è necessario.
Il progetto definisce `requires: [filesystem, git, shell, python]` nel suo stato. L'agente incrocia le proprie capacità dell'host con i requisiti e si blocca in un `mode` (es., `full`, `read-only`).

## Registrazione degli Eventi Basata su Grafo
I log in SAIPEN non sono stringhe lineari. Formano un grafo aciclico di decisioni utilizzando ID Evento (`E-001`). Questo permette branch complessi, merging di agenti e tracce di audit precise.

## Record di Decisione dell'Architettura (ADR)
I log di eventi transitori non ospitano conoscenze permanenti. SAIPEN impone che le decisioni architettoniche strutturali siano persistite come ADR (es. `KNOWLEDGE/ADR-001-use-sqlite.md`).

## Concorrenza e Limiti di Distribuzione
SAIPEN garantisce l'integrità dello stato tramite rivendicazioni (claim) basate su file (`owner`, `claim_time`) e grafi sequenziali (`LOG.md`). Tuttavia, **SAIPEN è un protocollo di stato, non un algoritmo di consenso distribuito.**
- **Filesystem Locale/Condiviso**: La risoluzione dei conflitti si basa su scritture atomiche del filesystem ("il primo commit vince").
- **Ambienti di Rete/Distribuiti**: Se gli agenti operano attraverso macchine disconnesse senza sincronizzazione dei file in tempo reale, si verificheranno race condition sui claim in `BOARD.md`. Negli assetti altamente distribuiti, il contratto di protocollo SAIPEN su disco DEVE rimanere stabile -- lo stato stesso del progetto continua a mutare costantemente, tramite le regole di SAIPEN stesse (checkpointing § 1.5), ma non la forma del protocollo che tali regole seguono.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
