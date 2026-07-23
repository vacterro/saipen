# SAIPEN-i panustamine

SAIPEN on esmalt spetsifikatsioon, teiseks rakendus. Enamik panuseid on muudatused failis `saipen/RFC.md`, failides `phases/*.md` või vastavustööriistades kaustas `tests/` -- mitte rakenduse koodis.

## Enne muudatuse väljapakkumist

Käivita [SAIPEN Lakmustest](SPEC_EE.md#saipen-lakmustest) oma idee peal:
1. Kas see muudab agentide vahelise ülemineku töökindlamaks?
2. Kas see muudab erinevate mudelite käitumise ühtlasemaks?
3. Kas see vähendab konteksti kaotamise tõenäosust?

Kui vastus on "ei" vähemalt kahele neist, on see protokolli ulatusest väljas, ükskõik kui kasulik see mujal ka poleks.

## Lüngast teatamine

Ava probleem (issue), kirjeldades:
- millises failis/jaotises lünk on (RFC.md, faasi dokument, skeem, test)
- konkreetsed tõendid (tsitaat, käsk ja selle väljund, stsenaarium, kus praegune käitumine puruneb)
- mida sa selle asemel ootaksid

Ebamäärased aruanded ("see tundub vale") on raskemini lahendatavad kui konkreetne `grep`/taasesitus. Vaata veateate malli (issue template), et näha, milline peaks aruanne välja nägema.

## Muudatuse tegemine

1. Loe enne muutmist täielikult läbi `saipen/RFC.md` ja asjakohased `phases/*.md` fail(id) -- enamik näilisi lünki on osutunud juba mujal lahendatuks või teadlikult teatud viisil piiritletuks dokumenteeritud põhjusel.
2. Kontrolli `CHANGELOG.md` ja `.saipen/KNOWLEDGE/decisions.md` eelnevat kunsti (prior art). Ära ava vaikselt uuesti otsust, mis on juba tehtud ja tagasi lükatud -- kui sul on uusi tõendeid, et varasem tagasilükkamine oli vale, ütle seda selgesõnaliselt PR (Pull Request) kirjelduses.
3. Iga normatiivne muudatus (MUST/MUST NOT/SHOULD) nõuab sissekannet `CHANGELOG.md` failis ja võimalusel katvust testides `tests/validate.sh` + `tests/validate.ps1` (mõlemad platvormid) või fiksaatorit `tests/scenarios/` all.
4. Käivita mõlemad validaatorid enne PR avamist:
   ```bash
   bash tests/validate.sh
   powershell -File tests/validate.ps1
   ```
5. Suurenda `VERSION` vastavalt `phases/ship.md` skeemile (patch ainult dokumentatsiooni selgituste jaoks, minor uue normatiivse käitumise jaoks, major lepingut rikkuvate muudatuste jaoks) ja hoia `README.md` versioonimärk sünkroonis -- `tests/validate.sh`/`.ps1` kontrollivad seda automaatselt, kui neid käivitatakse sellest kloonist.

## Stiil

- Protokolli ja faaside dokumendid: lühikesed, RFC-2119 võtmesõnad seal, kus need on olulised, ei mingit täitematerjali. Vaata `saipen/STYLE.md`.
- Kõik selles failis, commit-sõnumid, koodikommentaarid ja CHANGELOG: lihtsad ja professionaalsed. Projekti enda vestluse/LOG hääled (`saipen/STYLE.md`) ei kehti artefaktide kohta.

## Mis on ulatusest väljas

- SAIPEN-i muutmine hajutatud konsensussüsteemiks. Vaata `SPEC_EE.md` Concurrency & Distribution Boundaries jaotist.
- Masinloetav LOG-markeri grammatika väljaspool olemasolevat karkassi. `LOG.md` jääb kindla kuju ümber olevaks proosaks.
- `saipen doctor` käsk või midagi sarnast, mis oleks üleliigne võrreldes `saipen validate` + `saipen status`.

Neid kõiki on varem pakutud ja hinnatud; nende uuesti avamine vajab uusi tõendeid, mitte lihtsalt uuesti küsimist.
