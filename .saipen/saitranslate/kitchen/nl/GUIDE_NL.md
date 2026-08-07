<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Gids (Nederlands)

[TRANSLATED NL]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

## Snelstart

## Commando's

## Goed om te weten
- Niet-gecommitte wijzigingen als je terugkomt? Normaal -- SAIPEN commit alleen bij `ship`, niet bij elke stap. De agent controleert eerst van wie die wijzigingen zijn voordat hij iets aanraakt.
- Wil je dat hij een echte architectuurbeslissing onthoudt? Zet het in `.saipen/KNOWLEDGE/`, als één bestand `decisions.md` of genummerde `ADR-001.md`-bestanden.
- Geen git of shell op deze machine? De agent zegt het gewoon eerlijk (`mode`, `WAIT: <category> -- <vraag>`) in plaats van te gokken (de categorie is een van de zeven: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; het vertelt welk antwoord de blokkade opheft)
- Wil je een vangnet? `python <saipen-kloon>/tools/install_hook.py` installeert een pre-commit check.