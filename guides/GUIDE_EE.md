<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Juhis (Eesti)

Kuula siia, algaja. Probleem on lihtne: sinu AI agentidel on kuldkala mälu. Eile veetsid pool päeva oma arhitektuuri selgitades ja täna avad uue vestluse ning see hakkab kõike nullist ehitama ja lollakaid küsimusi küsima.

**SAIPEN** on lihtsalt üks kuradi märkmik kaustas `.saipen/`.

## Lühijuhend

1. **Paigalda üks kord masina kohta:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Käivita projektis:**
> `saipen set`

3. **Tööta:**
> `saipen`

## Käsud

| Käsk | Tegevus |
|---|---|
| `saipen set` | Initsialiseeri mälukaust `.saipen/` |
| `saipen continue` | Jätka tööd märkmete põhjal |
| `saipen stop` | Salvesta progress ja peatu |
| `saipen clean` | Sunnib agenti tööruumi puhastama, vanu lõpetatud pileteid eemaldama, orbfaile kustutama, katkisi teid parandama ja kõike uuendama. |
| `saipen translate` | Loob/uuendab 32-keelset tõlkepaketti isoleeritud kaustas `.saipen/saitranslate/`, puutumata teie lähtekoodi. |
| `saipen markhunt` | Teostab projekti sügava auditi ja salvestab leiud BOARD.md faili ilma midagi parandamata. |
| `saipen ship` | Käivitab otseselt väljalaske (versiooni uuendamine, muudatuste logi, silt, üleslaadimine) isegi väljaspool tavalist piletivoogu. |

## Kasulik teada
- Kui tuled projekti juurde tagasi ja leiad salvestamata muudatusi, on see normaalne -- SAIPEN teeb commiti alles `ship` käigus, mitte iga sammu järel. Agent kontrollib enne millegi puudutamist, kelle muudatused need on.
- Kui tahad, et agent mäletaks päris arhitektuuriotsust, pane see kausta `.saipen/KNOWLEDGE/` kas ühe faili `decisions.md` või nummerdatud failidena `ADR-001.md`.
- Kui masinas pole gitti ega shelli, ütleb agent seda otse (`mode`, `WAIT: <küsimus>`), selle asemel et arvata.
- Turvavõrku tahad? `python <saipen-kloon>/tools/install_hook.py` paigaldab commit-eelse kontrolli. Tüdinud? `python <saipen-kloon>/tools/uninstall_hook.py` võtab selle maha (ja toob vajadusel vana konksu tagasi).
- **Katseline:** `saipen sub spawn saihunt` -- üks käsk, toob `.saipen/extensions/subs/` ise SAIPEN kodust, kui projektis pole seda veel. Saad isoleeritud read-only agendi, kes uurib projekti ja annab leiud oma `OUTBOX.md` kaudu -- koodi ennast ei puuduta. Valmis kaks: `saiwiki` (dokumendid) ja `saihunt` (vearaha). Täiesti uus, lahinguarme veel pole.
