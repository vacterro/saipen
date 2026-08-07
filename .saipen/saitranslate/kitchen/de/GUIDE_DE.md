<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Anleitung (Deutsch)

[TRANSLATED DE]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN** ist einfach ein Notizbuch im Ordner `.saipen/` direkt in deinem Projekt.

## Schnellstart

## Befehle

## Gut zu wissen
- Nicht committete Änderungen, wenn du zurückkommst? Normal -- SAIPEN committet erst bei `ship`, nicht bei jedem Schritt. Der Agent prüft erst, wessen Änderungen das sind, bevor er etwas anfasst.
- Soll er sich eine echte Architekturentscheidung merken? Leg sie in `.saipen/KNOWLEDGE/` ab, entweder als `decisions.md` oder als nummerierte `ADR-001.md`-Dateien.
- Kein Git oder keine Shell auf dieser Maschine? Der Agent sagt es offen (`mode`, `WAIT: <category> -- <Frage>`), statt zu raten (die Kategorie ist eine von sieben: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; sie sagt dir, welche Art von Antwort dich entblockt)
- Willst du ein Sicherheitsnetz? `python <saipen-Klon>/tools/install_hook.py` installiert eine Pre-Commit-Prüfung.