# SAIPEN Spezifikation

## Abstrakt
**Designziel #1: Ein "kalter" Agent ohne Chatverlauf muss in der Lage sein, `/saipen continue` auszuführen und produktive Arbeit innerhalb einer Minute wieder aufzunehmen, ohne den Benutzer bitten zu müssen, den Kontext zu wiederholen.**

SAIPEN garantiert, dass jeder kompatible KI-Agent jedes Projekt sicher fortsetzen kann, ohne neu eingewiesen zu werden. Es ist ein ABI (Application Binary Interface) für Engineering-KI-Agenten – eine Kompatibilitätsschicht, die das Amnesie-Problem löst. Egal, ob du heute Claude, morgen Gemini und übermorgen GPT nutzt, sie alle arbeiten mit demselben Projektstatus, ohne dass du den Kontext neu erklären musst.

### Kernphilosophie: Projektstatus > Modellspeicher
Der Speicher sollte neben dem Code leben, nicht im Kopf eines anderen Modells. SAIPEN verlagert das Paradigma von `Projekt -> Speicher -> LLM` zu `Projekt -> SAIPEN Status -> LLM`. Der Speicher gehört zum Projekt.

Im Kern verwendet SAIPEN ein portables, dateibasiertes Fortsetzungsprotokoll für LLM-Agenten. Implementierungen KÖNNEN variieren. Der On-Disk-Vertrag MUSS stabil bleiben. Alles in diesem Protokoll existiert, um dem Fortsetzungstest zu dienen.

SAIPEN ist evolutionär, nicht kreativ. Sein Zweck ist es, Software zu vervollständigen, nicht sie neu zu erfinden. ADD erweitert bestehende Entwurfsmuster, Branchenkonventionen und offensichtliche Feature-Symmetrien.

- **`STATE`**: Existiert, um zu beantworten *"Was mache ich genau jetzt?"*
- **`BOARD`**: Existiert, um zu beantworten *"Welche Aufgabe nehme ich auf?"*
- **`LOG`**: Existiert, um zu beantworten *"Warum sind wir an diesem Punkt angelangt?"*
- **`KNOWLEDGE`**: Existiert, um zu beantworten *"Was ist die dauerhafte Wahrheit dieses Projekts?"*
- **`next_action`**: Das Herzstück von SAIPEN. Es beantwortet *"Welchen genauen Befehl führe ich in dieser Sekunde aus, um die Arbeit wieder aufzunehmen?"*

## Der SAIPEN Lackmustest

Jede vorgeschlagene Änderung oder neue Idee für das Protokoll MUSS die folgenden drei Fragen bestehen:
1. Macht sie den Übergang zwischen Agenten zuverlässiger?
2. Macht sie das Verhalten verschiedener Modelle einheitlicher?
3. Verringert sie die Wahrscheinlichkeit von Kontextverlusten?

Wenn die Antwort auf mindestens zwei dieser Fragen "Nein" lautet, wird die Idee abgelehnt. SAIPEN zieht Disziplin, Reproduzierbarkeit und Zuverlässigkeit der Neuartigkeit vor.

## Architektur

Das Protokoll ist streng normativ. SAIPEN unterteilt sich konzeptionell in zwei Schichten: **Kern (Core)** und **Wartung (Maintenance)**.
- **Die Kernschicht** garantiert eine sichere, herstellerneutrale Fortsetzung der Aufgaben.
- **Die Wartungsschicht** ist ein autonomes Software-Evolutionsmodell, das auf dem Kern aufbaut.

Unterhalb der beiden Schichten trennt SAIPEN drei Belange, die sich nie verflechten:
**Korrektheit und Fortsetzung** (Kern -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, Fähigkeits-Verhandlung, Checkpointing), **unbeaufsichtigte Evolution** (Wartung -- `HUNT`/`ADD`/`CLEAN`, voll funktionsfähig unter dem reinen `saipen`/`saipen continue` Standard) und **Durchsatz** (Ziel-Modus, Subagenten -- beide explizit opt-in, §1.3/§2.4). Ziel-Modus deaktivieren: Das Protokoll bleibt unverändert, ein Ticket nach dem anderen. Subagenten deaktivieren: `HUNT` führt dieselben sechs Kategorien nacheinander aus, gleiches Ergebnis. Nutze nur den Kern, ganz ohne Wartungsschicht: Es hält immer noch -- ein kalter Agent nimmt die Arbeit trotzdem korrekt wieder auf. Jede Schicht baut auf der darunterliegenden auf, ohne dass das Umgekehrte jemals zutrifft; nichts Stromaufwärts liegendes hängt von einem Stromabwärts liegenden Feature ab.

