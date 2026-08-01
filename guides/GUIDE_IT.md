<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Guida SAIPEN (Italiano)

SAIPEN è un taccuino di memoria persistente nella cartella `.saipen/` per agenti AI.

**Tasti rapidi:** `cc` prosegue un Goal Mode attivo, `sss` segnala lo stato senza toccare il codice e `ss` salva un checkpoint e si ferma. [Guarda la mappa completa degli 11 tasti](../saipen/RFC.md#110-command-surface). Funzionano anche i gemelli cirillici: `сс`, `ссс`, `аа`, `ее`, `рр`.

## Avvio Rapido

1. **Installa una volta per macchina:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Avvia progetto:**
> `saipen set`

3. **Lavorare:**
> `saipen`

## Comandi

| Comando | Azione |
|---|---|
| `saipen set` | Inizializza cartella memoria `.saipen/` |
| `saipen continue` | Riprendi lavoro dagli appunti |
| `saipen stop` | Salva progresso e ferma |
| `saipen status` | Leggi bacheca e stato |
| `saipen goal <text>` | Passa al nuovo obiettivo |
| `saipen clean` | Pulizia profonda del repository |
| `saipen translate` | Compilazione isolata per traduzione in 32 lingue |
| `saipen markhunt` | Audit profondo e illimitato -- registra solo i risultati |
| `saipen prepare` | Impacchetta il lavoro per la consegna al prossimo agente |
| `saipen ship` | Avvia flusso di rilascio |

## Buono a sapersi
- Modifiche non committate quando torni al progetto? Normale -- SAIPEN fa il commit solo con `ship`, non a ogni passo. L'agente verifica prima di chi sono quelle modifiche prima di toccare qualsiasi cosa.
- Vuoi che ricordi una vera decisione architetturale? Mettila in `.saipen/KNOWLEDGE/`, come file `decisions.md` o file numerati `ADR-001.md`.
- Niente git o shell su questa macchina? L'agente lo dice chiaramente (`mode`, `WAIT: <category> -- <domanda>`) invece di indovinare (la categoria è una delle sette: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; indica che tipo di risposta sblocca la situazione)
- Vuoi una rete di sicurezza? `python <clone-saipen>/tools/install_hook.py` installa un controllo pre-commit.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
