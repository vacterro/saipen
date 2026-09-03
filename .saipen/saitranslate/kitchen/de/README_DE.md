<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
</p>

<div align="center">
  <h3><a href="README.ee.md">🇪🇪 LOE SEDA EESTI KEELES / ESTONIAN 🇪🇪</a></h3>
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="README.ded.md">👴 Дед-Версия (Russian)</a> &nbsp;|&nbsp;
  <a href="README.ja.md">🇯🇵 日本語 (Japanese)</a>
</div>

# SAIPEN

**Fortsetzungsprotokoll für AI-Coding-Agenten.**Projektgedächtnis befindet sich in einfacher
Markdown-Dateien innerhalb des Projekts(`.saipen/`), also kann jeder kompatible kalter Agent —
keine Chat-Historie, kein Sitzungsgedächtnis — laufen`/saipen continue`, lesen die
persistierten`next_action`, und die Arbeit fortsetzen, ohne den Benutzer zu bitten, etwas erneut zu erklären
etwas. Zustand gehört zum Projekt, nicht zum Gedächtnis eines Modellherstellers.

**Ein Befehl zur Fortsetzung. Zustand in einfacher Datei. Maschinenüberprüfte Verträge.**

Das Repository validiert sich selbst bei jedem Push; installieren, Zustand, Überprüfungen und
Deinstallation sind alle lokal — keine Cloud-Dienste, kein Daemon, keine Datenbank.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.249.0** | [Spezifikation](SPEC.md) | [Leitfaden](GUIDE.md) | [Kern](saipen/CORE.md) | [Wartung](saipen/MAINTENANCE.md) | [Stil](saipen/STYLE.md) | [UI](saipen/UI.md) | [Konformität](saipen/CONFORMANCE.md) |MIT

