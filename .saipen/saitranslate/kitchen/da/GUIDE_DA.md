<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Guide (Dansk)

[TRANSLATED DA]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

## Hurtig Start

## Kommandoer

## Godt at vide
- Ikke-committede ændringer, når du kommer tilbage? Normalt -- SAIPEN committer først ved `ship`, ikke ved hvert trin. Agenten tjekker først, hvis ændringer det er, før den rører noget.
- Vil du have, at den husker en rigtig arkitekturbeslutning? Læg den i `.saipen/KNOWLEDGE/`, som en fil `decisions.md` eller nummererede `ADR-001.md`-filer.
- Ingen git eller shell på maskinen? Agenten siger det ligeud (`mode`, `WAIT: <category> -- <spørgsmål>`) i stedet for at gætte (kategorien er en af syv: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; den fortæller, hvilken type svar der låser op)
- Vil du have et sikkerhedsnet? `python <saipen-klon>/tools/install_hook.py` installerer et pre-commit-tjek.