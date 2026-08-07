<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Útmutató (Magyar)

[TRANSLATED HU]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

A **SAIPEN** egy jegyzetfüzet a projekted `.saipen/` mappájában.

## Gyors indulás

## Parancsok

## Jó tudni
- Nem commitolt változtatások, amikor visszatérsz a projekthez? Normális -- a SAIPEN csak `ship`-nél commitol, nem minden lépésnél. Az ágens előbb ellenőrzi, kié ezek a változtatások, mielőtt bármihez hozzáérne.
- Szeretnéd, hogy emlékezzen egy valódi architektúra döntésre? Tedd a `.saipen/KNOWLEDGE/` mappába, egyetlen `decisions.md` fájlként vagy számozott `ADR-001.md` fájlokként.
- Nincs git vagy shell ezen a gépen? Az ágens ezt nyíltan megmondja (`mode`, `WAIT: <category> -- <kérdés>`), ahelyett hogy találgatna (a kategória a hét egyike: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; megmondja, milyen válasz oldja fel a blokkot)
- Szeretnél biztonsági hálót? A `python <saipen-klón>/tools/install_hook.py` telepít egy commit előtti ellenőrzést.