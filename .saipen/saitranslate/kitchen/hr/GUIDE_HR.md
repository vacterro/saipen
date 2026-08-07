<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Vodič (Hrvatski)

[TRANSLATED HR]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN** je bilježnica u mapi `.saipen/` u vašem projektu.

## Brzi početak

## Naredbe

## Dobro je znati
- Necommitane promjene kad se vratiš na projekt? Normalno -- SAIPEN commita samo kod `ship`, ne kod svakog koraka. Agent prvo provjerava čije su te promjene prije nego što išta dotakne.
- Želiš da pamti pravu arhitektonsku odluku? Stavi je u `.saipen/KNOWLEDGE/`, kao jednu datoteku `decisions.md` ili numerirane datoteke `ADR-001.md`.
- Nema gita ni shella na ovom stroju? Agent to jasno kaže (`mode`, `WAIT: <category> -- <pitanje>`) umjesto da nagađa (kategorija je jedna od sedam: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; govori kakav odgovor otključava situaciju)
- Želiš sigurnosnu mrežu? `python <saipen-klon>/tools/install_hook.py` instalira provjeru prije svakog commita.