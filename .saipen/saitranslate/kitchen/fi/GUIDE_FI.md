<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Opas (Suomi)

[TRANSLATED FI]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

## Pika-aloitus

## Komennot

## Hyvä tietää
- Tallentamattomia muutoksia, kun palaat projektiin? Normaalia -- SAIPEN committaa vasta `ship`-vaiheessa, ei joka askeleella. Agentti tarkistaa ensin, kenen muutoksia ne ovat, ennen kuin koskee mihinkään.
- Haluatko sen muistavan oikean arkkitehtuuripäätöksen? Laita se kansioon `.saipen/KNOWLEDGE/` joko tiedostona `decisions.md` tai numeroituina `ADR-001.md`-tiedostoina.
- Ei gitiä eikä shelliä tällä koneella? Agentti sanoo sen suoraan (`mode`, `WAIT: <category> -- <kysymys>`) sen sijaan että arvaisi (kategoria on yksi seitsemästä: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; se kertoo, millainen vastaus avaa tilanteen)
- Haluatko turvaverkon? `python <saipen-klooni>/tools/install_hook.py` asentaa pre-commit-tarkistuksen.