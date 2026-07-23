<p align="center">
  <img src="../../assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="../../assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Fortsetzungsprotokoll für KI-Programmieragenten.** Persistenter Projektspeicher in einfachem Markdown, sodass ein "kalter" Agent ohne Chat-Verlauf `/saipen continue` ausführt und die Arbeit in unter einer Minute wieder aufnimmt -- keine erneute Einweisung, jeder Anbieter, jeden Tag.

**Ein Befehl. Null Amnesie.**

**v7.41.0** | [Spezifikation](../../SPEC.md) | [Leitfaden](../../GUIDE.md) | [RFC](../../saipen/RFC.md) | [Stil](../../saipen/STYLE.md) | [UI](../../saipen/UI.md) | [Konformität](../../saipen/CONFORMANCE.md) | einfaches Markdown | null Abhängigkeiten | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](../../guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](../../guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](../../guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](../../guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](../../guides/GUIDE_DED.md)

```text
Benutzer ->  /saipen continue
Agent    ->  liest STATE ("Was mache ich gerade?")
Agent    ->  liest BOARD ("Welche Aufgabe nehme ich auf?")
Agent    ->  liest next_action (führt Befehl aus)
Agent    ->  Arbeitet.
```

### Projektstatus > Modellspeicher
Der Speicher lebt im Projekt, nicht im Kopf eines Modells. `Projekt -> Speicher -> LLM` wird zu `Projekt -> SAIPEN Status -> LLM`.

### Wichtigste Protokolllogik & Garantien
- **Kern-Zustandsautomat**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Zero-Prompt-Autonomie**: Board leer? Automatischer Übergang `HUNT` (Bugs suchen) → `ADD` (Features entwickeln) → `HUNT` Schleife. Keine Fragen werden gestellt.
- **Explizite Auslöser**: `/saipen clean` (Repo-Bereinigung), `/saipen translate` (isolierte `.saipen/saitranslate/` Fabrik), `/saipen validate` (Konformitätsprüfung), `/saipen goal` (autonome Zielausführung).
- **Strenge Zuverlässigkeit**: Batch-Input-Parsing (chirurgische 1-für-1-Tickets), Dirty-Tree-Adoption (löscht niemals ungesicherte Arbeit), Geheimnis-Schwärzung (`sk-***`).

## Projekte, die SAIPEN nutzen
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Hochleistungs-Prompt-Management-Tool, das nativ in das SAIPEN-Speicherprotokoll integriert ist.

## Zwei Schichten

| Schicht | Erforderlich | Zweck |
|---|---|---|
| **Kern (Core)** | ✅ | Arbeit sicher fortsetzen |
| **Wartung (Maintenance)** | Oben auf Kern | Die Software ohne Aufgabenstellung weiterentwickeln |

**Automatisierte Evolution.** Board leer, tippe `/saipen`: `HUNT` prüft auf Fehler, toten Code, fehlschlagende Tests. Sauber? `ADD` baut die nächste offensichtlich fehlende Funktion, überprüft sie, sucht erneut. Produkt ist ausgereift -> stoppt ordnungsgemäß.

**ZIEL-Modus (GOAL Mode).** `/saipen goal <was du willst>` dreht das Board (alte Tickets herabgestuft, niemals gelöscht) und führt das neue Ziel aus -- kein "soll ich fortfahren?" zwischen den Tickets, VERIFY/REVIEW wird nie übersprungen. SHIP pusht automatisch zu einem existierenden Remote; ein brandneues Repo fragt immer noch einmal nach. Die Auslieferung des Ziels ist auch nicht der Endpunkt -- es fällt direkt in die autonome HUNT/ADD-Wartung, bis das Produkt ausgereift ist, blockiert ist oder der Lauf sein Limit erreicht (3 Wellen / 20 Tickets, dann Checkpoints und Berichte).

## Schnellstart

**1. Einmal pro Maschine installieren** -- lehrt Claude Code, Gemini, OpenCode, Aider, Antigravity:
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Ein Projekt starten** -- öffne einen Agenten in deinem Ordner, tippe:
> `saipen set`

Keine Installation? Füge eine Zeile bei einem beliebigen Agenten ein:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Plattform nicht in der obigen Liste (DeepSeek, Qwen, standalone OpenAI, etc.)?
Plattformspezifische Notizen befinden sich in `extensions/adapters/`.

## Dokumentations- & Spezifikationslinks
- **[SPEC.md](../../SPEC.md)** -- formale Architektur, Designziele, Lackmustest.
- **[RFC.md](../../saipen/RFC.md)** -- normative Spezifikation, die von Agenten ausgeführt wird.
- **[GUIDE.md](../../GUIDE.md)** -- menschliches Tutorial & ELI5-Leitfäden:
  - 🇷🇺 [Русский](../../guides/GUIDE_RU.md) | 🇺🇸 [English](../../guides/GUIDE_EN.md) | 🇪🇪 [Eesti](../../guides/GUIDE_EE.md) | 🇯🇵 [日本語](../../guides/GUIDE_JA.md) | 👴 [Версия Деда](../../guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](../../guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](../../guides/GUIDE_DE.md) | 🇫🇷 [Français](../../guides/GUIDE_FR.md) | 🇪🇸 [Español](../../guides/GUIDE_ES.md) | 🇮🇹 [Italiano](../../guides/GUIDE_IT.md)
  - 🇵🇹 [Português](../../guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](../../guides/GUIDE_NL.md) | 🇵🇱 [Polski](../../guides/GUIDE_PL.md) | 🇸🇪 [Svenska](../../guides/GUIDE_SV.md) | 🇩🇰 [Dansk](../../guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](../../guides/GUIDE_FI.md) | 🇳🇴 [Norsk](../../guides/GUIDE_NO.md) | 🇨🇳 [中文](../../guides/GUIDE_ZH.md) | 🇰🇷 [한국어](../../guides/GUIDE_KO.md) | 🇹🇭 [ไทย](../../guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](../../guides/GUIDE_VI.md) | 🇸🇦 [العربية](../../guides/GUIDE_AR.md) | 🇮🇱 [עברית](../../guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](../../guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](../../guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](../../guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](../../guides/GUIDE_EL.md) | 🇨🇿 [Čeština](../../guides/GUIDE_CS.md) | 🇷🇴 [Română](../../guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](../../guides/GUIDE_HU.md) | 🇧🇬 [Български](../../guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](../../guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](../../guides/GUIDE_HR.md)
- **[STYLE.md](../../saipen/STYLE.md)** -- Agentenkommunikationsstil & Stimmdefinition.
- **[UI.md](../../saipen/UI.md)** -- Designrichtlinien für die dunkle goldene Win95 UI.
- **[CONFORMANCE.md](../../saipen/CONFORMANCE.md)** -- verhaltensbezogene Testszenarien & Validator-Regeln.

<p align="center">
  <img src="../../assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
