# Turvapoliitika

## Ulatus

SAIPEN on spetsifikatsioon pluss väike komplekt lokaalseid paigaldus/eksport-skripte (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`, `export.ps1`/`.sh`). See ei käivita serverit, ei kogu telemeetriat ega edasta mingeid andmeid kuhugi. Kõik, mida skriptid teevad, on lokaalsed failisüsteemi kirjutamised failidesse, mida sa juba kontrollid (sinu enda `~/.claude`, `~/.gemini`, projekti `.saipen/` jne).

Siin kehtib kaks erinevat hoolitsuse taset ja tasub olla täpne, mitte väita üldist ohutust:

- **Sinu enda konfiguratsioonifailid** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.aider.conf.yml`) muudetakse ainult märgistatud `SAIPEN:BEGIN`/`END` ploki lisamise või eemaldamise teel, ja originaal kopeeritakse `<file>.bak` alla enne esimest muutmist. Uninstall lisaks kirjutab `<file>.uninstalled.bak` enne eemaldamist.
- **Oskuste kataloogid**, mille injector loob (`~/.claude/skills/saipen` jt), on SAIPENi omanduses olevad koopiad ja neid **ei** varundata: paigaldus kirjutab need täielikult üle ja uninstall eemaldab rekursiivselt. See on tahtlik — need sisaldavad ainult selle repositooriumi enda failide koopiaid — aga kui sa redigeerid kohalikku oskuste koopiat käsitsi, lähevad need muudatused kaduma järgmisel `inject`/`uninstall` käivitamisel. Hoia kohandusi oma konfiguratsiooniplokis või hargnemises (fork), mitte kopeeritud oskuste kausta sees.

Kaks asja, millest tasub tõesti turvaraportis teatada:
1. Alglaadimisskript teeb sinu failisüsteemile või git-ajaloole midagi muud peale selle, mida selle enda kommentaarid/README kirjeldavad.
2. Protokolli enda saladuste hügieeni reeglis (RFC.md § 1.1 -- ära kunagi kirjuta API võtmeid, tokeneid, paroole failidesse `STATE.md`/`BOARD.md`/`LOG.md`/`KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/`recovery/`/`logs/`) on tõeline lünk, mis põhjustaks SAIPENit järgival agendil saladuse lekkimise committitud faili. Kaks viimast on kõige peenemad: Recovery kopeerib rikutud `STATE.md` sõna-sõnalt `.saipen/recovery/` alla ja LOG sealing liigutab ridu sõna-sõnalt `.saipen/logs/` alla, nii et kõik, mis jõudis originaali, arhiveeritakse mehhanismi poolt, mille terve töö on mitte muuta sisu.

## Toetatud Versioonid

Toetatud on ainult viimane märgistatud väljalase harul `main`. See on protokolli spetsifikatsioon, mitte pikaajaline teenus -- siin pole LTS (pikaajalise toe) haru.

## Haavatavusest teatamine

Ava GitHubi probleem (issue). Kui aruanne hõlmab tõelist, praegu ära kasutatavat probleemi (mitte hüpoteetilist), märgi see privaatseks/turvalisuse nõuandeks (security advisory) selle repositooriumi **Security** vahekaardi kaudu ("Report a vulnerability"), mitte avaliku probleemina, et see ei oleks enne paranduse ilmumist avalikult nähtav.

Lisa: milline skript või RFC reegel, konkreetne stsenaarium ja mis tegelikult juhtub vs. mis peaks juhtuma. Sama tõendistandard nagu iga muu veateate puhul (vaata `CONTRIBUTING.md`).

<!-- source-digest: SECURITY.md sha256:a456565d1c932485 -->
