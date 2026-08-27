<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
</p>

<div align="center">
  <h3><a href="README.ee.md">🇪🇪 LOE SEDA EESTI KEELES / ESTONIAN 🇪🇪</a></h3>
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="README.ded.md">👴 Дед-Версия (Russian)</a> &nbsp;|&nbsp;
  <a href="README.ja.md">🇯🇵 日本語 (Japanese)</a>
</div>

# SAIPEN

**Jatko-protokolla AI-koodausagentteja varten.**Projektin muisti sijaitsee yksinkertaisessa
Markdown-tiedostojen sisällä projektissa(`.saipen/`), joten mikä tahansa yhteensopiva kylmä agentti —
ei keskusteluhistoriaa, ei istuntomuistia — voi suorittaa`/saipen continue`, lukea
tallennetun`next_action`, ja jatkaa työtä ilman, että käyttäjältä kysytään uudelleen selittämään
mitään. Tilaa kuuluu projektin omaan, ei yhden mallivendorin muistiin.

**Yksi komento jatkaakseen. Yksinkertaisen tiedoston tila. Koneen tarkistamat sopimukset.**

Tallennusvalvonta tarkistaa itsensä jokaisella pushilla; asennus, tila, tarkistukset ja
poistaminen on paikallinen — ei pilvessä, ei taustaprosessia, ei tietokantaa.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.231.7** | [Spesifikaatio](SPEC.md) | [Ohje](GUIDE.md) | [Ydin](saipen/CORE.md) | [Hoidot](saipen/MAINTENANCE.md) | [Tyyli](saipen/STYLE.md) | [Käyttöliittymä](saipen/UI.md) | [Soveltuvuus](saipen/CONFORMANCE.md) |MIT

