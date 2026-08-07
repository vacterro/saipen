<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Průvodce SAIPEN (Čeština)

[TRANSLATED CS]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN** je zápisník ve složce `.saipen/` ve tvém projektu.

## Rychlý start

## Příkazy

## Dobré vědět
- Necommitnuté změny, když se vrátíš k projektu? Normální -- SAIPEN commituje až při `ship`, ne při každém kroku. Agent nejdřív zkontroluje, čí jsou to změny, než se čehokoli dotkne.
- Chceš, aby si pamatoval skutečné architektonické rozhodnutí? Ulož ho do `.saipen/KNOWLEDGE/`, buď jako jeden soubor `decisions.md`, nebo jako číslované soubory `ADR-001.md`.
- Na tomto stroji není git ani shell? Agent to řekne rovnou (`mode`, `WAIT: <category> -- <otázka>`), místo aby hádal (kategorie je jedna ze sedmi: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; říká, jaká odpověď situaci odblokuje)
- Chceš záchrannou síť? `python <saipen-klon>/tools/install_hook.py` nainstaluje kontrolu před každým commitem.