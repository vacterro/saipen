<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Ghid SAIPEN (Română)

Ascultă, începătorule. Problema e simplă: agenții tăi AI au memoria unui peștișor auriu.

**SAIPEN** este un caiet în folderul `.saipen/` din proiectul tău.

**Comenzi rapide:** `cc` continuă contextul proiectului până la convergență (reia un obiectiv activ dacă este setat), `sss` afișează starea fără să atingă codul, iar `ss` salvează un punct de control și se oprește. [Vezi harta completă cu 15 taste](../saipen/RFC.md#110-command-surface). Gemenii chirilici funcționează și ei: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

## Pornire rapidă

1. **Instalați o dată per mașină:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Porniți proiectul:**
> `saipen set`

3. **Lucru:**
> `saipen`

## Comenzi

| Comandă | Acțiune |
|---|---|
| `saipen set` | Inițializați folderul de memorie |
| `saipen continue` | Reluați lucrul din note |
| `saipen stop` | Salvați progresul și opriți |
| `saipen status` | Citiți panoul |
| `saipen goal <text>` | Treceți la noul obiectiv |
| `saipen clean` | Curățați depozitul |
| `saipen translate` | Construcție izolată de traducere în 32 de limbi |
| `saipen markhunt` | Audit profund și nelimitat -- doar înregistrează constatările |
| `saipen prepare` | Împachetează lucrul pentru predare către următorul agent |
| `saipen ship` | Declanșați fluxul de lansare |

## Bine de știut
- Modificări necomise când revii la proiect? Normal -- SAIPEN face commit doar la `ship`, nu la fiecare pas. Agentul verifică mai întâi ale cui sunt acele modificări înainte de a atinge ceva.
- Vrei să rețină o decizie arhitecturală reală? Pune-o în `.saipen/KNOWLEDGE/`, fie ca un singur fișier `decisions.md`, fie ca fișiere numerotate `ADR-001.md`.
- Nu ai git sau shell pe această mașină? Agentul spune asta clar (`mode`, `WAIT: <category> -- <întrebare>`) în loc să ghicească (categoria este una din șapte: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; spune ce fel de răspuns deblochează situația)
- Vrei o plasă de siguranță? `python <clonă-saipen>/tools/install_hook.py` instalează o verificare pre-commit.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
