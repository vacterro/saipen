<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Guida SAIPEN (Italiano)

[TRANSLATED IT]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

## Avvio Rapido

## Comandi

## Buono a sapersi
- Modifiche non committate quando torni al progetto? Normale -- SAIPEN fa il commit solo con `ship`, non a ogni passo. L'agente verifica prima di chi sono quelle modifiche prima di toccare qualsiasi cosa.
- Vuoi che ricordi una vera decisione architetturale? Mettila in `.saipen/KNOWLEDGE/`, come file `decisions.md` o file numerati `ADR-001.md`.
- Niente git o shell su questa macchina? L'agente lo dice chiaramente (`mode`, `WAIT: <category> -- <domanda>`) invece di indovinare (la categoria è una delle sette: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; indica che tipo di risposta sblocca la situazione)
- Vuoi una rete di sicurezza? `python <clone-saipen>/tools/install_hook.py` installa un controllo pre-commit.