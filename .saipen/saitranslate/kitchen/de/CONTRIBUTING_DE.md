# Mitwirken bei SAIPEN

SAIPEN ist in erster Linie eine Spezifikation, in zweiter Linie eine Implementierung. Die meisten Beiträge
sind Änderungen an `saipen/RFC.md`, einer `phases/*.md` Datei oder den Konformitäts-
Werkzeugen in `tests/` -- nicht am Anwendungscode.

## Bevor du eine Änderung vorschlägst

Führe den [SAIPEN Lackmustest](../../SPEC.md#the-saipen-litmus-test) für deine
Idee durch:
1. Macht sie den Übergang zwischen Agenten zuverlässiger?
2. Macht sie das Verhalten verschiedener Modelle einheitlicher?
3. Verringert sie die Wahrscheinlichkeit von Kontextverlusten?

Wenn die Antwort auf mindestens zwei dieser Fragen "Nein" lautet, liegt dies außerhalb des Anwendungsbereichs für dieses
Protokoll, wie nützlich es anderswo auch sein mag.

## Eine Lücke melden

Eröffne ein Issue und beschreibe:
- in welcher Datei/Sektion sich die Lücke befindet (RFC.md, ein Phasendokument, ein Schema, ein Test)
- die konkreten Beweise (ein Zitat, ein Befehl und seine Ausgabe, ein Szenario, in dem
  das aktuelle Verhalten fehlschlägt)
- was du stattdessen erwarten würdest

Vage Berichte ("das fühlt sich falsch an") sind schwerer umzusetzen als ein spezifischer
`grep`/Reproduktion. Siehe die Vorlage für Fehlerberichte für die Form, die dies
annehmen sollte.

## Eine Änderung vornehmen

1. Lies `saipen/RFC.md` und die entsprechende(n) `phases/*.md` Datei(en) vollständig, bevor
   du Änderungen vornimmst -- die meisten offensichtlichen Lücken stellen sich als bereits an anderer Stelle behandelt heraus,
   oder sind aus einem dokumentierten Grund absichtlich auf eine bestimmte Weise abgegrenzt.
2. Überprüfe `CHANGELOG.md` und `.saipen/KNOWLEDGE/decisions.md` auf frühere Arbeiten.
   Eröffne nicht stillschweigend eine Entscheidung, die bereits getroffen und abgelehnt wurde --
   wenn du neue Beweise hast, dass eine frühere Ablehnung falsch war, sage dies explizit
   in der PR-Beschreibung.
3. Jede normative Änderung (ein MUSS/DARF NICHT/SOLLTE) benötigt einen Eintrag im `CHANGELOG.md`
   und, wo praktikabel, eine Abdeckung in `tests/validate.sh` +
   `tests/validate.ps1` (beide Plattformen) oder ein Fixture unter
   `tests/scenarios/`.
4. Führe beide Validatoren aus, bevor du einen PR eröffnest:
   ```bash
   bash tests/validate.sh
   powershell -File tests/validate.ps1
   ```
5. Erhöhe die `VERSION` gemäß dem Schema in `phases/ship.md` (Patch für reine Dokumentations-
   Klarstellungen, Minor für neues normatives Verhalten, Major für brechende
   Vertragsänderungen) und halte das Versions-Badge in der `README.md` synchron --
   `tests/validate.sh`/`.ps1` prüfen dies automatisch, wenn sie aus einem
   Klon dieses Repos ausgeführt werden.

## Stil

- Protokoll- und Phasendokumente: kurz, RFC-2119 Schlüsselwörter, wo sie wichtig sind, kein
  Füllmaterial. Siehe `saipen/STYLE.md`.
- Alles in dieser Datei, Commit-Nachrichten, Code-Kommentare und das
  CHANGELOG: einfach und professionell. Die eigenen Chat-/LOG-Stimmen des Projekts
  (`saipen/STYLE.md`) gelten nicht für Artefakte.

## Was außerhalb des Geltungsbereichs liegt

- SAIPEN in ein verteiltes Konsenssystem zu verwandeln. Siehe
  `SPEC.md` Abschnitt Nebenläufigkeits- & Verteilungsgrenzen.
- Maschinenlesbare LOG-Marker-Grammatik jenseits des bestehenden Grundgerüsts.
  `LOG.md` bleibt Prosa um eine feste Form.
- Ein `saipen doctor` Befehl oder ähnliches redundant mit `saipen validate` +
  `saipen status`.

Diese wurden jeweils schon einmal vorgeschlagen und evaluiert; ihre Wiedereröffnung erfordert
neue Beweise, nicht nur ein erneutes Fragen.
