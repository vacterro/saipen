<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Průvodce SAIPEN (Čeština)

Poslouchej, nováčku. Problém je jednoduchý: tvoji AI agenti mají paměť zlaté rybky.

**SAIPEN** je zápisník ve složce `.saipen/` ve tvém projektu.

## Rychlý start

1. **Nainstalujte jednou na počítač:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Spustit projekt:**
> `saipen set`

3. **Práce:**
> `saipen`

## Příkazy

| Příkaz | Akce |
|---|---|
| `saipen set` | Inicializovat složku paměti |
| `saipen continue` | Obnovit práci z poznámek |
| `saipen stop` | Uložit pokrok & zastavit |
| `saipen status` | Číst nástěnku |
| `saipen goal <text>` | Přepnout na nový cíl |
| `saipen clean` | Vyčistit repozitář |
| `saipen translate` | Izolované sestavení překladů do 32 jazyků |
| `saipen markhunt` | Hloubkový, neomezený audit -- pouze zaznamenává zjištění |
| `saipen prepare` | Zabalí práci k předání dalšímu agentovi |
| `saipen ship` | Spustit tok vydání |

## Dobré vědět
- Necommitnuté změny, když se vrátíš k projektu? Normální -- SAIPEN commituje až při `ship`, ne při každém kroku. Agent nejdřív zkontroluje, čí jsou to změny, než se čehokoli dotkne.
- Chceš, aby si pamatoval skutečné architektonické rozhodnutí? Ulož ho do `.saipen/KNOWLEDGE/`, buď jako jeden soubor `decisions.md`, nebo jako číslované soubory `ADR-001.md`.
- Na tomto stroji není git ani shell? Agent to řekne rovnou (`mode`, `WAIT: <category> -- <otázka>`), místo aby hádal.
- Chceš záchrannou síť? `python <saipen-klon>/tools/install_hook.py` nainstaluje kontrolu před každým commitem.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
