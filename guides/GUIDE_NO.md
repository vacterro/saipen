<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Guide (Norsk)

SAIPEN er en minnenotatbok i mappen `.saipen/` for AI-agenter.

**Hurtigtaster:** `cc` fortsetter en aktiv Goal Mode-kjøring, `sss` viser status uten å røre koden, og `ss` lagrer et sjekkpunkt og stopper. [Se hele 15-tasters kartet](../saipen/RFC.md#110-command-surface). Kyrilliske tvillinger fungerer også: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

## Hurtigstart

1. **Installer én gang per maskin:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Start prosjekt:**
> `saipen set`

3. **Arbeid:**
> `saipen`

## Kommandoer

| Kommando | Handling |
|---|---|
| `saipen set` | Initaliser minnemappe `.saipen/` |
| `saipen continue` | Gjenoppta arbeid fra notater |
| `saipen stop` | Lagre fremdrift & stopp |
| `saipen status` | Les tavle & status |
| `saipen goal <text>` | Bytt til nytt mål |
| `saipen clean` | Dyp repository-opprydding |
| `saipen translate` | Isolert 32-språklig oversettelsesbygg |
| `saipen markhunt` | Dyp, ubegrenset revisjon -- registrerer funn uten å fikse |
| `saipen prepare` | Pakker arbeidet for overlevering til neste agent |
| `saipen ship` | Utløs lanseringsflyt |

## Greit å vite
- Ikke-committede endringer når du kommer tilbake? Normalt -- SAIPEN committer først ved `ship`, ikke ved hvert steg. Agenten sjekker først hvem sine endringer det er, før den rører noe.
- Vil du at den skal huske en ekte arkitekturbeslutning? Legg den i `.saipen/KNOWLEDGE/`, som en fil `decisions.md` eller nummererte `ADR-001.md`-filer.
- Ingen git eller shell på denne maskinen? Agenten sier det rett ut (`mode`, `WAIT: <category> -- <spørsmål>`) i stedet for å gjette (kategorien er en av syv: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; den forteller hva slags svar som låser opp)
- Vil du ha et sikkerhetsnett? `python <saipen-klone>/tools/install_hook.py` installerer en pre-commit-sjekk.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
