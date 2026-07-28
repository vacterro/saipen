# Sicherheitsrichtlinie

## Geltungsbereich

SAIPEN ist eine Spezifikation plus ein kleiner Satz lokaler Installations-/Export-
Skripte (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`,
`export.ps1`/`.sh`). Es betreibt keinen Server, sammelt keine
Telemetriedaten und überträgt keine Daten irgendwohin. Alles, was die
Skripte tun, sind lokale Dateisystem-Schreibvorgänge auf Dateien, die du bereits kontrollierst
(dein eigenes `~/.claude`, `~/.gemini`, Projekt `.saipen/`, etc.).

Dabei gelten zwei unterschiedliche Sorgfaltsstufen, und es lohnt sich, genau
zu sein, anstatt pauschale Sicherheit zu behaupten:

- **Deine eigenen Konfigurationsdateien** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
  `.aider.conf.yml`) werden nur durch Hinzufügen oder Entfernen eines
  begrenzten `SAIPEN:BEGIN`/`END`-Blocks bearbeitet, und das Original wird vor
  der ersten Änderung als `<file>.bak` kopiert. Die Deinstallation schreibt
  zusätzlich `<file>.uninstalled.bak` vor dem Entfernen.
- **Die Skill-Verzeichnisse**, die der Injektor erstellt (`~/.claude/skills/saipen`
  und ähnliche), sind SAIPEN-eigene Kopien und werden **nicht** gesichert: Die
  Installation überschreibt sie vollständig und die Deinstallation entfernt sie
  rekursiv. Das ist beabsichtigt -- sie enthalten nichts als Kopien der eigenen
  Dateien dieses Repos -- aber wenn du eine lokale Skill-Kopie von Hand bearbeitest,
  gehen diese Änderungen bei der nächsten `inject`/`uninstall`-Ausführung verloren.
  Bewahre Anpassungen in deinem eigenen Konfigurationsblock oder einem Fork auf,
  nicht im kopierten Skill-Ordner.

Die beiden Dinge, die tatsächlich einen Sicherheitsbericht wert sind:
1. Ein Bootstrap-Skript tut etwas in deinem Dateisystem oder in der Git-Historie,
   das über das hinausgeht, was die eigenen Kommentare/README beschreiben.
2. Die protokolleigene Geheimhaltungsregel (RFC.md § 1.1 -- schreibe niemals
   API-Schlüssel, Token, Passwörter in `STATE.md`/`BOARD.md`/`LOG.md`/
   `KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/
   `recovery/`/`logs/`) hat eine echte Lücke, die dazu führen würde, dass ein
   Agent, der SAIPEN folgt, ein Geheimnis in eine festgeschriebene Datei (committed file) durchsickern lässt. Die letzten beiden sind die subtilen:
   Recovery kopiert eine beschädigte `STATE.md` wörtlich nach
   `.saipen/recovery/`, und die LOG-Siegelung verschiebt Zeilen wörtlich nach
   `.saipen/logs/`, sodass alles, was das Original erreicht hat, von einer
   Maschinerie archiviert wird, deren ganze Aufgabe es ist, den Inhalt nicht zu
   verändern.

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
