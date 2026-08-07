<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Guide (Norsk)

[TRANSLATED NO]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

## Hurtigstart

## Kommandoer

## Greit å vite
- Ikke-committede endringer når du kommer tilbake? Normalt -- SAIPEN committer først ved `ship`, ikke ved hvert steg. Agenten sjekker først hvem sine endringer det er, før den rører noe.
- Vil du at den skal huske en ekte arkitekturbeslutning? Legg den i `.saipen/KNOWLEDGE/`, som en fil `decisions.md` eller nummererte `ADR-001.md`-filer.
- Ingen git eller shell på denne maskinen? Agenten sier det rett ut (`mode`, `WAIT: <category> -- <spørsmål>`) i stedet for å gjette (kategorien er en av syv: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; den forteller hva slags svar som låser opp)
- Vil du ha et sikkerhetsnett? `python <saipen-klone>/tools/install_hook.py` installerer en pre-commit-sjekk.