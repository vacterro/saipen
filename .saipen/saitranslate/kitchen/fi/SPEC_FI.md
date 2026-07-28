# SAIPEN Spesifikaatio

## Tiivistelmä
**Suunnittelutavoite #1: Kylmän agentin, jolla on nolla keskusteluhistoriaa, on kyettävä suorittamaan `/saipen continue` ja jatkamaan tuottavaa työtä minuutin sisällä ilman, että käyttäjää pyydetään toistamaan kontekstia.**

SAIPEN takaa, että mikä tahansa yhteensopiva tekoälyagentti voi turvallisesti jatkaa mitä tahansa projektia ilman uudelleenohjeistusta. Se on ABI (Application Binary Interface) tekoälyagenteille—yhteensopivuuskerros, joka ratkaisee amnesiaongelman. Riippumatta siitä, käytätkö Claudea tänään, Geminiä huomenna ja GPT:tä ylihuomenna, ne kaikki toimivat samaa projektin tilaa vasten vaatimatta kontekstin toistamista.

### Keskeinen filosofia: Projektin tila > Mallin muisti
Muistin tulisi elää koodin vieressä, ei toisen mallin pään sisällä. SAIPEN siirtää paradigman muodosta `Projekti -> Muisti -> LLM` muotoon `Projekti -> SAIPEN Tila -> LLM`. Muisti kuuluu projektille.

Ytimessään SAIPEN käyttää siirrettävää, tiedostopohjaista jatkamisprotokollaa LLM-agenteille. Toteutukset SAATTAVAT vaihdella. Levyllä olevan sopimuksen TÄYTYY pysyä vakaana. Kaikki tässä protokollassa on olemassa palvellakseen Jatkamistestiä (Continuation Test).

SAIPEN on evolutionaarinen, ei luova. Sen tarkoitus on saattaa ohjelmisto valmiiksi, ei keksiä sitä uudelleen. ADD laajentaa olemassa olevia suunnittelumalleja, alan käytäntöjä ja ilmeistä ominaisuussymmetriaa.

- **`STATE`**: On olemassa vastatakseen kysymykseen *"Mitä teen juuri nyt?"*
- **`BOARD`**: On olemassa vastatakseen kysymykseen *"Minkä tehtävän otan käsittelyyn?"*
- **`LOG`**: On olemassa vastatakseen kysymykseen *"Miksi tulimme tähän pisteeseen?"*
- **`KNOWLEDGE`**: On olemassa vastatakseen kysymykseen *"Mikä on tämän projektin kestävä totuus?"*
- **`next_action`**: SAIPENin sydän. Se vastaa kysymykseen *"Minkä tarkan komennon suoritan juuri tällä sekunnilla jatkaakseni työtä?"*

## SAIPEN Lakmustesti

Minkä tahansa ehdotetun muutoksen tai uuden idean protokollaan TÄYTYY läpäistä seuraavat kolme kysymystä:
1. Tekeekö se agenttien välisestä siirtymisestä luotettavampaa?
2. Tekeekö se eri mallien käyttäytymisestä yhdenmukaisempaa?
3. Vähentääkö se kontekstin katoamisen todennäköisyyttä?

Jos vastaus on "ei" edes kahteen näistä kysymyksistä, idea hylätään. SAIPEN asettaa kurinalaisuuden, toistettavuuden ja luotettavuuden uutuudenviehätyksen edelle.

## Arkkitehtuuri

Protokolla on tiukan normatiivinen. SAIPEN jakautuu käsitteellisesti kahteen kerrokseen: **Ydin (Core)** ja **Ylläpito (Maintenance)**. 
- **Ydinkerros** takaa turvallisen, toimittajaneutraalin tehtävän jatkamisen. 
- **Ylläpitokerros** on autonominen ohjelmiston evoluutiomalli, joka on rakennettu Ytimen päälle.

Kahden kerroksen alla SAIPEN erottaa kolme asiaa, jotka eivät koskaan sotkeudu toisiinsa:
**oikeellisuus ja jatkaminen** (Ydin -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, kyvykkyyksien neuvottelu, tarkistuspisteet), **valvomaton evoluutio** (Ylläpito -- `HUNT`/`ADD`/`CLEAN`, täysin toimiva puhtaan `saipen`/`saipen continue` -oletuksen alla), ja **läpimeno** (Goal-tila, Alinagentit -- molemmat eksplisiittisesti valinnaisia, §1.3/§2.4). Ota Goal-tila pois käytöstä: protokolla pysyy muuttumattomana, yksi tiketti kerrallaan. Ota aliagentit pois käytöstä: `HUNT` ajaa samat kuusi kategoriaa peräkkäin, sama tulos. Käytä pelkkää Ydintä ilman Ylläpitokerrosta lainkaan: se pätee yhä -- kylmä agentti jatkaa edelleen oikein. Jokainen kerros rakentuu allaan olevan päälle siten, että päinvastainen ei koskaan pidä paikkaansa; mikään ylävirrassa ei riipu alavirran ominaisuuden olemassaolosta.

