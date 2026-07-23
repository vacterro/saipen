# Turvapoliitika

## Ulatus

SAIPEN on spetsifikatsioon pluss väike komplekt lokaalseid paigaldus/eksport-skripte (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`, `export.ps1`/`.sh`). See ei käivita serverit, ei kogu telemeetriat ega edasta mingeid andmeid kuhugi. Kõik, mida skriptid teevad, on lokaalsed failisüsteemi kirjutamised failidesse, mida sa juba kontrollid (sinu enda `~/.claude`, `~/.gemini`, projekti `.saipen/` jne), kusjuures igaüht neist kaitseb automaatne `.bak` varukoopia enne esimest muutmist.

Kaks asja, millest tasub tõesti turvaraportis teatada:
1. Alglaadimisskript teeb sinu failisüsteemile või git-ajaloole midagi muud peale selle, mida selle enda kommentaarid/README kirjeldavad.
2. Protokolli enda saladuste hügieeni reeglis (RFC.md § 1.1 -- ära kunagi kirjuta API võtmeid, tokeneid, paroole failidesse `STATE.md`/`BOARD.md`/`LOG.md`/`KNOWLEDGE/`/`kitchen/`) on tõeline lünk, mis põhjustaks SAIPEN-it järgival agendil saladuse lekkimise committitud faili.

## Toetatud Versioonid

Toetatud on ainult viimane märgistatud väljalase harul `main`. See on protokolli spetsifikatsioon, mitte pikaajaline teenus -- siin pole LTS (pikaajalise toe) haru.

## Haavatavusest teatamine

Ava GitHubi probleem (issue). Kui aruanne hõlmab tõelist, praegu ära kasutatavat probleemi (mitte hüpoteetilist), märgi see privaatseks/turvalisuse nõuandeks (security advisory) selle repositooriumi **Security** vahekaardi kaudu ("Report a vulnerability"), mitte avaliku probleemina, et see ei oleks enne paranduse ilmumist avalikult nähtav.

Lisa: milline skript või RFC reegel, konkreetne stsenaarium ja mis tegelikult juhtub vs. mis peaks juhtuma. Sama tõendistandard nagu iga muu veateate puhul (vaata `CONTRIBUTING_EE.md`).