```text
saipen/
  RFC.md                    normative Spezifikation (unterteilt in Kern und Wartung)
  CONFORMANCE.md             Selbsttest-Vektoren + Szenario-Abdeckungstabelle
  SKILL.md                  dünner Einstiegspunkt für Skill-lesende Plattformen
  STYLE.md                  Stimmen: Chat, LOG.md, Artefakte
  UI.md                     Spezifikation für Dunkle Goldene Win95 UI (obligatorisch für UI-Arbeiten)
  phases/                   strikte Zustandsautomaten-Logik
    [Kern-Phasen]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Wartungs-Phasen]
    hunt.md / add.md / clean.md / translate.md
    
    validate.md             Konformitätsprüfung

extensions/                 <- DIE ADAPTIVE SCHICHT
  adapters/                 modellspezifische Anweisungsbrücken, für Plattformen, die der
                             Injektor nicht automatisch erkennt (README.md verweist hierher)
  schemas/                  state.schema.json wird maschinell von tools/validate.py gelesen
                             (einzige Quelle der Wahrheit für die Form von STATE); board/log
                             Schemas bleiben nur als Referenz (siehe schemas/README.md)
  templates/                frische .saipen/ Boilerplate
  security/                 BEISPIEL-Hook zum Kopieren in ein Projekt (RFC § 1.9, hängt an VERIFY)
  performance/              BEISPIEL-Hook zum Kopieren in ein Projekt (RFC § 1.9, hängt an REVIEW)
  subs/                     BEISPIEL Nur-Lese Forschungs-Subagenten (RFC § 1.9) -- eigenes
                             STATE/BOARD/LOG pro Subagent, Ergebnisse nur über OUTBOX,
                             niemals ein zweiter Schreibpfad in das Projekt

bootstrap/                  <- INSTALLIEREN/EXPORTIEREN/DEINSTALLIEREN, jeweils auf einer Maschine
  inject.ps1 / .sh          installiert den SAIPEN Block + Skill Kopien (README Schnellstart)
  uninstall.ps1 / .sh       macht inject rückgängig -- entfernt Blöcke + Skill Kopien
  export.ps1 / .sh          archiviert ein Projekt .saipen/ für Backups

tools/                      <- KANONISCHER VALIDATOR & REPO UTILITIES
  validate.py               kanonischer Konformitätsvalidator (stdlib Python, keine
                             Installationen; validiert STATE direkt gegen state.schema.json,
                             plus Graph-Prüfungen, die das Shell-Paar nicht durchführen kann)
  install_hook.py           installiert einen pre-commit Hook, der validate.py ausführt
  uninstall_hook.py         entfernt genau diesen Hook (stellt jeden vorherigen wieder her)

tests/                      <- KONFORMITÄTSSCHICHT
  validate.ps1 / .sh        eingefrorene portable Basis für Hosts ohne Python --
                             neue Prüfungen landen nur in tools/validate.py
  scenarios/                Mock-Zustände (Crash-Recovery, Claim-Konflikte, etc.)
```

## Zwei-Wege-Fähigkeitsverhandlung
Agenten erklären nicht einfach, was sie können; das Protokoll fordert, was benötigt wird.
Das Projekt definiert `requires: [filesystem, git, shell, python]` in seinem Status. Der Agent gleicht seine Host-Fähigkeiten ab und sperrt sich in einen `mode` (z.B. `full`, `read-only`).

## Graph-basierte Ereignisprotokollierung
Logs in SAIPEN sind keine linearen Zeichenketten. Sie bilden einen azyklischen Graphen von Entscheidungen unter Verwendung von Event-IDs (`E-001`). Dies ermöglicht komplexe Verzweigungen, Agentenzusammenführungen und präzise Audit-Trails.

## Architecture Decision Records (ADR)
Flüchtige Ereignisprotokolle beherbergen kein dauerhaftes Wissen. SAIPEN schreibt vor, dass strukturelle architektonische Entscheidungen als ADRs (z.B. `KNOWLEDGE/ADR-001-use-sqlite.md`) aufbewahrt werden.

## Nebenläufigkeits- & Verteilungsgrenzen
SAIPEN gewährleistet die Zustandsintegrität über dateibasierte Claims (`owner`, `claim_time`) und sequenzielle Graphen (`LOG.md`). Allerdings ist **SAIPEN ein Zustandsprotokoll, kein verteilter Konsensalgorithmus.**
- **Lokales/Gemeinsames Dateisystem**: Die Konfliktauflösung beruht auf atomaren Dateisystem-Schreibvorgängen ("der erste Commit gewinnt").
- **Vernetzte/Verteilte Umgebungen**: Wenn Agenten über getrennte Maschinen hinweg ohne Dateisynchronisation in Echtzeit arbeiten, treten Race-Conditions bei `BOARD.md`-Claims auf. In stark verteilten Setups MUSS der SAIPEN On-Disk-Protokollvertrag stabil bleiben -- der Projektstatus selbst mutiert ständig durch SAIPENs eigene Regeln (§ 1.5 Checkpointing), niemals die Form des Protokolls, denen diese Regeln folgen.

<p align="center">
  <img src="../../assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
