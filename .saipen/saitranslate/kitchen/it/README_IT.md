<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
</p>

<div align="center">
  <h3><a href="README.ee.md">🇪🇪 LOE SEDA EESTI KEELES / ESTONIAN 🇪🇪</a></h3>
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="README.ded.md">👴 Дед-Версия (Russian)</a> &nbsp;|&nbsp;
  <a href="README.ja.md">🇯🇵 日本語 (Japanese)</a>
</div>

# SAIPEN

**Protocollo di continuazione per agenti di codifica AI.**La memoria del progetto vive in formato plain
file Markdown all'interno del progetto(`.saipen/`), quindi qualsiasi agente freddo compatibile —
nessuna cronologia delle chat, nessuna memoria della sessione — può eseguire`/saipen continue`, leggere il
persistito`next_action`, e riprendere il lavoro senza chiedere all'utente di riconoscere nuovamente
qualcosa. Lo stato appartiene al progetto, non alla memoria di un singolo fornitore di modelli.

**Un comando per riprendere. Stato in file plain. Contratti controllati automaticamente dalla macchina.**

Il repository si verifica da solo su ogni push; install, stato, controlli e
uninstall sono tutte locali — nessun servizio cloud, nessun demone, nessun database.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.231.8** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [Core](saipen/CORE.md) | [Maintenance](saipen/MAINTENANCE.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) |MIT

