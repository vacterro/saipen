<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Guide (Svenska)

SAIPEN är en minnesanteckningsbok i mappen .saipen/ för AI-agenter.

AI agents have one fatal flaw: they forget. Close the window and everything they learned about your project is gone — what you were building, what failed, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch. SAIPEN is the fix: a persistent notebook in the .saipen/ folder. The agent reads STATE and BOARD on startup, sees exactly where it left off, and gets back to work without a single repeated word.

**Snabbkommandon:** `cc` fortsätter projektets kontext till konvergens (återupptar ett aktivt mål om ett är satt), `sss` visar status utan att röra koden och `ss` sparar en kontrollpunkt och stannar. [Se hela 15-tangentkartan](../saipen/RFC.md#110-command-surface). Kyrilliska tvillingar fungerar också: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

## Snabbstart

1. **Installera en gång per maskin:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Starta projekt:**
> `saipen set`

3. **Arbeta:**
> `saipen`

## Kommandon

| Kommando | Åtgärd |
|---|---|
| `saipen set` | Initiera minnesmapp `.saipen/` |
| `saipen continue` | Återuppta arbete från anteckningar |
| `saipen stop` | Spara framsteg & stanna |
| `saipen status` | Läs tavla & status |
| `saipen goal <text>` | Växla till nytt mål |
| `saipen clean` | Djupgående rensning av arkiv |
| `saipen translate` | Isolerad 32-språkig översättningsbygge |
| `saipen markhunt` | Djup, obegränsad granskning -- registrerar bara fynd |
| `saipen prepare` | Paketerar arbetet för överlämning till nästa agent |
| `saipen ship` | Utlös lanseringsflöde |

## Bra att veta
- Ocommittade ändringar när du kommer tillbaka? Normalt -- SAIPEN committar först vid `ship`, inte vid varje steg. Agenten kollar först vems ändringar det är innan den rör något.
- Vill du att den ska minnas ett riktigt arkitekturbeslut? Lägg det i `.saipen/KNOWLEDGE/`, som en fil `decisions.md` eller numrerade `ADR-001.md`-filer.
- Ingen git eller shell på maskinen? Agenten säger det rakt ut (`mode`, `WAIT: <category> -- <fråga>`) istället för att gissa (kategorin är en av sju: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; den säger vilken typ av svar som låser upp).
- Vill du ha ett skyddsnät? `python <saipen-klon>/tools/install_hook.py` installerar en pre-commit-kontroll.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.


