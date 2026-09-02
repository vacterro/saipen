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

**AI koodiagentide jätkumise protokoll.**Projekti mälestus asub lihtsas
Markdown failides projekti sees(`.saipen/`), seega iga ühilduv külma agent —
ei vaja vestluse ajalugu, ei vaja seansimälestust — saab tööd teha`/saipen continue`, lugeda
salvestatud`next_action`, ja jätkata tööd ilma, et kasutajalt peaks taas selgitama
midagi. Olek kuulub projektil, mitte ühe mudeli tootjate mälestusele.

**Üks käsk jätkamiseks. Lihtfaili olek. Masina kontrollitud lepingud.**

Repo valideerib ise iga pushiga; install, olek, kontrollid ja
eemaldamine on kohaline — ei ole ühtegi pilveteenust, ei daemoni, ei andmebaasi.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.238.3** | [Spetsifikatsioon](SPEC.md) | [Juhend](GUIDE.md) | [Tuumik](saipen/CORE.md) | [Hooldus](saipen/MAINTENANCE.md) | [Stiil](saipen/STYLE.md) | [Kasutajaliides](saipen/UI.md) | [Kohasus](saipen/CONFORMANCE.md) |MIT

**Kiirklahvid:** `cc` viib projekti konvergentsini (jätkab käimasolevat eesmärki, kui see on seatud), `sss` näitab olekut koodi puudutamata ja `ss` salvestab kontrollpunkti ning peatub. [Vaata täielikku 19 kiirklahvi kaarti](saipen/RFC.md#110-command-surface). Kirillitsa kaksikud töötavad ka: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## Mis jääb alles

Elus projektimälestus asub`.saipen/`— lihtsad failid, mida saab lugeda, erinevus ja
komiteerida koodi kõrval. Külma agent vastab viiele küsimusele failidest
üksinda:

|Fail / väli|Vastused|
|---|---|
| `STATE.md` |Mis juhtub praegu?(faasis, aktiivne pilet, töörežiim, takistaja) |
| `BOARD.md` |Millist tööd on olemas / milline on aktiivne?(pileti graaf: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |Miks projekt on jõudnud sellele seisundile?(ainult lisamiseks suunatud sündmuse graaf) |
| `KNOWLEDGE/` |Millised jätkusuvaldavad projektiga seotud faktilised andmed peavad säilma seansside vahel?|
| `next_action` (sisse`STATE.md`) |Milline täpsustatud toiming peab järgmise agenti tegelema?|

See on kontrollpunkti leping, mitte disaini soovitus:`saipen stop`ja iga
pileti üleminemisel kirjutage failid kindlas järjekorras ja tulemus kontrollitakse
validatori poolt. Midagi ei salvestata hosandatud andmebaasi ja midagi ei kadaku, kui
süsession lõpeb.

## Kiire alustus

**1. Install once per machine**— õpetab Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity ja igasugune`~/.agents/skills`loetja(FreeBuff jne.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`blokkimine agenti juhendisse
failid, mida sul juba on(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— kopeerimine igaühele`.bak`esimese —
ja kopeerib protokollide failid vastavate oskustega kataloogidesse. Midagi väljaspool neid
teed, ei deemoni, ei võrguühendusi.</sub>

**2. Alusta projektiga**— avage oma kataloogis agent, sisestage:

> `saipen set`

**Installimine?**Kleebige üks rida mõnele agentile:

> Lugeda&lt;kloon&gt;/saipen/BOOT.md esmalt(külma käivituse tuumik), seejärel&lt;kloon&gt;/saipen/INDEX.md +&lt;kloon&gt;/saipen/STYLE.md ja järgi neid.

**Muutid mõtet?**Üks käsk pannab selle tagasi:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

See eemaldab täpselt märgistatud bloki(jätmata ülejäänud faili muutmata), salvestab
a `.uninstalled.bak`teha kopeerimist enne ja eemaldab oskushoidlad.

## Miks mitte lihtsalt vestluse ajalugu?

SAIPEN sihitanud täpselt ühe ebaõnnestusega: AI koodimääratud agent, mis unustab kõike
kui seanss lõpeb. Teised tööriistad ja harjumused katta osa sellest probleemist:

|Viis|Mida see on hea|Mida see ei kanda|
|---|---|---|
|Kõne ajalugu / mudeli mälestus|Tõhus, nulli seadistus|Sessiooni- ja tarnija sõltuv; ei salvestata projektiga, seega külma agent ei näe seda|
|Statiline`AGENTS.md`/ juhendfail|Püsivad seadused ja traditsioonid|Ei ise esinda elulise ülesandetõhususe staat,`next_action`, või taastusajalugu|
|Probleem / TODO jälgija|Ülesannete ja tagamise jälgimine|Ei määrake ise agenti jätkumise semantikat — mis on külma agentil vajalik lugeda ja täita jätkamisel|
| **SAIPEN** |Eluline töökoormus, sündmuse ajalugu, kestlik teadus, masinvalvitud jätkumise reeglid — lihtsates failides koodi kõrval|Midagi; see kombinatsioon on leping|

Erinevus ei ole üksik fail. See on see, et SAIPEN teeb jätkamise samm
masinvalvitud: külma agenti esimene toiming pärast`/saipen continue`on
määratud salvestatud`next_action`ja kontrollitakse validatorega, mitte
mälestusest taastatud.

## Inženöri tõendid

SAIPEN paireb normatiivse lihtfaili protokolli tähtsusega, tähtsusega, vigaorienteeritud
kontrollid. Repo tegevusviis näitab protokolli/olekumasinade kujundamist, Python
tööriistad, skeemipõhine olek, taastusloogika, regressioonitestid,
mitmekohaline töövoogide piirid ja spetsifikatsiooni korraldus.

- **Kujundatud leping.** [SPEC.md](SPEC.md)määrab failipõhise
jätkumismodeli ja stabiilse kettale kantud lepingu;[CORE.md](saipen/CORE.md)
ja[MAINTENANCE.md](saipen/MAINTENANCE.md)omavad praegust normatiivset käitumist.
- **Masina kontrollitud olek.**stdlib-only kanoniline
  [kinnitaja](tools/validate.py)loeb sisse reaalajas
  [STATE skeem](extensions/schemas/state.schema.json)ja kontrollib faasi
üleminekuid, piletide sõltuvusi, sündmusegraafi lingisid, üle dokumendi
invariantide, võimaluste ja taastusoleku.
- **Vigastuskaal.** [CONFORMANCE.md](saipen/CONFORMANCE.md)kuvab
nõuetest[sündmuse fikseerimiste](tests/scenarios/); the
  [sценарий runner](tools/run_scenarios.py)tehakse struktuurilisi pass/fail testi
sealhulgas vigastatud taastamise staat, kehtetu üleminemised, sõltuvuse tsüklid ja
ainusloetav piirangud.
- **Regressioonikontrollid.** [audit_checks.py](tools/audit_checks.py)muudab
teadaolevate heade kopeerimised ja tõestab, et valideerija kontrollid saavad ikkagi olla punased, mitte
püsivalt rohelise kontrolli kui tõendust.
- **Käivitatav kiht.** [saipen.py](tools/saipen.py)annab journaliseeritud staat
tegevused;[bootstrap/](bootstrap/)hoiab paigalduse, eemalduse ja eksporti
abivahendid, valikuline[pre-commit hook installeerija](tools/install_hook.py).
- **Selged vahetused.**Põhiosakond protokolli staat on lihtsad failid ilma tööaja
sõltuvusega. Kanoniline kinnitamine ja CLI tööriistad nõuavad Pythoni, kuid kasutavad ainult
tema standardi kirjastusi ja ei vaja`pip`paigaldust.

## Arhitektuur

Kolm kihti, tugevalt ühesuunaline sõltuvus:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Core ei sõltu Maintenance-st: autonoomse evolutsiooni keelatud, SAIPEN
on ikkagi täielik jätkuval protokoll — külma agent jätkab ikkagi tööd.

- **Core state machine** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Autonoomne hooldus**— plaat peatatud(ei ole töödeldav`## TODO`,
midagi`## DOING`)ja mitte`BLOCKED`? Auto-transitsioonid`HUNT` (skänni vigadeid)
  → `ADD` (arendada funktsioone) → `HUNT`, ei küsi ühtegi küsimust. Seanss, mis istub
  `BLOCKED`ei auto-hunti
  ([Hooldus § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Sihtmoodus** — `/saipen goal <objective>`keeratab taeva ja juhivad
eesmärki edasi kaudu VERIFY/REVIEW, jäädes sõltumatu hoolduse alla
kuni lõpetamise reegel põleb või käigu jõuab oma kappe(3 laine / 20 piletit,
seejärel kontrollpunktid ja aruanded) ([Hooldus § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Tugevdamine**— pakkumise sisend parsitakse kirurgiliselt ükshaaval piletiteks
  (TUGI § 1.8); kõvakestuse jätkamine säilitab tehtud, kuid veel kinnitamata tööd(TUGI § 1.5);
salajastega sarnased väärtused on logidest eemaldatud(`sk-***`) (TUGI § 1.2).

## Tavalised käsklused

Päevapärase sisendi punktid; täna olev tervet pind asub
[TUGI § 1.10](saipen/CORE.md#110-command-surface).

|Käsk|Teostab|
|---|---|
| `/saipen set` |Projekti võtmine kasutusele: loo`.saipen/`olek|
| `/saipen continue` |Jäta järgi juba salvestatud projektistatusest — ei kordata koolitust|
| `/saipen plan` |Teisenda palve või algne tagasijuhendus ülesanneteks|
| `/saipen goal <text>` |Autonoomne lainevõrrand uue eesmärgi suhtes|
| `/saipen validate` |Käivita vastuvõtuvõimluse kontrollid|
| `/saipen status` |Vaidlusviisne aruanne: faas, ülesanded, takistused, vananemine|
| `/saipen stop` |Kontrollpunkti ja peatus|

<details>
<summary><b>More commands</b></summary>

|Käsk|Tegevus|
|---|---|
| `/saipen hunt` |Võta kohe vastu puuduse/paranduse üle kontrolli|
| `/saipen markhunt` |Kuiv, piiratud audit — kirjeldab leidmisvõtteid, ei tegele parandustega|
| `/saipen ship` |Väljastusväravad; kui lubatud, siis kinnita, märgista ja pushi|
| `/saipen clean` |Tahvel ja staatuse puhastus|
| `/saipen translate` |Isolatsioonifaktorisatsioon|
| `/saipen prepare` / `/saipen collect` |Paketi töö üleandmiseks/integreerimiseks valmis paketi|
| `/saipen test` |Käivita deklareeritud testide komplekt, aruanne ainult|
| `/saipen crew` |Fikseeritud järjekorra meeskondliku tõrge(hunted → kordamine → võtmine → ehitus → tõlge → dokumentatsioon → saada) |
| `/saipen improve` |Metajuhtimise audit protokolli paranduste kohta|
| `/saipen sub ...` |Loo/otse käsitsi loomata ainult loetavalt alamagentide|

**Paketi võtmed.** `ee`/`qq`Valmistage täielik tõlge/wiki paketid ilma
integreerimine;`eee`/`qqq`Võta vastu ainult valmis paketid, seejärel integreeri, kontrolli,
kinnita ja pushi.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)käivitab tervet
sisseehitatud meeskonda kindlas järjekorras — sensorid(saihunt, saitest, saipython, saiui),
tootjad(saitranslate, saiwiki)ja Core ainuke peapuu kirjutaja —
kuni teine täielik läbikäigu ei jää midagi tõelist muuta. See lisab täpselt ühe
mehhanismi oma enda jaoks: kestliku orkestratsiooni sihtriigi(``execution_intent:
koondu` with `converge_target: crew`)mis teeb sirkliit võimaliku taastamiseks ja
tõestuslikest andmetest tuletatavalt kriisist.`saipen crew --dry-run --json`tuletab
sirkliidi ainult loetavaks;`bootstrap/saipen_crew.*`on VALIKULINE käsitsi
mitmeaknane abivahend, mitte mis`saipen crew`tähendab. Vaata
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Mis SAIPEN ei ole

- **LLM või mudel**— see on protokoll, mida agentid järgivad, mitte tarkus.
- **IDE või kohandatud mälubaasi**— staat on lihtsad failid oma projektis;
midagi ei ole hostitud.
- **Git asendaja**— Git hoiab endiselt kontrolli versioonihistoriga; salvesta oma
  `.saipen/`nagu iga teine kood.
- **Distribueeritud konsensus**— vaata konkurentsirajooni allpool.
- **Tagasiside, et LLM teeb õigused tehnilised otsused**— see
vähendab konteksti kaotust ja käitumiskõrvalekalle; see ei tee stohhastilisi agente
viga vaba.

SAIPENi ülesanne on jätkusuutlikkus/olekukohustus plus valideerimine ja tööriistad —
käesolev agentile andes masinvaldusega alguspunkti, mitte magia.

**Konkurentsipiir.**Journalitud staatilised muudatused(SAIOPS)kasuta
projektiga seotud OS lukku ja taastusjournali([OPS § 5](saipen/OPS.md#5-locks)).
Tavalised projektimuudatused ja ühendamata kirjutajad asuvad selle lukku väljas. SAIPEN
ei ole jaotatud konsensust, seega ühendamata kirjutajad nõuavad välist
koordineerimist([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ekosüsteem

|Projekt|Suhe SAIPENiga|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Kohalik Windowsi juhtpaneel SAIPENi projektidele — avastab automaatselt`.saipen/`tööruume, visualiseerib reaalajas olukorda ja vastavusmärge, haldab pakkumisi ja käivitab AI CLI-sid. Kohane, mitte autoriteet.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Allpool olev CodeNomad-i viisakas haru, mis integreerib SAIPENi: sisestab`BOOT.md`/`STYLE.md`avalehtedele, avaldab SAIPENi otseteed ja projekt-olukorra vaateid ning lisab jätkuva pakkumise järjekorra.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Kanditav Windowsi klahv- ja lõigetehaldur, mis avastab automaatselt`.saipen/`katalooge ja lisab loetamatu STATE/BOARD/LOG vaateid.|

## Dokumentatsioon

|Dokument|Mis see on|
|---|---|
| [SPEC.md](SPEC.md) |Formaalne arhitektuur, disaini eesmärgid, litmus testimine|
| [CORE.md](saipen/CORE.md) |Normatiivne jätk, olekumachine ja käskude leping|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Autonoomne hooldus ja Eesmärkimoode|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Võimaldavad/tegevuslikud nõuded ja valideerimise reeglid|
| [GUIDE.md](GUIDE.md) |Inimene juhend|
| [RFC.md](saipen/RFC.md) |Kohandamine suunatud jagatud normatiivsete dokumentidele|
| [STYLE.md](saipen/STYLE.md) |Agenti kommunikatsioonistüli ja hääl|
| [UI.md](saipen/UI.md) |Vana kuldne UI disaini juhendid|
|Kaat|Esitluskaat —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Inglise](guides/GUIDE_EN.md) · 🇪🇪 [Eesti](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Saksa](guides/GUIDE_DE.md) · 🇫🇷 [Prantsuse](guides/GUIDE_FR.md) · 🇪🇸 [Hispaania](guides/GUIDE_ES.md) · 🇮🇹 [Itaalia](guides/GUIDE_IT.md)

🇵🇹 [Portugali](guides/GUIDE_PT.md) · 🇳🇱 [Hollandi](guides/GUIDE_NL.md) · 🇵🇱 [Poola](guides/GUIDE_PL.md) · 🇸🇪 [Soome](guides/GUIDE_SV.md) · 🇩🇰 [Tšehhi](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Konfiguratsiooni märkmed

**Vastuse keel.**Agent vastab**eesti keeles**vaikimisi — see on
seadistus, mitte protokolli nõue, ja midagi muud SAIPENist ei ole eesti keeles.
Protokoll, kood, commit-id ja iga dokumendid jäävad inglise keeleks iga
väärtuse korral. Muuda seda ühes kohas:`reply_language:`readme faili
[`saipen/STYLE.md`](saipen/STYLE.md). `et`eesti keeles,`en`inglise keeles,`ru`vene keeles,
`auto`valib sõnumist, mida sa silti saatsid.

**Adapterid.**Platformi ei kaeta injektoriga(DeepSeek, Qwen, standalone
OpenAI jne.)? Platformispetsiifilised märkused asuvad`extensions/adapters/`.

## Pildid

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
