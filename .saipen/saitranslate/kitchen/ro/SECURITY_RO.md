<!-- TRANSLATED TO RO -->
# Security Policy

## Scope (Domeniu de aplicare)

SAIPEN este o specificație plus un set mic de scripturi locale de instalare/export
(`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`,
`export.ps1`/`.sh`). Nu rulează un server, nu colectează
telemetrie și nu transmite niciun fel de date nicăieri. Tot ceea ce fac
scripturile sunt scrieri locale pe sistemul de fișiere în fișiere pe care deja le controlați
(propriul dumneavoastră `~/.claude`, `~/.gemini`, proiectul `.saipen/`, etc.).

Aici se aplică două niveluri diferite de atenție și merită să fim exacți
în loc să pretindem o siguranță generală:

- **Propriile dumneavoastră fișiere de configurare** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
  `.aider.conf.yml`) sunt editate doar prin adăugarea sau eliminarea unui
  bloc delimitat `SAIPEN:BEGIN`/`END`, iar originalul este copiat în
  `<file>.bak` înainte de prima modificare. Dezinstalarea scrie suplimentar
  `<file>.uninstalled.bak` înainte de eliminare.
- **Directoarele de skill** pe care injectorul le creează (`~/.claude/skills/saipen`
  și altele asemenea) sunt copii deținute de SAIPEN și **nu** sunt salvate: instalarea
  le suprascrie integral și dezinstalarea le elimină recursiv. Acest lucru este
  intenționat -- ele nu conțin decât copii ale propriilor fișiere ale acestui depozit --
  dar dacă editați manual o copie locală de skill, acele modificări se pierd la
  următorul `inject`/`uninstall`. Păstrați personalizările în propriul bloc de
  configurare sau într-un fork, nu în interiorul folderului de skill copiat.

Cele două lucruri care merită cu adevărat un raport de securitate:
1. Un script bootstrap care face ceva în sistemul dumneavoastră de fișiere sau
   în istoricul git dincolo de ceea ce descriu propriile comentarii/README.
2. Propria regulă de igienă a secretelor a protocolului (RFC.md § 1.1 -- nu scrieți
   niciodată chei API, tokenuri, parole în `STATE.md`/`BOARD.md`/`LOG.md`/
   `KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/
   `recovery/`/`logs/`) având un gol real care ar face ca un agent
   care urmează SAIPEN să scurgă un secret într-un fișier comis (committed).
   Ultimele două sunt subtile: Recovery copiază un `STATE.md` corupt literalmente
   în `.saipen/recovery/`, iar sigilarea (sealing) LOG mută rândurile literalmente
   în `.saipen/logs/`, astfel că tot ce a ajuns la original este arhivat de un
   mecanism a cărui sarcină întreagă este să nu altereze conținutul.

## Supported Versions

Only the latest tagged release on `main` is supported. This is a
protocol specification, not a long-lived service -- there is no LTS
branch.

## Reporting a Vulnerability

Open a GitHub issue. If the report involves a real, currently-exploitable
problem (not a hypothetical), mark it as a private/security advisory via
this repository's **Security** tab ("Report a vulnerability") instead of
a public issue, so it isn't publicly visible before a fix ships.

Include: which script or RFC rule, the concrete scenario, and what
actually happens vs. what should happen. Same evidence standard as any
other bug report (see `CONTRIBUTING.md`).
