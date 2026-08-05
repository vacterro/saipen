<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Fortsetzungsprotokoll für KI-Codiereingabe-Agenten.** Dauerhafter Projekt-Speicher in
reinetext-Markdown, sodass ein kalter Agent ohne Chat-Historie `/saipen continue` ausführt
und die Arbeit in unter einer Minute wiederaufnimmt -- kein Erklärungsbedarf, jeder Anbieter, an jedem Tag.

**Ein Befehl. Null Amnesie.**

**Schnellzugriff:** `cc` setzt einen aktiven Goal Mode fort, `sss` meldet Status ohne Code anzufassen und `ss` speichert einen Checkpoint und stoppt. [Siehe die komplette 15-Tasten-Karte](saipen/RFC.md#110-command-surface). Kyrillische Zwillinge funktionieren auch: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Antwortsprache.** Der Agent antwortet standardmäßig **auf Estnisch** — das ist eine Einstellung, keine Marotte, und nichts anderes an SAIPEN ist estnisch. Geändert wird das an einer Stelle: die Zeile `reply_language:` am Anfang von [`saipen/STYLE.md`](saipen/STYLE.md). `et` Estnisch, `en` Englisch, `ru` Russisch, `auto` wählt anhand der Sprache deiner Nachricht. Das Protokoll, der Code, die Commits und alle Dokumente bleiben bei jedem Wert englisch.

**v7.195.0** | [Spezifikation](SPEC.md) | [Handbuch](GUIDE.md) | [RFC](saipen/RFC.md) | [Stil](saipen/STYLE.md) | [UI](saipen/UI.md) | [Konformität](saipen/CONFORMANCE.md) | Plain Markdown | Zero Deps | MIT

```text
Benutzer ->  /saipen continue
Agent    ->  liest STATE ("Was mache ich jetzt?")
Agent    ->  liest BOARD ("Welche Aufgabe übernehme ich?")
Agent    ->  liest next_action (führt Befehl aus)
Agent    ->  arbeitet.
```

### Projekt-Zustand > Modell-Speicher
Der Speicher lebt im Projekt, nicht im Kopf des Modells. `Projekt -> Speicher -> LLM` wird zu `Projekt -> SAIPEN State -> LLM`.

### Wichtigste Protokolllogik & Garantien
- **Kern-Zustandsautomat**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Null-Prompt-Autonomie**: Keine offenen Aufgaben mehr? Automatischer Wechsel: `HUNT` (Bugs suchen) → `ADD` (Funktionen erweitern) → `HUNT`-Schleife. Keine Fragen nötig.
- **Explizite Auslöser**: `/saipen clean` (Repo aufräumen), `/saipen translate` (isolierte `.saipen/saitranslate/`-Fabrik), `/saipen markhunt` (trockenes, unbegrenztes Audit, nur Aufzeichnung), `/saipen prepare` (Arbeit für Übergabe verpacken), `/saipen validate` (Konformitätsprüfung), `/saipen goal` (autonome Wellen-Ausführung). Meta/Steuerung: `/saipen status` (Nur-Lese-Bericht), `/saipen stop` (Kontrollpunkt setzen und anhalten). Vollständige Liste: RFC.md § 1.10.
- **Strenge Zuverlässigkeit**: Batch-Eingabeparsing (chirurgische 1-für-1-Tickets), Übernahme unsauberer Repositorys (löscht nie uncommitted Arbeit), Geheimnis-Schwärzung (`sk-***`).
- **In Entwicklung -- saicrew**: eine optionale Bonusschicht (`extensions/subs/`, ohne Core-Änderungen) für einen Multi-Agenten-Crew -- ein Core-Schreiber plus schreibgeschützte Worker `saihunt`/`saipython`, die über ihre eigene `OUTBOX.md` berichten. Derzeit im aktiven Live-Test, noch nicht Ende-zu-Ende verifiziert -- siehe `extensions/subs/crew.md`.

## Projekte mit SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Hochleistungs-Prompt-Verwaltungstool, nativ mit dem SAIPEN-Speicherprotokoll integriert.

## Zwei Ebenen

| Ebene | Erforderlich | Zweck |
|---|---|---|
| **Core** | ✅ | Arbeit sicher fortsetzen |
| **Maintenance** | Auf Core aufbauend | Software ohne neue Aufgabenstellung weiterentwickeln |

**Automatisierte Evolution.** Keine offenen To-Dos mehr vorhanden? Tippe `/saipen`: `HUNT` prüft auf Bugs, toten Code und fehlschlagende Tests. Alles sauber? `ADD` baut die nächste offensichtlich fehlende Funktion, überprüft sie und führt erneut `HUNT` aus. Produkt ausgereift -> stoppt ordnungsgemäß.

**GOAL-Modus.** `/saipen goal <was du willst>` richtet das Board neu aus (alte Tickets werden herabstufen, aber nie gelöscht) und treibt das neue Ziel voran -- kein "Soll ich fortfahren?" zwischen Tickets, VERIFY/REVIEW werden nie übersprungen. SHIP führt automatisch ein Push zu einem bestehenden Remote durch; ein brandneues Repository fragt einmal nach. Das Erreichen des Ziels ist ebenfalls kein Endpunkt -- es geht direkt in die autonome HUNT/ADD-Wartung über, bis das Produkt ausgereift oder blockiert ist oder der Lauf sein Limit erreicht (3 Wellen / 20 Tickets, setzt dann Kontrollpunkte und berichtet).

## Schnellstart

**1. Einmal pro Gerät installieren** -- lehrt Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex und jedem generischen ~/.agents/skills-Leser (FreeBuff, etc.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Projekt starten** -- öffne einen Agenten in deinem Ordner und tippe:
> `saipen set`

Keine Installation? Füge eine Zeile in einen beliebigen Agenten ein:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Plattform nicht in der Liste oben (DeepSeek, Qwen, eigenständiges OpenAI usw.)?
Plattformspezifische Hinweise befinden sich in `extensions/adapters/`.

## Dokumentation & Spezifikations-Links
- **[SPEC.md](SPEC.md)** -- formale Architektur, Entwurfsziele, Lakmustest.
- **[RFC.md](saipen/RFC.md)** -- normative Spezifikation, die von Agenten ausgeführt wird.
- **[GUIDE.md](GUIDE.md)** -- Benutzerhandbuch & ELI5-Anleitungen:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- Agenten-Kommunikationsstil & Sprachdefinition.
- **[UI.md](saipen/UI.md)** -- Vintage Golden UI-Design-Richtlinien.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- Verhaltenstest-Szenarien & Validierungsregeln.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

## ## Screenshots

<details>
<summary>Zum Aufklappen klicken</summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff-Agent-Anweisungen" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen-Screenshot 2026-08-01" width="600"/>

</details>

<!-- source-digest: README.md sha256:951d8044313a6456 -->
