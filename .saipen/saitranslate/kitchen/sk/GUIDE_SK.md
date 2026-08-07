<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Sprievodca SAIPEN (Slovenčina)

[TRANSLATED SK]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN** je zápisník v priečinku `.saipen/` vo vašom projekte.

## Rýchly štart

## Príkazy

## Dobré vedieť
- Necommitnuté zmeny, keď sa vrátiš k projektu? Normálne -- SAIPEN commituje až pri `ship`, nie pri každom kroku. Agent najprv skontroluje, čie sú tieto zmeny, kým sa čohokoľvek dotkne.
- Chceš, aby si pamätal skutočné architektonické rozhodnutie? Ulož ho do `.saipen/KNOWLEDGE/`, buď ako jeden súbor `decisions.md`, alebo ako číslované súbory `ADR-001.md`.
- Na tomto stroji nie je git ani shell? Agent to povie priamo (`mode`, `WAIT: <category> -- <otázka>`), namiesto hádania (kategória je jedna zo siedmich: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; hovorí, aká odpoveď odomkne situáciu)
- Chceš záchrannú sieť? `python <saipen-klon>/tools/install_hook.py` nainštaluje kontrolu pred každým commitom.