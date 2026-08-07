<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Przewodnik SAIPEN (Polski)

[TRANSLATED PL]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

## Szybki Start

## Polecenia

## Warto wiedzieć
- Niezacommitowane zmiany po powrocie do projektu? Normalka -- SAIPEN commituje dopiero przy `ship`, nie na każdym kroku. Agent najpierw sprawdza, czyje to zmiany, zanim czegokolwiek dotknie.
- Chcesz, żeby pamiętał prawdziwą decyzję architektoniczną? Wrzuć ją do `.saipen/KNOWLEDGE/`, jako plik `decisions.md` albo ponumerowane pliki `ADR-001.md`.
- Brak gita albo shella na tej maszynie? Agent mówi to wprost (`mode`, `WAIT: <category> -- <pytanie>`), zamiast zgadywać (kategoria jest jedną z siedmiu: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; mówi, jaka odpowiedź odblokowuje sytuację)
- Chcesz siatkę bezpieczeństwa? `python <klon-saipen>/tools/install_hook.py` instaluje sprawdzenie przed commitem.