**Schnellzugriff:** `cc` führt den Projektkontext bis zur Konvergenz fort (setzt ein laufendes Ziel fort, falls eines gesetzt ist), `sss` meldet Status ohne Code anzufassen und `ss` speichert einen Checkpoint und stoppt. [Siehe die komplette 19-Tasten-Karte](saipen/RFC.md#110-command-surface). Kyrillische Zwillinge funktionieren auch: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

```text
Project
  |
  +-- .saipen/STATE.md ------ what is happening right now (phase, ticket, mode, next_action)
  +-- .saipen/BOARD.md ------ what work exists (DOING / TODO / DONE / BLOCKED)
  +-- .saipen/LOG.md -------- why the project reached this state (event history)
  +-- .saipen/KNOWLEDGE/ ---- what durable facts must survive sessions
          |
          v
   /saipen continue
          |
          v
      cold agent
          |
          v
     next_action -> work -> checkpoint -> next ticket
```

## Was bleibt

Live-Projekt-Speicher befindet sich in`.saipen/`— einfache Dateien, die Sie lesen, vergleichen und
zusammen mit dem Code committen können. Ein kalter Agent beantwortet fünf Fragen aus den Dateien
allein:

|Datei / Feld|Antworten|
|---|---|
| `STATE.md` |Was geschieht gerade?(Phase, aktiver Ticket, Betriebsmodus, Blocker) |
| `BOARD.md` |Was für Arbeit existiert / was ist aktiv?(Ticket-Graph: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |Warum hat das Projekt diesen Zustand erreicht?(append-only-Event-Graph) |
| `KNOWLEDGE/` |Welche dauerhaften Projektfakten müssen Sitzungen überstehen?|
| `next_action` (in`STATE.md`) |Welche exakte Aktion sollte der nächste Agent ausführen?|

Dies ist ein Checkpoint-Vertrag, kein Designvorschlag:`saipen stop`und jeder
Ticket-Übergang schreibt die Dateien in einer festen Reihenfolge, und das Ergebnis wird von
einem Validator geprüft. Nichts wird in einer gehosteten Datenbank gespeichert, und nichts geht verloren, wenn ein
Die Sitzung endet.

## Schnellstart

**1. Einmal pro Maschine installieren**— lehrt Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity und jede generische`~/.agents/skills`Leser(FreeBuff usw.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`Block in die Agenten-Anweisung
Dateien, die Sie bereits haben(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— jeweils als Backup in`.bak`erstens —
und kopiert das Protokoll in die entsprechenden Skill-Ordner. Nichts außerhalb dieser
Pfade, kein Daemon, keine Netzwerkaufrufe.</sub>

**2. Starten Sie ein Projekt**— öffnen Sie einen Agenten in Ihrem Ordner und geben Sie ein:

> `saipen set`

**Keine Installation?**Einen Codezeile in jeden Agenten einfügen:

> Lesen Sie&lt;clone&gt;/saipen/BOOT.md zuerst(kalter Start Kernel), dann&lt;clone&gt;/saipen/INDEX.md +&lt;klonieren&gt;/saipen/STYLE.md und folgen Sie ihnen.

**Geändert Ihre Meinung?**Ein Befehl stellt es zurück:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Es entfernt genau den markierten Block(und lässt den Rest Ihrer Datei unberührt), speichert
a `.uninstalled.bak`kopieren Sie zuerst und entfernen Sie die Skill-Ordner.

## Warum nicht einfach die Chat-Historie?

SAIPEN zielt auf einen spezifischen Fehler ab: einen KI-Code-Agenten, der nichts merkt
einmal die Sitzung endet. Andere Tools und Gewohnheiten decken Teil dieses Problems ab:

|Ansatz|Wofür es gut ist|Was es nicht trägt|
|---|---|---|
|Chatverlauf / Modellerinnerung|Bequem, keine Einrichtung erforderlich|Sitzung- und anbieterabhängig; nicht mit dem Projekt gespeichert, also sieht ein kalter Agent es nie|
|Statisch`AGENTS.md`/ Anweisungsdatei|Beständige stehende Regeln und Konventionen|Stellt nicht von selbst den Live-Aufgabenstatus dar`next_action`, oder Wiederherstellungshistorie|
|Problem / TODO-Tracker|Aufgaben- und Backlog-Management|Definiert nicht alleine die Fortsetzungssemantik des Agenten — was ein kalter Agent bei der Fortsetzung lesen und ausführen muss|
| **SAIPEN** |Live-Ausführungsstatus, Arbeitswarteschlange, Ereignishistorie, haltbarer Wissen und maschinenüberprüfbare Fortsetzungsregeln — in normalen Dateien neben dem Code|Nichts; diese Kombination ist der Vertrag|

Der Unterschied liegt nicht in einer einzelnen Datei. Es ist vielmehr, dass SAIPEN den Fortsetzungsschritt ausführt
maschinenüberprüfbar: die erste Aktion eines kalten Agents nach`/saipen continue`ist
durch die gespeicherte`next_action`und von einem Validator überprüft, nicht
aus dem Gedächtnis rekonstruiert.

## Engineering Evidence

SAIPEN kombiniert einen normativen, normalen Datei-Protokoll mit ausführbaren, fehlerorientierten
Prüfungen. Das Repository veranschaulicht das Protokoll/State-Machine-Design, Python
Tooling, schema-gesteuerte Zustände, Wiederherstellungsv reasoning, Regressionstests,
Multi-Agenten-Workflow-Grenzen und Spezifikationsdisziplin.

- **Geschriebener Vertrag.** [SPEC.md](SPEC.md)definiert das dateibasierte
Fortsetzungsmodell und den stabilen auf-Disk-Vertrag;[CORE.md](saipen/CORE.md)
und[MAINTENANCE.md](saipen/MAINTENANCE.md)beschreiben das aktuelle normative Verhalten.
- **Maschinengeschützter Zustand.**Der stdlib-only canonical
  [Validator](tools/validate.py)liest den live
  [STATE-Schema](extensions/schemas/state.schema.json)und prüft Phase
Übergänge, Ticket-Abhängigkeiten, Event-Graph-Links, cross-document
Invarianten, Fähigkeiten und Recovery-Zustand.
- **Fehlerabdeckung.** [CONFORMANCE.md](saipen/CONFORMANCE.md)zuordnet
Anforderungen zu[Szenario-Fixtures](tests/scenarios/); der
  [Szenario-Runner](tools/run_scenarios.py)führt strukturelle Pass-/Fail-Fälle aus
einschließlich beschädigter Wiederherstellungszustände, ungültiger Übergänge, Abhängigkeitszyklen und
schreibgeschützter Einschränkungen.
- **Regression-Controls.** [audit_checks.py](tools/audit_checks.py)verändert
bekannte gute Kopien und beweist, dass die Validatoren-Prüfungen dennoch rot werden können, anstatt
eine dauerhaft grüne Prüfung als Beweis zu behandeln.
- **Ausführbare Schicht.** [saipen.py](tools/saipen.py)erstellt journaled Zustand
Vorgänge;[bootstrap/](bootstrap/)enthält install, uninstall und export
Hilfsmittel mit optionaler[pre-commit Hook-Installer](tools/install_hook.py).
- **Explizite Kompromisse.**Kernprotokollzustand sind einfache Dateien ohne Laufzeit
Abhängigkeit. Kanonische Validierung und CLI-Tools benötigen Python, verwenden aber nur
dessen Standardbibliothek und benötigen keine`pip`Installation.

## Architektur

Drei Schichten, strikt einseitige Abhängigkeiten:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Core hängt nicht von Maintenance ab: mit deaktiviertem autonomem Evolution, SAIPEN
ist dennoch ein vollständiges Fortsetzungsprotokoll — ein kalter Agent nimmt dennoch wieder auf.

- **Core Zustandsmaschine** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Autonomer Wartung**— Board angehalten(nichts nutzbar in`## TODO`,
nichts in`## DOING`)und nicht`BLOCKED`? Auto-Übergänge`HUNT` (Fehler scannen)
  → `ADD` (Funktionen entwickeln) → `HUNT`, keine Fragen gestellt. Eine Sitzung sitzt bei
  `BLOCKED`niemals automatisch jagt
  ([Wartung § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Zielmodus** — `/saipen goal <objective>`dreht das Brett um und führt den
Zielvorgang durch VERIFY/REVIEW, wodurch es in autonome Wartung gerät
bis die Abschlussregel ausgelöst wird oder die Ausführung ihre Obergrenze erreicht(3 Wellen / 20 Tickets,
dann Checkpoints und berichtet) ([Wartung § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Verfestigung**— Batch-Input wird in chirurgische Einzel-Tickets zerlegt
  (CORE § 1.8); dirty-tree-Fortsetzung bewahrt unbestätigte Arbeit(CORE § 1.5);
geheimnisartige Werte werden aus Protokollen herausgenommen(`sk-***`) (CORE § 1.2).

## Häufige Befehle

Alltägliche Einstiegspunkte; die vollständige aktuelle Oberfläche befindet sich in
[Core § 1.10](saipen/CORE.md#110-command-surface).

|Befehl|Tut|
|---|---|
| `/saipen set` |Ein Projekt übernehmen: erstellen`.saipen/`Zustand|
| `/saipen continue` |Aus einem persistierten Projektzustand fortsetzen — keine Neubriefung|
| `/saipen plan` |Eine Anfrage oder ein Roh-Backlog in Tickets umwandeln|
| `/saipen goal <text>` |Autonomer Wellenlauf gegen ein neues Ziel|
| `/saipen validate` |Konformitätschecks durchführen|
| `/saipen status` |Nur-Lesereport: Phase, Tickets, Blocker, Veraltetheit|
| `/saipen stop` |Checkpoint setzen und anhalten|

<details>
<summary><b>More commands</b></summary>

|Befehl|Tut|
|---|---|
| `/saipen hunt` |Defekt/Verbesserungssweep jetzt erzwingen|
| `/saipen markhunt` |Trocken, ungekappelter Audit — erfasst Ergebnisse, bewirkt keine Änderungen|
| `/saipen ship` |Freigabeschleusen; commit, tag und push, wenn erlaubt|
| `/saipen clean` |Board- und Zustandsreinigung|
| `/saipen translate` |Isolierte Übersetzungsfabrik|
| `/saipen prepare` / `/saipen collect` |Paketarbeit für Übergabe / ein fertiges Paket integrieren|
| `/saipen test` |Das deklarierte Testsuite ausführen, nur berichten|
| `/saipen crew` |Festgelegter Crewkreislauf(jagd → reproduzieren → aufnahme → bauen → übersetzen → dokumentieren → schiffen) |
| `/saipen improve` |Meta-Steuerungsaudit von Protokollverbesserungen|
| `/saipen sub ...` |Spawn/adopt schreibgeschützte Unteragenten|

**Paket Schlüssel.** `ee`/`qq`vollständige Übersetzung/wiki-Pakete ohne
integrieren;`eee`/`qqq`nur fertige Pakete akzeptieren, dann integrieren, überprüfen,
prüfen und pushen.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)geht das ganze
eingebaute Crew in fester Reihenfolge — Sensoren(saihunt, saitest, saipython, saiui),
Erzeuger(saitranslate, saiwiki)und Core als einzigen Haupt-Tree-Schreiber —
bis zu einem weiteren frischen Durchlauf nichts Reales mehr zu ändern bleibt. Es fügt genau einen
Mechanismus seiner eigenen: das haltbare Orchestrierungsziel(`execution_intent:
konvergieren` with `konvergierendes Ziel: crew`)das den Schaltkreis wiederherstellbar macht und
aus Beweisen ableitbar ist.`saipen crew --dry-run --json`leitet den
Schaltkreis schreibgeschützt;`bootstrap/saipen_crew.*`ist ein OPTIONALES manuelles
Multi-Window-Hilfsmittel, nie was`saipen crew`bedeutet. Siehe
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Was SAIPEN nicht ist

- **Ein LLM oder ein Modell**— es ist ein Protokoll, das Agenten befolgen, nicht eine Intelligenz.
- **Ein IDE oder eine gehostete Speicherdatenbank**— der Zustand besteht aus normalen Dateien in deinem Projekt;
nichts wird gehostet.
- **Ein Ersatz für Git**— Git besitzt weiterhin die Versionsgeschichte; commit deine
  `.saipen/`wie jeder andere Code.
- **Verteiltes Konsens**— siehe die Konkurrenzgrenze unten.
- **Eine Garantie, dass ein LLM korrekte ingenieurtechnische Entscheidungen trifft**— es
reduziert den Kontextverlust und das Verhaltensdriften; es macht keine stochastischen Agenten
fehlerfrei.

SAIPEN's Aufgabe ist ein Fortsetzungs/Zustandsvertrag plus Validierung und Tools —
dem nächsten Agenten eine maschinenüberprüfte Ausgangsbasis anstelle von Magie übergeben.

**Konkurrenzgrenze.**protokollierte Zustandsänderungen(SAIOPS)verwenden eine
projektbezogene Betriebssystem-Sperre und ein Wiederherstellungsjournal([OPS § 5](saipen/OPS.md#5-locks)).
Normale Projektbearbeitungen und nicht verbundene Schreiber befinden sich außerhalb dieser Sperre. SAIPEN
ist kein verteiltes Konsensprotokoll, daher erfordern nicht verbundene Schreiber externe
Koordination([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ökosystem

|Projekt|Beziehung zu SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Lokale Windows-Steuerzentrale für SAIPEN-Projekte — erkennt automatisch`.saipen/`Arbeitsbereiche, visualisiert den Live-Zustand und Konformitätsurteile, verwaltet Tickets und startet AI-CLIs. Ein Begleiter, nicht die Autorität.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Downstream CodeNomad-Fork, der SAIPEN integriert: injiziert`BOOT.md`/`STYLE.md`in OpenCode-Starts, macht SAIPEN-Shortcuts und Projektzustandsansichten sichtbar und fügt eine persistente Prompt-Warteschlange hinzu.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Portabler Windows-Notizblock und Snippet-Manager, der automatisch erkennt`.saipen/`Ordner und fügt einen schreibgeschützten STATE/BOARD/LOG-Viewer hinzu.|

## Dokumentation

|Dokument|Was es ist|
|---|---|
| [SPEC.md](SPEC.md) |Formale Architektur, Designziele, Litmus-Test|
| [CORE.md](saipen/CORE.md) |Normative Fortsetzung, Zustandsmaschine und Befehlsvertrag|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Autonomer Wartung und Goal-Modus|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Ausführbare/verhaltensbasierte Anforderungen und Validatorenregeln|
| [GUIDE.md](GUIDE.md) |Menschlicher Tutorial|
| [RFC.md](saipen/RFC.md) |Kompatibilitätsleitstelle zu den geteilten normativen Dokumenten|
| [STYLE.md](saipen/STYLE.md) |Kommunikationsstil und Stimme des Agenten|
| [UI.md](saipen/UI.md) |Vintage Golden UI-Designrichtlinien|
|Broschüre|Präsentationsbroschüre —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Englisch](guides/GUIDE_EN.md) · 🇪🇪 [Estnisch](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Deutsch](guides/GUIDE_DE.md) · 🇫🇷 [Französisch](guides/GUIDE_FR.md) · 🇪🇸 [Spanisch](guides/GUIDE_ES.md) · 🇮🇹 [Italienisch](guides/GUIDE_IT.md)

🇵🇹 [Portugiesisch](guides/GUIDE_PT.md) · 🇳🇱 [Niederländisch](guides/GUIDE_NL.md) · 🇵🇱 [Polnisch](guides/GUIDE_PL.md) · 🇸🇪 [Schwedisch](guides/GUIDE_SV.md) · 🇩🇰 [Dänisch](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Konfigurationshinweise

**Antwortsprache.**Der Agent antwortet in**estnisch**als Standard — das ist eine
Einstellung, nicht eine Protokollvorgabe, und nichts anderes an SAIPEN ist estnisch.
Das Protokoll, der Code, die Commits und jedes Dokument bleiben auf jedem
Wert englisch. Ändern Sie es an einem Ort: die`reply_language:`Zeile am Anfang der
[`saipen/STYLE.md`](saipen/STYLE.md). `et`estnischen,`en`englischen,`ru`russischen,
`auto`wählt aus der Nachricht, die Sie gesendet haben.

**Adapter.**Plattform nicht von dem Injector abgedeckt(DeepSeek, Qwen, standalone
OpenAI, etc.)? Prozessor-spezifische Hinweise befinden sich in`extensions/adapters/`.

## Screenshots

<details>
<summary><b>Click to expand</b></summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- translation-model: qwen3:14b contract:structured-markdown-v2 -->
<!-- source-digest: README.md sha256:bb47f7158db4a7a4fd99298427c1e4bc6859433c36435640e129cc6dad2a63b7 -->
