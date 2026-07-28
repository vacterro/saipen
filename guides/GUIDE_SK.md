<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Sprievodca SAIPEN (Slovenčina)

Počúvaj, nováčik. Problém je jednoduchý: tvoji AI agenti majú pamäť zlatej rybky.

**SAIPEN** je zápisník v priečinku `.saipen/` vo vašom projekte.

## Rýchly štart

1. **Nainštalujte raz na počítač:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Spustiť projekt:**
> `saipen set`

3. **Práca:**
> `saipen`

## Príkazy

| Príkaz | Akcia |
|---|---|
| `saipen set` | Inicializovať priečinok pamäte |
| `saipen continue` | Obnoviť prácu z poznámok |
| `saipen stop` | Uložiť pokrok a zastaviť |
| `saipen status` | Čítať nástenku |
| `saipen goal <text>` | Prepnúť na nový cieľ |
| `saipen clean` | Vyčistiť repozitár |
| `saipen translate` | Izolované zostavenie prekladu do 32 jazykov |
| `saipen markhunt` | Hĺbkový, neobmedzený audit -- iba zaznamenáva zistenia |
| `saipen prepare` | Zabalí prácu na odovzdanie ďalšiemu agentovi |
| `saipen ship` | Spustiť tok vydania |

## Dobré vedieť
- Necommitnuté zmeny, keď sa vrátiš k projektu? Normálne -- SAIPEN commituje až pri `ship`, nie pri každom kroku. Agent najprv skontroluje, čie sú tieto zmeny, kým sa čohokoľvek dotkne.
- Chceš, aby si pamätal skutočné architektonické rozhodnutie? Ulož ho do `.saipen/KNOWLEDGE/`, buď ako jeden súbor `decisions.md`, alebo ako číslované súbory `ADR-001.md`.
- Na tomto stroji nie je git ani shell? Agent to povie priamo (`mode`, `WAIT: <category> -- <otázka>`), namiesto hádania.
- Chceš záchrannú sieť? `python <saipen-klon>/tools/install_hook.py` nainštaluje kontrolu pred každým commitom.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
