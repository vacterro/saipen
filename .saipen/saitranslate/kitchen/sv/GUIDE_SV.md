<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Guide (Svenska)

[TRANSLATED SV]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

## Snabbstart

## Kommandon

## Bra att veta
- Ocommittade ändringar när du kommer tillbaka? Normalt -- SAIPEN committar först vid `ship`, inte vid varje steg. Agenten kollar först vems ändringar det är innan den rör något.
- Vill du att den ska minnas ett riktigt arkitekturbeslut? Lägg det i `.saipen/KNOWLEDGE/`, som en fil `decisions.md` eller numrerade `ADR-001.md`-filer.
- Ingen git eller shell på maskinen? Agenten säger det rakt ut (`mode`, `WAIT: <category> -- <fråga>`) istället för att gissa (kategorin är en av sju: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; den säger vilken typ av svar som låser upp).
- Vill du ha ett skyddsnät? `python <saipen-klon>/tools/install_hook.py` installerar en pre-commit-kontroll.