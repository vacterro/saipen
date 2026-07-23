# Sicherheitsrichtlinie

## Geltungsbereich

SAIPEN ist eine Spezifikation plus ein kleiner Satz lokaler Installations-/Export-
Skripte (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`,
`export.ps1`/`.sh`). Es betreibt keinen Server, sammelt keine
Telemetriedaten und überträgt keine Daten irgendwohin. Alles, was die
Skripte tun, sind lokale Dateisystem-Schreibvorgänge auf Dateien, die du bereits kontrollierst
(dein eigenes `~/.claude`, `~/.gemini`, Projekt `.saipen/`, etc.), jeweils
geschützt durch ein automatisches `.bak` Backup vor der ersten Modifikation.

Die beiden Dinge, die tatsächlich einen Sicherheitsbericht wert sind:
1. Ein Bootstrap-Skript tut etwas in deinem Dateisystem oder in der Git-Historie,
   das über das hinausgeht, was die eigenen Kommentare/README beschreiben.
2. Die protokolleigene Geheimhaltungsregel (RFC.md § 1.1 -- schreibe niemals
   API-Schlüssel, Token, Passwörter in `STATE.md`/`BOARD.md`/`LOG.md`/
   `KNOWLEDGE/`/`kitchen/`) hat eine echte Lücke, die dazu führen würde, dass ein
   Agent, der SAIPEN folgt, ein Geheimnis in eine festgeschriebene Datei (committed file) durchsickern lässt.

## Unterstützte Versionen

Nur das neueste markierte Release auf `main` wird unterstützt. Dies ist eine
Protokollspezifikation, kein langlebiger Dienst -- es gibt keinen LTS-
Branch.

## Eine Sicherheitslücke melden

Eröffne ein GitHub-Issue. Wenn der Bericht ein echtes, aktuell ausnutzbares
Problem beinhaltet (nicht hypothetisch), markiere es als private/Security Advisory über
den **Security**-Tab dieses Repositories ("Report a vulnerability") anstelle
eines öffentlichen Issues, damit es vor der Veröffentlichung eines Fixes nicht öffentlich sichtbar ist.

Füge hinzu: welches Skript oder welche RFC-Regel, das konkrete Szenario und was
tatsächlich passiert vs. was passieren sollte. Gleicher Beweisstandard wie bei jedem
anderen Fehlerbericht (siehe `CONTRIBUTING.md`).
