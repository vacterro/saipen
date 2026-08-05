<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Opas (Suomi)

SAIPEN on muistilehtiö `.saipen/`-kansiossa tekoälyagenteille.

**Pikanäppäimet:** `cc` jatkaa aktiivista Goal Mode -ajoa, `sss` näyttää tilan koskematta koodiin ja `ss` tallentaa tarkistuspisteen ja pysähtyy. [Katso täydellinen 14 näppäimen kartta](../saipen/RFC.md#110-command-surface). Kyrilliset kaksoset toimivat myös: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

## Pika-aloitus

1. **Asenna kerran konetta kohti:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Käynnistä projekti:**
> `saipen set`

3. **Työskentele:**
> `saipen`

## Komennot

| Komento | Toiminto |
|---|---|
| `saipen set` | Alusta muisti-kansio `.saipen/` |
| `saipen continue` | Jatka työtä muistiinpanoista |
| `saipen stop` | Tallenna edistyminen ja pysäytä |
| `saipen status` | Lue taulu ja tila |
| `saipen goal <text>` | Siirry uuteen tavoitteeseen |
| `saipen clean` | Syvä tietovaraston siivous |
| `saipen translate` | Eristetty 32 kielen käännöksen rakennus |
| `saipen markhunt` | Syvä, rajoittamaton tarkastus -- kirjaa vain löydökset |
| `saipen prepare` | Pakkaa työn seuraavalle agentille luovutusta varten |
| `saipen ship` | Käynnistä julkaisuvirta |

## Hyvä tietää
- Tallentamattomia muutoksia, kun palaat projektiin? Normaalia -- SAIPEN committaa vasta `ship`-vaiheessa, ei joka askeleella. Agentti tarkistaa ensin, kenen muutoksia ne ovat, ennen kuin koskee mihinkään.
- Haluatko sen muistavan oikean arkkitehtuuripäätöksen? Laita se kansioon `.saipen/KNOWLEDGE/` joko tiedostona `decisions.md` tai numeroituina `ADR-001.md`-tiedostoina.
- Ei gitiä eikä shelliä tällä koneella? Agentti sanoo sen suoraan (`mode`, `WAIT: <category> -- <kysymys>`) sen sijaan että arvaisi (kategoria on yksi seitsemästä: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; se kertoo, millainen vastaus avaa tilanteen)
- Haluatko turvaverkon? `python <saipen-klooni>/tools/install_hook.py` asentaa pre-commit-tarkistuksen.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
