<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Gids (Nederlands)

SAIPEN is een geheugennotitieblok in de map `.saipen/` voor AI-agente.

## Snelstart

1. **Eenmalig installeren per machine:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Project starten:**
> `saipen set`

3. **Werken:**
> `saipen`

## Commando's

| Commando | Actie |
|---|---|
| `saipen set` | Geheugenmap `.saipen/` initialiseren |
| `saipen continue` | Werk hervatten vanuit notities |
| `saipen stop` | Voortgang opslaan & stoppen |
| `saipen status` | Bord & status lezen |
| `saipen goal <text>` | Draaien naar nieuw doel |
| `saipen clean` | Diepe opschoning van repository |
| `saipen translate` | Geïsoleerde vertaling build voor 32 talen |
| `saipen markhunt` | Diepe, ongelimiteerde audit -- registreert alleen bevindingen |
| `saipen prepare` | Verpakt het werk voor overdracht aan de volgende agent |
| `saipen ship` | Release flow activeren |

## Goed om te weten
- Niet-gecommitte wijzigingen als je terugkomt? Normaal -- SAIPEN commit alleen bij `ship`, niet bij elke stap. De agent controleert eerst van wie die wijzigingen zijn voordat hij iets aanraakt.
- Wil je dat hij een echte architectuurbeslissing onthoudt? Zet het in `.saipen/KNOWLEDGE/`, als één bestand `decisions.md` of genummerde `ADR-001.md`-bestanden.
- Geen git of shell op deze machine? De agent zegt het gewoon eerlijk (`mode`, `WAIT: <category> -- <vraag>`) in plaats van te gokken.
- Wil je een vangnet? `python <saipen-kloon>/tools/install_hook.py` installeert een pre-commit check.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
