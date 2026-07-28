# SAIPENiin osallistuminen

SAIPEN on ensisijaisesti spesifikaatio, vasta toissijaisesti toteutus. Useimmat kontribuutiot ovat muutoksia tiedostoihin `saipen/RFC.md`, `phases/*.md` tai `tests/`-kansion vaatimustenmukaisuustyökaluihin -- ei sovelluskoodiin.

## Ennen muutoksen ehdottamista

Aja [SAIPEN Lakmustesti](SPEC.md#the-saipen-litmus-test) ideaasi vasten:
1. Tekeekö se agenttien välisestä siirtymisestä luotettavampaa?
2. Tekeekö se eri mallien käyttäytymisestä yhdenmukaisempaa?
3. Vähentääkö se kontekstin katoamisen todennäköisyyttä?

Jos vastaus on "ei" edes kahteen näistä, ehdotuksesi on tämän protokollan laajuuden ulkopuolella, vaikka se voisi olla hyödyllinen muualla.

## Puutteen raportointi

Avaa issue (tiketti), jossa kuvailet:
- missä tiedostossa/osiossa puute on (RFC.md, vaihedokumentti, skeema, testi)
- konkreettinen todiste (lainaus, komento ja sen tuloste, skenaario, jossa nykyinen käyttäytyminen rikkoutuu)
- mitä odottaisit sen sijaan

Epämääräisiin raportteihin ("tämä tuntuu oudolta") on vaikeampi reagoida kuin tiettyyn `grep`-osumaan tai toistettavaan tapaukseen. Katso bugiraporttimallista muoto, jonka tämän tulisi ottaa.

## Muutoksen tekeminen

1. Lue `saipen/RFC.md` ja asiaankuuluvat `phases/*.md` -tiedostot kokonaan ennen muokkaamista -- useimmat ilmeiset puutteet osoittautuvat jo muualla käsitellyiksi, tai ne on tarkoituksella rajattu tietyllä tavalla dokumentoidusta syystä.
2. Tarkista `CHANGELOG.md` ja `.saipen/KNOWLEDGE/decisions.md` aiemman historian osalta. Älä avaa hiljaa uudelleen päätöstä, joka on jo tehty ja hylätty -- jos sinulla on uutta todistusaineistoa siitä, että aiempi hylkäys oli väärä, sano se selvästi PR:n (Pull Request) kuvauksessa.
3. Jokainen normatiivinen muutos (MUST/MUST NOT/SHOULD) vaatii `CHANGELOG.md` -merkinnän ja, mikäli käytännöllistä, testikattavuuden tiedostoihin `tests/validate.sh` + `tests/validate.ps1` (molemmat alustat) tai skenaarion kansioon `tests/scenarios/`.
4. Aja kanoninen validaattori ennen PR:n avaamista:
   ```bash
   python tools/validate.py
   ```
   Tämä on se, jolla on väliä -- se tarkistaa STATE.md:n extensions/schemas/state.schema.json -tiedostoa vasten, käy läpi LOG.md:n tapahtumagraafin suljettujen segmenttien yli ja varmistaa runtime-manifestin ja injector-kytkennät. tests/validate.sh / validate.ps1 ovat jäädytetty kannettava pohja isännille, joilla ei ole Pythonia (ne sanovat sen jokaisen tiedoston yläosassa): vähemmän tarkistuksia, säilytetty vain, jotta isäntä ilman Pythonia ei jää tyhjän päälle. Aja ne myös, jos muutoksesi koskettaa kumpaakaan niistä, mutta älä koskaan niiden sijaan -- pelkän pohjan läpäisy todistaa paljon vähemmän kuin miltä näyttää. CI ajaa kanonisen validaattorin jokaisella pushilla ja PR:llä riippumatta (.github/workflows/validate.yml).
5. Nosta `VERSION`-numeroa `phases/ship.md` -tiedoston kaavion mukaisesti (patch vain dokumentaation selvennyksille, minor uudelle normatiiviselle käyttäytymiselle, major rikkoville sopimusmuutoksille) ja pidä `README.md`:n versiolätkä synkronoituna -- `tests/validate.sh`/`.ps1` tarkistavat tämän automaattisesti, kun niitä ajetaan tämän repon kloonista.

## Tyyli

- Protokolla- ja vaihedokumentit: ytimekäs, RFC-2119 avainsanat siellä missä niillä on merkitystä, ei täytesanoja. Katso `saipen/STYLE.md`.
- Kaikki tässä tiedostossa, commit-viestit, koodikommentit ja CHANGELOG: selkeä ja ammattimainen. Projektin omat chat/LOG -äänet (`saipen/STYLE.md`) eivät koske artefakteja.

## Mikä ei kuulu laajuuteen

- SAIPENin muuttaminen hajautetuksi konsensusjärjestelmäksi. Katso `SPEC.md`:n Samanaikaisuus ja jakautumisen rajat (Concurrency & Distribution Boundaries) -osio.
- Koneellisesti jäsennettävä LOG-merkkikielioppi olemassa olevan luurangon ulkopuolella. `LOG.md` pysyy proosana kiinteän muodon ympärillä.
- `saipen doctor` -komento tai vastaava redundantti työkalu yhdistelmälle `saipen validate` + `saipen status`.

Näitä jokaista on ehdotettu ja arvioitu aiemmin; niiden uudelleen avaaminen vaatii uusia todisteita, ei vain pelkkää uudelleen kysymistä.

