<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Ghid SAIPEN (Română)

[TRANSLATED RO]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN** este un caiet în folderul `.saipen/` din proiectul tău.

## Pornire rapidă

## Comenzi

## Bine de știut
- Modificări necomise când revii la proiect? Normal -- SAIPEN face commit doar la `ship`, nu la fiecare pas. Agentul verifică mai întâi ale cui sunt acele modificări înainte de a atinge ceva.
- Vrei să rețină o decizie arhitecturală reală? Pune-o în `.saipen/KNOWLEDGE/`, fie ca un singur fișier `decisions.md`, fie ca fișiere numerotate `ADR-001.md`.
- Nu ai git sau shell pe această mașină? Agentul spune asta clar (`mode`, `WAIT: <category> -- <întrebare>`) în loc să ghicească (categoria este una din șapte: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; spune ce fel de răspuns deblochează situația)
- Vrei o plasă de siguranță? `python <clonă-saipen>/tools/install_hook.py` instalează o verificare pre-commit.