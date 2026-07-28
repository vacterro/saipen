# Turvallisuuskäytäntö

## Laajuus

SAIPEN on spesifikaatio plus pieni joukko paikallisia asennus/vienti -skriptejä (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`, `export.ps1`/`.sh`). Se ei aja palvelinta, ei kerää telemetriaa, eikä siirrä mitään dataa minnekään. Kaikki, mitä skriptit tekevät, on paikallisia tiedostojärjestelmän kirjoituksia tiedostoihin, joita jo hallitset (oma `~/.claude`, `~/.gemini`, projektin `.saipen/` jne.).

Tässä sovelletaan kahta eri huolellisuustasoa, ja on syytä olla tarkka sen sijaan, että väittäisi kaikenkattavaa turvallisuutta:

- **Omia konfiguraatiotiedostojasi** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.aider.conf.yml`) muokataan vain lisäämällä tai poistamalla rajattu `SAIPEN:BEGIN`/`END`-lohko, ja alkuperäinen kopioidaan `<file>.bak`-tiedostoksi ennen ensimmäistä muutosta. Poisto kirjoittaa lisäksi `<file>.uninstalled.bak` ennen poistamista.
- **Taitohakemistot**, jotka lisäysosa luo (`~/.claude/skills/saipen` ja vastaavat), ovat SAIPENin omistamia kopioita, eikä niitä **ei** varmuuskopioida: asennus ylikirjoittaa ne kokonaan ja poisto poistaa ne rekursiivisesti. Tämä on tarkoituksellista -- ne sisältävät vain kopioita tämän repon omista tiedostoista -- mutta jos muokkaat paikallista taitokopiota käsin, nämä muokkaukset menetetään seuraavassa `inject`/`uninstall`-ajossa. Säilytä mukautukset omassa konfiguraatiolohkossasi tai forkissa, ei kopioidussa taitokansiossa.

Kaksi asiaa, joista todella kannattaa tehdä turvallisuusilmoitus:
1. Bootstrap-skripti, joka tekee tiedostojärjestelmällesi tai git-historiallesi jotain muuta kuin mitä sen omat kommentit/README kuvaavat.
2. Protokollan oma salaisuuksien hygienia -sääntö (RFC.md § 1.1 -- älä koskaan kirjoita API-avaimia, tokeneita tai salasanoja tiedostoihin `STATE.md`/`BOARD.md`/`LOG.md`/`KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/`recovery/`/`logs/`), jossa on todellinen aukko, joka aiheuttaisi SAIPENia seuraavan agentin vuotavan salaisuuden versiohallintaan (committed file). Kaksi viimeistä ovat hienovaraisia: Recovery kopioi vioittuneen `STATE.md`:n sanatarkasti kohteeseen `.saipen/recovery/`, ja LOG-tiivistys siirtää rivit sanatarkasti kohteeseen `.saipen/logs/`, joten kaikki mikä saavutti alkuperäisen, arkistoidaan koneiston toimesta, jonka koko tehtävä on olla muuttamatta sisältöä.

## Tuetut versiot

Vain viimeisin tagattu julkaisu `main`-haarassa on tuettu. Tämä on protokollaspesifikaatio, ei pitkäikäinen palvelu -- LTS-haaraa ei ole.

## Haavoittuvuudesta ilmoittaminen

Avaa GitHub-issue (tiketti). Jos raportti koskee todellista, tällä hetkellä hyödynnettävissä olevaa ongelmaa (ei hypoteettista), merkitse se yksityiseksi/turvallisuustiedotteeksi (private/security advisory) tämän repon **Security** -välilehden kautta ("Report a vulnerability") julkisen issuen sijaan, jotta se ei ole julkisesti näkyvillä ennen korjauksen julkaisua.

Sisällytä mukaan: mikä skripti tai RFC-sääntö, konkreettinen skenaario ja mitä todellisuudessa tapahtuu vs. mitä pitäisi tapahtua. Sama todisteiden standardi kuin missä tahansa muussakin bugiraportissa (katso `CONTRIBUTING.md`).
