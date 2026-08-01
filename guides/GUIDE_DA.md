<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Guide (Dansk)

SAIPEN er en hukommelsesnotesbog i mappen `.saipen/` til AI-agenter.

**Hurtigtaster:** `cc` fortsætter en aktiv Goal Mode-kørsel, `sss` viser status uden at røre koden, og `ss` gemmer et kontrolpunkt og stopper. [Se hele 11-tasters kortet](../saipen/RFC.md#110-command-surface). Kyrilliske tvillinger virker også: `сс`, `ссс`, `аа`, `ее`, `рр`.

## Hurtig Start

1. **Installer én gang pr. maskine:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Start projekt:**
> `saipen set`

3. **Arbejde:**
> `saipen`

## Kommandoer

| Kommando | Handling |
|---|---|
| `saipen set` | Initialiser hukommelsesmappe `.saipen/` |
| `saipen continue` | Genoptag arbejde fra noter |
| `saipen stop` | Gem fremskridt & stop |
| `saipen status` | Læs tavle & status |
| `saipen goal <text>` | Skift til nyt mål |
| `saipen clean` | Dybdegående oprydning af repository |
| `saipen translate` | Isoleret 32-sproget oversættelsesbyg |
| `saipen markhunt` | Dybdegående, ubegrænset revision -- registrerer kun fund |
| `saipen prepare` | Pakker arbejdet til overdragelse til næste agent |
| `saipen ship` | Udløs udgivelsesflow |

## Godt at vide
- Ikke-committede ændringer, når du kommer tilbage? Normalt -- SAIPEN committer først ved `ship`, ikke ved hvert trin. Agenten tjekker først, hvis ændringer det er, før den rører noget.
- Vil du have, at den husker en rigtig arkitekturbeslutning? Læg den i `.saipen/KNOWLEDGE/`, som en fil `decisions.md` eller nummererede `ADR-001.md`-filer.
- Ingen git eller shell på maskinen? Agenten siger det ligeud (`mode`, `WAIT: <category> -- <spørgsmål>`) i stedet for at gætte (kategorien er en af syv: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; den fortæller, hvilken type svar der låser op)
- Vil du have et sikkerhedsnet? `python <saipen-klon>/tools/install_hook.py` installerer et pre-commit-tjek.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