**Tasti rapidi:** `cc` prosegue il contesto del progetto fino alla convergenza (riprende un obiettivo attivo se ne è impostato uno), `sss` segnala lo stato senza toccare il codice e `ss` salva un checkpoint e si ferma. [Guarda la mappa completa degli 19 tasti](saipen/RFC.md#110-command-surface). Funzionano anche i gemelli cirillici: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

```text
Project
  |
  +-- .saipen/STATE.md ------ what is happening right now (phase, ticket, mode, next_action)
  +-- .saipen/BOARD.md ------ what work exists (DOING / TODO / DONE / BLOCKED)
  +-- .saipen/LOG.md -------- why the project reached this state (event history)
  +-- .saipen/KNOWLEDGE/ ---- what durable facts must survive sessions
          |
          v
   /saipen continue
          |
          v
      cold agent
          |
          v
     next_action -> work -> checkpoint -> next ticket
```

## Cosa persiste

La memoria del progetto in corso vive in`.saipen/`— file semplici che puoi leggere, confrontare e
committare accanto al codice. Un agente freddo risponde a cinque domande provenienti dai file
da solo:

|File / campo|Risposte|
|---|---|
| `STATE.md` |Cosa sta succedendo in questo momento?(fase, ticket attivo, modalità operativa, blocco) |
| `BOARD.md` |Quali lavori esistono / quali sono attivi?(grafico dei ticket: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |Perché il progetto ha raggiunto questo stato?(grafico degli eventi append-only) |
| `KNOWLEDGE/` |Quali fatti del progetto devono sopravvivere alle sessioni?|
| `next_action` (in`STATE.md`) |Qual'è l'azione esatta che l'agente successivo deve eseguire?|

Questo è un contratto di checkpoint, non un suggerimento di progettazione:`saipen stop`e ogni
transizione del ticket scrive i file in un ordine fisso, e il risultato viene verificato da
un validatore. Niente viene memorizzato in un database ospitato, e niente viene perso quando un
la sessione termina.

## Avvio rapido

**1. Installa una volta per macchina**— insegna a Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity e qualsiasi lettore generico`~/.agents/skills`reader(FreeBuff, ecc.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`blocco per l'istruzione dell'agente
file che già possiedi(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— eseguendo il backup di ciascuno in`.bak`primo —
e copia il protocollo nelle cartelle delle competenze corrispondenti. Niente al di fuori di quelle
percorsi, nessun demone, nessuna chiamata di rete.</sub>

**2. Avvia un progetto**— apri un agente nella tua cartella, digita:

> `saipen set`

**Nessun installazione?**Incolla una riga in qualsiasi agente:

> Leggi&lt;clone&gt;/saipen/BOOT.md prima(kernel di avvio freddo), poi&lt;clone&gt;/saipen/INDEX.md +&lt;clona&gt;/saipen/STYLE.md e seguile.

**Hai cambiato idea?**Un comando lo rimette a posto:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Rimuove esattamente il blocco contrassegnato(lasciando il resto del tuo file intatto), salva
a `.uninstalled.bak`crea una copia prima, e rimuove le cartelle delle competenze.

## Perché non il solo storico della chat?

SAIPEN mira a un fallimento specifico: un agente di codifica AI che non ricorda nulla
una volta che la sessione termina. Altri strumenti e abitudini coprono parte di quel problema:

|Approccio|A cosa serve|Cosa non trasporta|
|---|---|---|
|Storia della chat / memoria del modello|Conveniente, zero configurazione|Dipendente dalla sessione e dal fornitore; non memorizzato con il progetto, quindi un agente freddo non lo vede mai|
|Statico`AGENTS.md`/file di istruzione|Regole e convenzioni durature|Non rappresenta da solo lo stato attuale del compito in corso,`next_action`, o la storia del recupero|
|Tracker di problemi / TODO|Gestione compiti e backlog|Non definisce da sola i semantici di continuazione dell'agente — ciò che un agente freddo deve leggere ed eseguire al ripresa|
| **SAIPEN** |Lo stato di esecuzione in tempo reale, la coda di lavoro, la cronologia degli eventi, la conoscenza duratura e le regole di continuazione verificabili da macchina — in file normali accanto al codice|Nulla; quella combinazione è il contratto|

La differenza non è un singolo file. È che SAIPEN esegue il passo di ripresa
verificabile da macchina: l'azione iniziale di un agente freddo dopo`/saipen continue`è
determinata da ciò che è persistito`next_action`e verificata da un validatore, non
ricostruita dalla memoria.

## Evidenza ingegneristica

SAIPEN combina un protocollo normativo in file semplici con un esecutivo orientato agli errori
controlli. Il repository dimostra il design del protocollo/machine state, Python
strumenti, stato guidato da schema, ragionamento di recupero, testing di regressione,
limiti del flusso di lavoro multi-agente, e disciplina delle specifiche.

- **Contratto progettato.** [SPEC.md](SPEC.md)definisce il modello di continuazione supportato da file
e il contratto stabile su disco;[CORE.md](saipen/CORE.md)
e[MAINTENANCE.md](saipen/MAINTENANCE.md)definiscono il comportamento normativo corrente.
- **Stato verificato da macchina.**Il validator canonico stdlib-only
  [validator](tools/validate.py)legge lo stato live
  [schema dello stato](extensions/schemas/state.schema.json)e controlla le transizioni di fase
dipendenze dei biglietti, collegamenti del grafico degli eventi, invarianti tra documenti
invarianti, capacità e stato di recupero.
- **Copertura dei fallimenti.** [CONFORMANCE.md](saipen/CONFORMANCE.md)mappa
i requisiti a[fixture dei scenari](tests/scenarios/); il
  [runner scenario](tools/run_scenarios.py)esegue casi pass/fail strutturali
inclusi lo stato di recupero danneggiato, transizioni non valide, cicli di dipendenza e
restrizioni di sola lettura.
- **Controlli di regressione.** [audit_checks.py](tools/audit_checks.py)modifica
copie note come corrette e dimostra che i controlli del validator possono comunque fallire, piuttosto
che considerare un controllo sempre verde come prova.
- **Livello eseguibile.** [saipen.py](tools/saipen.py)fornisce uno stato registrato
operazioni;[bootstrap/](bootstrap/)conserva install, uninstall e export
helper, con un opzionale[installatore di hook pre-commit](tools/install_hook.py).
- **Scelte esplicite.**Lo stato del protocollo principale è costituito da file normali senza dipendenze runtime
dipendenza. La validazione canonica e gli strumenti CLI richiedono Python, ma utilizzano solo
la sua libreria standard e non necessitano di`pip`install.

## Architettura

Tre livelli, dipendenze strettamente unidirezionali:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Core non dipende da Maintenance: con l'evoluzione autonoma disabilitata, SAIPEN
è comunque un protocollo di continuazione completo — un agente freddo riprende comunque.

- **Core state machine** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Manutenzione autonoma**— scheda arrestata(niente funzionante in`## TODO`,
niente in`## DOING`)e non`BLOCKED`? Transizioni automatiche`HUNT` (rileva errori)
  → `ADD` (evolvi funzionalità) → `HUNT`, nessuna domanda posta. Una sessione seduta a
  `BLOCKED`non caccia automaticamente
  ([Manutenzione § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Modalità Obiettivo** — `/saipen goal <objective>`ruota la tavola e esegue l'
obiettivo in avanti attraverso VERIFY/REVIEW, cadendo nell'autonomia della manutenzione
fino al verificarsi della regola di completamento o al raggiungimento del limite(3 onde / 20 ticket,
quindi checkpoint e rapporto) ([Manutenzione § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Rafforzamento**— l'input in batch viene analizzato in ticket singoli e mirati
  (CORE § 1.8); la continuazione dell'albero sporco preserva il lavoro non committuto(CORE § 1.5);
i valori simili a segreti vengono eliminati dai log(`sk-***`) (CORE § 1.2).

## Comandi comuni

Punti di ingresso quotidiani; la superficie completa corrente vive in
[Core § 1.10](saipen/CORE.md#110-command-surface).

|Comando|Fa|
|---|---|
| `/saipen set` |Adotta un progetto: crea`.saipen/`stato|
| `/saipen continue` |Riprendi dallo stato del progetto persistito — nessun ribracing|
| `/saipen plan` |Trasforma una richiesta o un backlog grezzo in ticket|
| `/saipen goal <text>` |Esecuzione autonoma di un'onda contro un nuovo obiettivo|
| `/saipen validate` |Esegui i controlli di conformità|
| `/saipen status` |Rapporto in sola lettura: fase, ticket, blocchi, obsolescenza|
| `/saipen stop` |Checkpoint e arresto|

<details>
<summary><b>More commands</b></summary>

|Comando|Esegue|
|---|---|
| `/saipen hunt` |Forza l'analisi dei difetti/miglioramenti ora|
| `/saipen markhunt` |Audit secco, non limitato — registra i risultati, non apporta alcuna correzione|
| `/saipen ship` |Gate di rilascio; commit, tag e push quando permesso|
| `/saipen clean` |Pulizia del board e dello stato|
| `/saipen translate` |Fabbrica di traduzione isolata|
| `/saipen prepare` / `/saipen collect` |Lavoro del pacchetto per il trasferimento / integrare un pacchetto pronto|
| `/saipen test` |Esegui l'insieme di test dichiarato, segnala solo|
| `/saipen crew` |Circuito dell'equipaggio in ordine fisso(caccia → riproduzione → acquisizione → costruzione → traduzione → documentazione → spedizione) |
| `/saipen improve` |Audit di controllo meta per miglioramenti del protocollo|
| `/saipen sub ...` |Genera/adopta sottoragenti in sola lettura|

**Chiavi del pacchetto.** `ee`/`qq`prepara pacchetti completi di traduzione/wiki senza
integrare;`eee`/`qqq`accetta solo pacchetti pronti, quindi integra, verifica,
esamina e spinge.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)cammina per intero
crew incorporato in un ordine fisso — sensori(saihunt, saitest, saipython, saiui),
produttori(saitranslate, saiwiki)e Core come unico scrittore principale —
fino a quando un'altra passata fresca non ha più nulla di reale da modificare. Aggiunge esattamente uno
meccanismo proprio: il bersaglio di orchestrazione duratura(`execution_intent:
convergere` with `converge_target: crew`)che rende il circuito riprendibile e
derivabile da un crash a partire da prove.`saipen crew --dry-run --json`deriva il
circuito in sola lettura;`bootstrap/saipen_crew.*`è un AIUTANTE MANUALE OPZIONALE
a finestre multiple, mai ciò che`saipen crew`significa. Vedi
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Cosa SAIPEN non è

- **Un LLM o un modello**— è un protocollo che gli agenti seguono, non un'intelligenza.
- **Un IDE o un database di memoria ospitato**— lo stato è costituito da file semplici nel tuo progetto;
nulla è ospitato.
- **Un sostituto di Git**— Git continua a possedere la cronologia delle versioni; effettua il commit del
  `.saipen/`come qualsiasi altro codice.
- **Consenso distribuito**— vedi il limite di concorrenza qui sotto.
- **Una garanzia che un LLM prenderà decisioni ingegneristiche corrette**— esso
riduce la perdita di contesto e il drift comportamentale; non rende gli agenti stocastici
infallibili.

L'obiettivo di SAIPEN è un contratto di continuazione/ stato più validazione e strumenti —
passare all'agente successivo un punto di partenza verificato automaticamente da un computer, non magia.

**Confini di concorrenza.**Mutazioni dello stato registrate(SAIOPS)utilizza un
blocco del sistema operativo limitato al progetto e un registro di recupero([OPS § 5](saipen/OPS.md#5-locks)).
Le modifiche ordinarie al progetto e gli scrittori disconnessi sono fuori da quel blocco. SAIPEN
non è consenso distribuito, quindi gli scrittori disconnessi richiedono un'esterna
coordinazione([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ecosistema

|Progetto|Relazione con SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Centro di controllo locale per Windows per progetti SAIPEN — rileva automaticamente`.saipen/`gli spazi di lavoro, visualizza lo stato in tempo reale e i verdicti di conformità, gestisce i ticket e lancia CLI AI. Un compagno, non l'autorità.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Fork downstream di CodeNomad che integra SAIPEN: inietta`BOOT.md`/`STYLE.md`nelle lanci di OpenCode, espone scorciatoie SAIPEN e visualizzazioni dello stato del progetto, e aggiunge una coda di prompt persistente.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Blocco appunti portatile per Windows che rileva automaticamente`.saipen/`le cartelle e aggiunge un visualizzatore di stato/pannello/log in sola lettura.|

## Documentazione

|Document|Di cosa si tratta|
|---|---|
| [SPEC.md](SPEC.md) |Architettura formale, obiettivi di progettazione, test di litmus|
| [CORE.md](saipen/CORE.md) |Continuazione normativa, macchina a stati e contratto dei comandi|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Manutenzione autonoma e Modalità Obiettivo|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Requisiti eseguibili/comportamentali e regole del validatore|
| [GUIDE.md](GUIDE.md) |Tutorial per l'utente|
| [RFC.md](saipen/RFC.md) |Reindirizzamento della compatibilità ai documenti normativi separati|
| [STYLE.md](saipen/STYLE.md) |Stile e voce della comunicazione dell'agente|
| [UI.md](saipen/UI.md) |Linee guida per il design dell'interfaccia utente Vintage Golden|
|Brochure|Brochure presentazione —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Inglese](guides/GUIDE_EN.md) · 🇪🇪 [Estone](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Tedesco](guides/GUIDE_DE.md) · 🇫🇷 [Francese](guides/GUIDE_FR.md) · 🇪🇸 [Spagnolo](guides/GUIDE_ES.md) · 🇮🇹 [Italiano](guides/GUIDE_IT.md)

🇵🇹 [Portoghese](guides/GUIDE_PT.md) · 🇳🇱 [Olandese](guides/GUIDE_NL.md) · 🇵🇱 [Polacco](guides/GUIDE_PL.md) · 🇸🇪 [Svedese](guides/GUIDE_SV.md) · 🇩🇰 [Danese](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Note di configurazione

**Lingua di risposta.**L'agente risponde in**estone**per default — che è un'impostazione, non un requisito del protocollo, e nient'altro su SAIPEN è in estone.
Il protocollo, il codice, i commit e ogni documento rimangono in inglese a ogni
valore. Modificalo in un unico posto: la riga in alto di
estone,`reply_language:`inglese,
[`saipen/STYLE.md`](saipen/STYLE.md). `et`russo,`en`seleziona dal messaggio che hai inviato.`ru`Adattatori.
`auto`Adapters.

**Adattatori.**Piatto non coperto dall'iniettore(DeepSeek, Qwen, standalone
OpenAI, ecc.)? Le note specifiche per piattaforma vivono in`extensions/adapters/`.

## Screenshot

<details>
<summary><b>Click to expand</b></summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- translation-model: qwen3:14b contract:structured-markdown-v2 -->
<!-- source-digest: README.md sha256:bb47f7158db4a7a4fd99298427c1e4bc6859433c36435640e129cc6dad2a63b7 -->
