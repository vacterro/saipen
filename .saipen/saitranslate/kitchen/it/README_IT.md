<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Protocollo di continuazione per agenti AI di codifica.** Memoria di progetto persistente in markdown semplice, in modo che un agente "freddo" senza cronologia di chat esegua `/saipen continue` e riprenda il lavoro in meno di un minuto -- nessuna ri-spiegazione, qualsiasi provider, qualsiasi giorno.

**Un comando. Zero amnesia.**

**v7.81.0** | [Spec](SPEC.md) | [Guida](GUIDE.md) | [RFC](saipen/RFC.md) | [Stile](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformità](saipen/CONFORMANCE.md) | markdown semplice | zero dipendenze | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Utente  ->  /saipen continue
Agente  ->  legge STATE ("Cosa faccio adesso?")
Agente  ->  legge BOARD ("Quale task sto prendendo?")
Agente  ->  legge next_action (esegue il comando)
Agente  ->  Lavora.
```

### Stato del Progetto > Memoria del Modello
La memoria vive nel progetto, non nella testa del modello. `Progetto -> Memoria -> LLM` diventa `Progetto -> Stato SAIPEN -> LLM`.

### Logica Chiave del Protocollo & Garanzie
- **Macchina a Stati Principale**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Autonomia Senza Prompt**: Nessun to-do aperto rimasto? Transizione automatica nel ciclo `HUNT` (scansione bug) → `ADD` (evoluzione funzionalità) → `HUNT`. Nessuna domanda posta.
- **Trigger Espliciti**: `/saipen clean` (pulizia repository), `/saipen translate` (fabbrica isolata `.saipen/saitranslate/`), `/saipen markhunt` (audit completo senza correzioni, solo registrazione), `/saipen prepare` (pacchetto di lavoro per il passaggio di consegna), `/saipen validate` (controllo di conformità), `/saipen goal` (esecuzione autonoma di ondate). Meta/controllo: `/saipen status` (report in sola lettura), `/saipen stop` (salvataggio punto di controllo e arresto). Elenco completo: RFC.md § 1.10.
- **Affidabilità Rigorosa**: Parsing dell'input a lotti (ticket chirurgici 1 a 1), adozione di albero con modifiche non committate (non cancella mai il lavoro non committato), oscuramento dei segreti (`sk-***`).
- **In sviluppo -- saicrew**: uno strato bonus opzionale (`extensions/subs/`, senza modifiche al Core) per eseguire una squadra multi-agente -- un Core scrittore più worker di sola lettura `saihunt`/`saipython`, che riportano tramite il proprio `OUTBOX.md`. Attualmente in test dal vivo, non ancora verificato end-to-end -- vedi `extensions/subs/crew.md`.

## Progetti basati su SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Strumento di gestione dei prompt ad alte prestazioni integrato nativamente con il protocollo di memoria SAIPEN.

## Due Livelli

| Livello | Richiesto | Scopo |
|---|---|---|
| **Core** | ✅ | Continuare il lavoro in sicurezza |
| **Manutenzione** | Sopra il Core | Far evolvere il software senza assegnazione manuale dei task |

**Evoluzione Automatizzata.** Nessun to-do aperto rimasto, digita `/saipen`: `HUNT` analizza alla ricerca di bug, codice morto, test falliti. Tutto pulito? `ADD` sviluppa la successiva funzionalità mancante evidente, la verifica e torna a cercare bug con `HUNT`. Quando il prodotto è maturo -> si arresta delicatamente.

**Modalità GOAL.** `/saipen goal <ciò che desideri>` cambia l'obiettivo della lavagna (i vecchi ticket vengono declassati, mai eliminati) e spinge avanti il nuovo obiettivo in modo autonomo -- nessuna domanda tipo "devo continuare?" tra i ticket, VERIFY/REVIEW non vengono mai saltati. SHIP effettua automaticamente il push su un remote esistente; una repository completamente nuova chiederà una sola volta. Spedire (SHIP) l'obiettivo non è il punto di arresto -- passa direttamente alla manutenzione autonoma HUNT/ADD finché il prodotto non è maturo, bloccato o l'esecuzione raggiunge il limite (3 ondate / 20 ticket, poi crea un punto di controllo e riporta).

## Avvio Rapido

**1. Installa una volta per macchina** -- insegna a Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex e qualsiasi lettore generico di ~/.agents/skills (FreeBuff, ecc.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Avvia un progetto** -- apri un agente nella cartella del progetto, digita:
> `saipen set`

Nessuna installazione? Incolla una riga a qualsiasi agente:
> Leggi <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md e seguili.

La piattaforma non è presente nell'elenco sopra (DeepSeek, Qwen, OpenAI standalone, ecc.)?
Le note per ciascuna piattaforma si trovano in `extensions/adapters/`.

## Link a Documentazione & Specifiche
- **[SPEC.md](SPEC.md)** -- architettura formale, obiettivi di progettazione, test decisivo.
- **[RFC.md](saipen/RFC.md)** -- specifica normativa eseguita dagli agenti.
- **[GUIDE.md](GUIDE.md)** -- tutorial per umani & guide ELI5:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- stile di comunicazione dell'agente & definizione del tono.
- **[UI.md](saipen/UI.md)** -- linee guida di progettazione UI Win95 Dark Golden.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- scenari di test comportamentale & regole del validatore.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