**Pikanäppäimet:** `cc` jatkaa projektin kontekstia konvergenssiin (jatkaa käynnissä olevaa tavoitetta, jos sellainen on asetettu), `sss` näyttää tilan koskematta koodiin ja `ss` tallentaa tarkistuspisteen ja pysähtyy. [Katso täydellinen 19 näppäimen kartta](saipen/RFC.md#110-command-surface). Kyrilliset kaksoset toimivat myös: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

```text
Project
  |
  +-- .saipen/STATE.md ------ what is happening right now (phase, ticket, mode, next_action)
  +-- .saipen/BOARD.md ------ what work exists (DOING / TODO / DONE / BLOCKED)
  +-- .saipen/LOG.md -------- why the project reached this state (event history)
  +-- .saipen/KNOWLEDGE/ ---- what durable facts must survive sessions
          |
          v
   /saipen continue
          |
          v
      cold agent
          |
          v
     next_action -> work -> checkpoint -> next ticket
```

## Mitä jää jäljelle

Live-hankkeen muisti on tallennettuna tiedostoihin`.saipen/`— yksinkertaisiin tiedostoihin, joita voit lukea, vertailla ja
kommentoida koodin vieressä. Kylmä agentti vastaa viiteen kysymykseen tiedostoista
yksin:

|Tiedosto / kenttä|Vastaukset|
|---|---|
| `STATE.md` |Mitä tapahtuu juuri nyt?(vaihe, aktiivinen tiketti, toimintatila, este) |
| `BOARD.md` |Mikä työ on olemassa / mikä on aktiivista?(tiketin graafi: TEHDÄÄN, TEHTÄVÄ, TEHTY, ESTELTY) |
| `LOG.md` |Miksi projektin on saavuttanut tämän tilan?(lisäysgraafi) |
| `KNOWLEDGE/` |Mikä kestävä projektin tiedot on säilytettävä istuntosession yli?|
| `next_action` (sisällä`STATE.md`) |Mikä tarkka toimenpide seuraavan agentin on suoritettava?|

Tämä on kohdantarkistus-sopimus, ei suunnittelusuosituksia:`saipen stop`ja jokainen
tiketin siirtymä kirjoittaa tiedostot kiinteässä järjestyksessä, ja tulos tarkistetaan
validaattorilla. Ei mitään tallenneta verkkotallennustietokantaan, eikä mitään menetetä, kun
istunto loppuu.

## Pikasuositus

**1. Asenna kerran laitteelle**— opettaa Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity, ja minkä tahansa yleisen`~/.agents/skills`lukijan(FreeBuff, jne.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`lohko agentin ohjeeseen
tiedostot, joita sinulla jo on(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— varmuuskopioidaan`.bak`ensin —
ja kopioi protokollan vastaaviin taitotaso-haarojen kansioihin. Ei mitään muuta kuin näissä
polkuja, ei taustaprosessia, ei verkkokutsuja.</sub>

**2. Aloita projektin**— avaa agentti kansiossa, kirjoita:

> `saipen set`

**Asennus vaadittu?**Liitä yksi rivi mihin tahansa agenttiin:

> Lue&lt;clone&gt;/saipen/BOOT.md ensin(kylmäkäynnistysydin), sitten&lt;clone&gt;/saipen/INDEX.md +&lt;klooni&gt;/saipen/STYLE.md ja seuraa niitä.

**Muuttuitko mielentyössäsi?**Yksi komento palauttaa sen takaisin:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Se poistaa tarkan merkityn kohdan(jättäen muun tiedoston muutoksen huomiotta), tallentaa
a `.uninstalled.bak`tee ensin kopio ja poista taidotiedostot.

## Miksi ei vain keskusteluhistoriaa?

SAIPEN kohdellaan tiettyä epäonnistumista: AI-koodityökalu, joka unohtaa kaiken
kun istunto loppuu. Muut työkalut ja tapojen kattavat osittain sen ongelman:

|Käytännön lähestymistapa|Mikä siitä on hyötyä|Mikä se ei kulje|
|---|---|---|
|Keskusteluhistoria / mallin muisti|Kätevä, nollavalmistelu|Istuntovaikutteinen ja myyjistä riippuvainen; ei tallenneta projektin mukana, joten kylmä agentti ei koskaan näe sitä|
|Staattinen`AGENTS.md`/ohje-tiedosto|Kestävät seisovaatimukset ja perinteet|Ei itse edusta elinympäristön tehtävän tilaa`next_action`, tai palautushistoriaa|
|Ongelma / TODO -seurantajärjestelmä|Tehtävä- ja takapitojenhallinta|Ei määritä itsestään agentin jatkotoiminnan semantiikkaa — mitä kylmä agentti on pakotettava lukemaan ja suorittamaan jatkoperässä|
| **SAIPEN** |Elävän suoritus tila, työjonos, tapahtumahistoria, kestävä tieto ja koneen tarkistettavat jatkotoimintasäännöt — tavallisissa tiedostoissa koodin vieressä|Ei mitään; tuo yhdistelmä on sopimus|

Ero ei ole yksittäisessä tiedostossa. Se on se, että SAIPEN tekee jatkoperässä vaiheen
koneen tarkistettavissa: kylmän agentin ensimmäinen toimenpide jälkeen`/saipen continue`on
määrätty tallennetusta`next_action`ja vahvistettu validoinnista, ei
muistista uudelleenrakennettu.

## Ingeniöörimaiset todisteet

SAIPEN yhdistää normatiivisen tavallistiedostosopimuksen suoritettavien, epäonnistumisohjelmoitujen kanssa
tarkistukset. Tietokanta osoittaa protokollan/tilinäkymäsuunnittelun, Python
työkalut, skeeman mukainen tila, palautumisjärjestelmän ajattelu, regressiotestaus,
monen agentin työkalujen rajat ja määrittelyä koskeva tarkkuus.

- **Suunniteltu sopimus.** [SPEC.md](SPEC.md)määrittelee tiedostotuki
jatko-kehitysmodelin ja vakauden levylle tallennetun sopimuksen;[CORE.md](saipen/CORE.md)
ja[MAINTENANCE.md](saipen/MAINTENANCE.md)omaavat nykyisen virallisen käytöksen.
- **Koneen tarkistettu tila.**stdlib-only canonical
  [validaattori](tools/validate.py)lukemaan live
  [tilan malleja](extensions/schemas/state.schema.json)ja tarkistaa vaihe
siirrot, lipun riippuvuudet, tapahtumien graafiset yhteydet, ristiriitaiset
asiakirjat, invariantit, mahdollisuudet ja palautumistila.
- **Virheen peittäminen.** [CONFORMANCE.md](saipen/CONFORMANCE.md)kartoittaa
vaatimuksia[skenaarioihin](tests/scenarios/); the
  [skenaario-ajaja](tools/run_scenarios.py)suorittaa rakenteellisia onnistumis-/epäonnistumistapauksia
mukaan lukien vioittuneen palautustilan, virheelliset siirtymät, riippuvuiskierrot ja
vainojen rajoitukset.
- **Regressiotarkistukset.** [audit_checks.py](tools/audit_checks.py)muuttaa
tunnetusti hyvät kopiot ja osoittaa, että validoinnin tarkistukset voivat silti epäonnistua, sen sijaan että
pitäisi pysyvän vihreän tarkistuksen todisteena.
- **Suoritettava kerros.** [saipen.py](tools/saipen.py)tallentaa journalisoidun tilan
toiminnot;[bootstrap/](bootstrap/)sisältää asennuksen, poistamisen ja vienti
apuohjelmat, valinnaisella[pre-commit -hookin asentaja](tools/install_hook.py).
- **Selkeät vaihtoehdot.**Perusprotokollan tila on tavallisia tiedostoja ilman suoritusajon
riippuvuutta. Kanoninen validointi ja CLI -työkalut vaativat Pythonin, mutta käyttävät vain
sen standardikirjastoa ja eivät tarvitse`pip`asennusta.

## Rakennetta

Kolme kerrosta, tiukasti yksisuuntaiset riippuvuudet:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Core ei riipu Maintenance:stä: autonomisen kehityksen poistamisella, SAIPEN
jää vielä täydelliseksi jatkuvaan protokollaksi — kylmä agentti jatkaa toimintaa.

- **Core tilansiirtymä** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Autonominen ylläpito**— laite pysäytetty(ei toimivaa`## TODO`,
ei mitään`## DOING`)ja ei`BLOCKED`? Automaattiset siirtymät`HUNT` (tarkista virheet)
  → `ADD` (kehitysominaisuudet) → `HUNT`, ei kysymyksiä. Istumisessa istuu
  `BLOCKED`ei automaattisesti etsi
  ([Hoidon § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Tavoite-tila** — `/saipen goal <objective>`kääntää laudan ja ajaa
tavoitteen eteenpäin VERIFY/REVIEW-kautta, jolloin se jää autonomiseen hoidon alle
kunnes täyttöehdot toteutuvat tai ajon määrä saavuttaa ylärajan(3 aaltoa / 20 lippua,
sitten tarkistuspisteet ja raportti) ([Hoidon § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Vahvistus**— sarjatulo analysoi tarkasti yksi kerrallaan lippuun
  (CORE § 1.8); likaisen puun jatko säilyttää vahvistamattoman työn(CORE § 1.5);
salaisuusmuotoiset arvot poistetaan lokista(`sk-***`) (CORE § 1.2).

## Yleisesti käytetyt komennot

Päivittäiset sisääntulopisteet; täydellinen nykyinen pinta on
[Core § 1.10](saipen/CORE.md#110-command-surface).

|Komento|Tee|
|---|---|
| `/saipen set` |Hyväksy projektia: Luo`.saipen/`tila|
| `/saipen continue` |Jatka tallennetusta projektin tilasta — ei uudelleenohjausta|
| `/saipen plan` |Muunna pyyntö tai alkuperäinen takapito tiketeiksi|
| `/saipen goal <text>` |Itseohjautuva aaltojen suoritus uudella tavoitteella|
| `/saipen validate` |Suorita sopivuus- tai yhteensopivuus tarkistukset|
| `/saipen status` |Vain lukemiseen: vaihe, tiketit, esteet, vanhentuminen|
| `/saipen stop` |Tallenna ja pysäytä|

<details>
<summary><b>More commands</b></summary>

|Komento|Tekee|
|---|---|
| `/saipen hunt` |Pakota virheen/parannuksen käsittely nyt|
| `/saipen markhunt` |Kuiva, rajaton tarkastus — tallentaa löydöt, ei korjaa mitään|
| `/saipen ship` |Julkaisuportit; vahvista, merkkaa ja lähetä, kun sallitaan|
| `/saipen clean` |Taulukon ja tilan puhdistus|
| `/saipen translate` |Erillinen käännösfactory|
| `/saipen prepare` / `/saipen collect` |Pakettityö siirtoon / integroi valmis paketti|
| `/saipen test` |Suorita ilmoitettu testikokoelma, raportoi vain|
| `/saipen crew` |Kiinteäjärjestyksinen tiimityökalu(hunta → toista → otto → rakenna → käännä → dokumentoi → lähetä) |
| `/saipen improve` |Metaohjauksen tarkastus protokollan parannuksista|
| `/saipen sub ...` |Luo/adoptoi vain luettavat alitiemit|

**Pakettisalasanoja.** `ee`/`qq`Valmista täydellinen käännös/wiki-paketti ilman
integroimista;`eee`/`qqq`Hyväksy vain valmiit paketit, sitten integroi, tarkista,
arvioi ja lähetä.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)kulkee koko
sisäänrakennettu joukko kiinteässä järjestyksessä — sensorit(saihunt, saitest, saipython, saiui),
tuottajat(saitranslate, saiwiki)ja Core ainoana pääpuun kirjoittajana —
kunnes toinen uusi kierros ei jää mitään todellista muutettavaksi. Se lisää täsmälleen yhden
omalla mekanismillaan: kestävä kohteen säätö(“execution_intent:
kohtaamaan` with `converge_target: crew`)joka tekee piirin jatketavaksi ja
häiriötilanteen aiheuttavaksi todisteista.`saipen crew --dry-run --json`johdattaa
piiriin vain lukemiseen;`bootstrap/saipen_crew.*`on VAIHTOEHTOINEN manuaalinen
monien ikkunoiden apuväline, ei koskaan mitä`saipen crew`tarkoittaa. Katso
[täysin](extensions/subs/crew.md).
</details>

## Mitä SAIPEN ei ole

- **LLM tai malli**— se on protokolla, jonka agentit seuraavat, ei älykkyyttä.
- **IDE tai sijoitettu muistitietokanta**— tila on tavallisia tiedostoja projektissasi;
ei mitään ole julkaisemassa.
- **Gitin korvaaja**— Git omistaa vielä versionhallinnan; tallenna
  `.saipen/`kuten muukin koodi.
- **Jakautunut konsenssi**— katso konkurrensin rajat alla.
- **Takuu siitä, että LLM tekee oikeita insinööriäisiä päätöksiä**— se
vähentää kontekstin menetystä ja käyttäytymisen poikkeamaa; se ei tehoa stokastisia agentteja
virheettömiin.

SAIPENin tehtävä on tila- ja tilapito- sopimus sekä validointi ja työkalut —
käyttäen seuraavalle agentille tarkistettua lähtökohtaa, ei taikaa.

**Konkurrensin rajat.**Journaloidut tilamuutokset(SAIOPS)käytä
projektin mukaisesti käytettävä OS lukko ja palautusjournali([OPS § 5](saipen/OPS.md#5-locks)).
Normaaliset projektimuutokset ja yhdistämättömät kirjoittajat ovat sen ulkopuolella. SAIPEN
ei ole jakautunut konsensuksen, joten yhdistämättömät kirjoittajat vaativat ulkoista
sopimusta([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ecosystem

|Projekt|Suhteellisuus SAIPENiin|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Paikallinen Windows -hallintakeskus SAIPEN -hankkeisiin — automaattisesti havaitsee`.saipen/`työtilat, visualisoi elävän tilan ja yhteensopivuuden arvioinnit, hallitsee lomakkeita ja käynnistää AI -CLI:t. Kompanion, ei virallinen taho.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Alapuolella oleva CodeNomad -haara, joka integroi SAIPEN: injektio`BOOT.md`/`STYLE.md`OpenCode -käynnistysten, paljastaa SAIPEN -pikavalikot ja hankkeen tilan näkymät, ja lisää pysyvän pyyntöjonojen.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Siirrettävä Windows -kynä ja snippet -hallinta, joka tunnistaa automaattisesti`.saipen/`kansiot ja lisää vainon tila/taulukko/loki -katselimen.|

## Dokumentaatio

|Dokumentti|Mitä se on|
|---|---|
| [SPEC.md](SPEC.md) |Virallinen arkkitehtuuri, suunnittelotavoitteet, litmus-testi|
| [CORE.md](saipen/CORE.md) |Virallinen jatko, tilansiirtymä ja komentosopimus|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Itsenäinen ylläpito ja Tavoitemoodi|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Suoritettavat/käyttäytymisvaatimukset ja validointisäännöt|
| [GUIDE.md](GUIDE.md) |Ihmisen ohjeistus|
| [RFC.md](saipen/RFC.md) |Soveltuvuus ohjaa jakautuneisiin virallisiksi dokumentteihin|
| [STYLE.md](saipen/STYLE.md) |Agentin viestintätyyli ja ääni|
| [UI.md](saipen/UI.md) |Klassinen kultaisten käyttöliittymäsuunnittelun ohjeet|
|Brochure|Esitteet —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Englanti](guides/GUIDE_EN.md) · 🇪🇪 [Vox](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Saksa](guides/GUIDE_DE.md) · 🇫🇷 [Ranska](guides/GUIDE_FR.md) · 🇪🇸 [Espanja](guides/GUIDE_ES.md) · 🇮🇹 [Italiano](guides/GUIDE_IT.md)

🇵🇹 [Portugali](guides/GUIDE_PT.md) · 🇳🇱 [Alankomaat](guides/GUIDE_NL.md) · 🇵🇱 [Puola](guides/GUIDE_PL.md) · 🇸🇪 [Ruotsi](guides/GUIDE_SV.md) · 🇩🇰 [Tanska](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norja](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Vietnamien kieli](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Turkki](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Indonesian](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Tšekki](guides/GUIDE_CS.md) · 🇷🇴 [Romania](guides/GUIDE_RO.md) · 🇭🇺 [Unkari](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenia](guides/GUIDE_SK.md) · 🇭🇷 [Kroatia](guides/GUIDE_HR.md)

</details>

## Asetusmuistiot

**Vastauskieli.**Agentti vastaa**eestineä**oletusarvoisesti — se on
asetus, ei protokollan vaatimus, ja ei mitään muuta SAIPEN:stä ole eestinen.
Protokolla, koodi, muutokset ja kaikki dokumentit pysyvät englanniksi jokaisella
arvolla. Muuta se yhdessä paikassa:`reply_language:`rivi yläpuolella
[`saipen/STYLE.md`](saipen/STYLE.md). `et`eestinä,`en`englanniksi,`ru`venäjäksi,
`auto`valitsee viestistä, jonka lähetit.

**Adaptoijat.**Platform not covered by the injector(DeepSeek, Qwen, standalone
OpenAI, etc.)? Per-platform notes live in`extensions/adapters/`.

## Screenshots

<details>
<summary><b>Click to expand</b></summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- translation-model: qwen3:14b contract:structured-markdown-v2 -->
<!-- source-digest: README.md sha256:bb47f7158db4a7a4fd99298427c1e4bc6859433c36435640e129cc6dad2a63b7 -->