```text
saipen/
  RFC.md                    normatiivinen spesifikaatio (jaettu Ytimeen ja Ylläpitoon)
  CONFORMANCE.md             itsetarkistusvektorit + skenaarioiden kattavuustaulukko
  SKILL.md                  ohut aloitustiedosto taitoja lukeville alustoille
  STYLE.md                  äänet: chat, LOG.md, artefaktit
  UI.md                     Dark Golden Win95 UI spesifikaatio (pakollinen UI-työlle)
  BOOT.md                   käynnistyssekvenssi / kylmäkäynnistyksen orkestrointi
  phases/                   16 docs, one per RFC § 1.6 enum value (machine-checked both ways by tools/validate.py)
    [Ydinvaiheet (Core Phases)]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Ylläpitovaiheet (Maintenance Phases)]
    hunt.md / add.md / clean.md / translate.md / markhunt.md

  [Infrastructure]
  prepare.md                työtilan valmistelu
  validate.md               vaiheiden välinen vaatimustenmukaisuus

extensions/                 <- ADAPTIIVINEN KERROS
  adapters/                 mallikohtaiset ohjesillat, alustoille, joita 
                             injektori ei tunnista automaattisesti (README.md osoittaa tänne)
  schemas/                  state.schema.json on koneellisesti luettava tiedosto tools/validate.py -ohjelmalle
                             (yksi totuuden lähde STATE:n muodolle); board/log
                             -skeemat pysyvät vain viitteellisinä (katso schemas/README.md)
  templates/                tuore .saipen/ koodipohja
  security/                 ESIMERKKI-hook, jonka voi kopioida projektiin (RFC § 1.9, liitetään VERIFY-vaiheeseen)
  performance/              ESIMERKKI-hook, jonka voi kopioida projektiin (RFC § 1.9, liitetään REVIEW-vaiheeseen)
  subs/                     ESIMERKKI vain-luku -tutkimusaliagenteista (RFC § 1.9) -- oma
                             STATE/BOARD/LOG per aliagentti, löydökset vain OUTBOXin kautta,
                             ei koskaan toista kirjoituspolkua projektiin

bootstrap/                  <- ASENNUS/VIENTI/POISTO, yksi kone kerrallaan
  inject.ps1 / .sh          asentaa SAIPEN-lohkon + taitokopiot (README Pika-aloitus)
  uninstall.ps1 / .sh       kumoaa injectin -- poistaa lohkot + taitokopiot
  export.ps1 / .sh          arkistoi projektin .saipen/-kansion varmuuskopiointia varten
  saipen_crew.bat / .sh     käynnistää SAIPEN-työryhmätyökalun

tools/                      <- KANONINEN VALIDAATTORI & REPO-TYÖKALUT
  validate.py               kanoninen vaatimustenmukaisuuden validaattori (stdlib Python, nolla
                             asennusta; validoi STATE:n suoraan state.schema.json:ia
                             vastaan, plus graafitarkistukset, joita shell-pari ei voi tehdä)
  install_hook.py           asentaa pre-commit -hookin, joka suorittaa validate.py:n
  uninstall_hook.py         poistaa tasan tuon hookin (palauttaa mahdollisen aiemman)

tests/                      <- VAATIMUSTENMUKAISUUSKERROS
  validate.ps1 / .sh        jäädytetty siirrettävä lattia isännille ilman Pythonia --
                             uudet tarkistukset laskeutuvat vain tiedostoon tools/validate.py
  scenarios/                mock-tilat (kaatumisesta toipuminen, varauskonfliktit jne.)
```

## Kaksisuuntainen kyvykkyyksien neuvottelu
Agentit eivät pelkästään ilmoita, mitä ne voivat tehdä; protokolla vaatii sitä, mitä tarvitaan.
Projekti määrittelee `requires: [filesystem, git, shell, python]` tilassaan. Agentti ristiintaulukoi isännän kyvykkyydet vaatimuksia vasten ja lukitsee itsensä `mode`-tilaan (esim. `full`, `read-only`).

## Graafipohjainen tapahtumien kirjaus
SAIPENissa logit eivät ole lineaarisia merkkijonoja. Ne muodostavat syklittömän päätösgraafin käyttäen Tapahtuma-ID:itä (Event IDs, esim. `E-001`). Tämä sallii monimutkaisen haarautumisen, agenttien yhdistymisen ja tarkat auditointipolut.

## Arkkitehtuuripäätösten tietueet (Architecture Decision Records, ADR)
Ohimenevät tapahtumalogit eivät sisällä pysyvää tietoa. SAIPEN vaatii, että rakenteelliset arkkitehtuuripäätökset säilytetään ADR:inä (esim. `KNOWLEDGE/ADR-001-use-sqlite.md`).

## Samanaikaisuus ja jakautumisen rajat
SAIPEN varmistaa tilan eheyden tiedostopohjaisten varausten (`owner`, `claim_time`) ja peräkkäisten graafien (`LOG.md`) avulla. Kuitenkin **SAIPEN on tilaprotokolla, ei hajautettu konsensusalgoritmi.**
- **Paikallinen/Jaettu tiedostojärjestelmä**: Konfliktien ratkaisu luottaa atomisiin tiedostojärjestelmän kirjoituksiin ("ensimmäinen commit voittaa").
- **Verkottuneet/Hajautetut ympäristöt**: Jos agentit toimivat toisistaan irrallisilla koneilla ilman reaaliaikaista tiedostojen synkronointia, tulee tapahtumaan kilpailutilanteita (race conditions) `BOARD.md`:n varauksissa. Hyvin hajautetuissa ympäristöissä SAIPENin levyllä olevan protokollasopimuksen TÄYTYY pysyä vakaana -- projektin tila itsessään mutatoituu jatkuvasti SAIPENin omien sääntöjen kautta (§ 1.5 tarkistuspisteet), mutta protokollan muoto, jota nämä säännöt seuraavat, ei koskaan muutu.


<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
