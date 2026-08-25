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

**Folytatási protokoll AI kódoló ügynökökhez.**A projekt memóriája a sima
Markdown fájlokban található a projektben(`.saipen/`), így bármely kompatibilis hideg ügynök —
nincs chat történet, nincs munkamenet memória — futtatható`/saipen continue`, olvashatja a
tárolt`next_action`, és folytathatja a munkát anélkül, hogy a felhasználónak újra elmagyarázná
valamit. A állapot a projekté, nem egy modell gyártó memóriájáé.

**Egy parancs a folytatáshoz. Sima fájl állapot. Gépellenőrzött szerződéseket.**

A tárhely minden push esetén ellenőrzi magát; telepítés, állapot, ellenőrzések, és
A telepítés eltávolítása mind helyi – nincs felhőszolgáltatás, nincs démon, nincs adatbázis.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.230.0** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [Core](saipen/CORE.md) | [Maintenance](saipen/MAINTENANCE.md) | [Stílus](saipen/STYLE.md) | [UI](saipen/UI.md) | [Konformancia](saipen/CONFORMANCE.md) |MIT

**Gyorsbillentyűk:** a `cc` a projekt kontextusát konvergenciáig folytatja (folytat egy futó célt, ha be van állítva), az `sss` kód érintése nélkül jelzi az állapotot, az `ss` pedig menti az ellenőrzőpontot és megáll. [Lásd a teljes 19 billentyűs térképet](saipen/RFC.md#110-command-surface). A cirill ikrek is működnek: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## Mi marad meg

Élő projekt memóriája él a`.saipen/`— egyszerű fájlok, amelyeket olvashatsz, diff-ölhetsz és
következő commit a kód mellé. Egy hideg ügynök válaszol öt kérdésre a fájlok alapján
egyedül:

|Fájl / mező|Válaszok|
|---|---|
| `STATE.md` |Mi történik éppen?(fázis, aktív jegy, működési mód, akadály) |
| `BOARD.md` |Mi a jelenlegi munka / mi aktív?(jegy grafikon: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |Miért érkezett el a projekt ez állapotba?(csak hozzáadásos eseménygrafikon) |
| `KNOWLEDGE/` |Milyen tartós projektinformációk maradnak fenn munkamenetek között?|
| `next_action` (benne`STATE.md`) |Mi az, amit a következő ügynök pontosan végrehajtson?|

Ez egy ellenőrző szerződés, nem egy tervezési javaslat:`saipen stop`és minden
jegyátmenet fájlokat írjon megadott sorrendben, és az eredményt ellenőrzi
egy validátor. Nincs tárolva a hosztolt adatbázisban, és semmi nem veszett el, amikor egy
a munkamenet véget ér.

## Gyors kezdés

**1. Telepítse egyszer gépenként**— oktatja a Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity, és bármely általános`~/.agents/skills`olvasó(FreeBuff, stb.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`blokkot az ügynök utasításába
már meglévő fájlokat(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— mindegyiket biztonságba helyezi`.bak`először —
és másolja a protokollt a megfelelő készség mappákba. Semmi sem kerül ki ezekből
útvonalak, nincs démon, nincs hálózati hívások.</sub>

**2. Indíts egy projektet**— nyisd meg egy ügynököt a mappádban, írd be:

> `saipen set`

**Nincs telepítés?**Másold be egy sorozatot bármely ügynöködbe:

> Olvasd el&lt;klónozd&gt;/saipen/BOOT.md elsőnek(hideg indítási mag), majd&lt;klónozd&gt;/saipen/INDEX.md +&lt;klón&gt;/saipen/STYLE.md és kövessék őket.

**Változtál döntéseden?**Egy parancs visszahelyezi:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Ez pontosan a megjelölt blokkot eltávolítja(miközben a fájl többi részét érintetlenül hagyja), mentés
a `.uninstalled.bak`másolat először, és eltávolítja a készség mappáit.

## Miért nem csak a beszélgetés történetét?

A SAIPEN egy adott problémára koncentrál: egy AI kódoló ügynök, amely semmit nem emlékszik
egyszer a munkamenet véget ér. Más eszközök és szokások részben megoldják ezt a problémát:

|Megközelítés|Miért hasznos|Mi nem tartalmazza|
|---|---|---|
|Beszélgetési előzmény / modell memóriája|Kényelmes, nulla beállítás|Munkamenet- és szolgáltatófüggő; nem tárolja a projekttel, így a hideg ügynök sosem látja|
|Statikus`AGENTS.md`/ utasításfájl|Tartós álláspontok és konvenciók|Magában nem képviseli a valós feladatállapotot`next_action`, vagy a visszaállítási előzményt|
|Probléma / TODO nyilvántartó|Feladat- és visszamaradt feladatkezelés|Nem határozza meg magában az ügynök folytatásának szemantikáját — mit kell egy hűvös ügynöknek olvasnia és végrehajtania a folytatáskor|
| **SAIPEN** |Élő végrehajtási állapot, munka sor, eseménynapló, tartós tudás és gépellenőrzött folytatási szabályok — egyszerű fájlokban a kód mellett|Semmi; ez a kombináció a szerződés|

A különbség nem egyetlen fájlban van. Az, hogy a SAIPEN végrehajtja a folytatási lépést
gépellenőrzött: egy hűvös ügynök első lépése utána`/saipen continue`az
által meghatározott`next_action`és egy ellenőrzővel ellenőrizve, nem
memóriából újraépítve.

## Mérnöki bizonyíték

A SAIPEN egy szabványos egyszerű fájlprotokollt párosít egy végrehajtható, hibára optimalizálttal
ellenőrzések. A tárhely bemutatja a protokoll/állapotgép tervezést, Python
eszköztár, sémák alapú állapot, visszanyerési logika, regressziós tesztelés,
többügynélküli munkafolyamat határok, és specifikációs diszciplína.

- **Kialakított szerződés.** [SPEC.md](SPEC.md)meghatározza a fájlal tárolt
folytatási modellt és a stabil lemezre írt szerződést;[CORE.md](saipen/CORE.md)
és[MAINTENANCE.md](saipen/MAINTENANCE.md)saját jelenlegi normatív viselkedést.
- **Gépellenőrzött állapot.**A stdlib-only kanonikus
  [validátor](tools/validate.py)olvasza a live
  [ÁLLAPOT sémáját](extensions/schemas/state.schema.json)és ellenőrzi a fázis
átmeneteket, jegy függőségeket, eseménypontok kapcsolatait, dokumentumok közötti
invariánsokat, képességeket és visszanyitási állapotot.
- **Hibakiterjesztés.** [CONFORMANCE.md](saipen/CONFORMANCE.md)térképezi
követelményeket a[szcenárió alapértelmezett beállításokhoz](tests/scenarios/); a
  [szcenárió futtató](tools/run_scenarios.py)végrehajtja a szerkezeti átmenet/hibás eseteket
beleértve a meghibásodott visszaállítási állapotot, érvénytelen átmeneteket, függőségi kört, és
csak olvasható korlátozásokat.
- **Regressziós ellenőrzések.** [audit_checks.py](tools/audit_checks.py)módosítja
ismert jó másolatokat, és bizonyítja, hogy a validátor ellenőrzései még mindig vörösek lehetnek, és nem
kezeli a mindig zöld ellenőrzést bizonyítékként.
- **Végrehajtható réteg.** [saipen.py](tools/saipen.py)naplózott állapotot biztosít
műveletek;[bootstrap/](bootstrap/)telepítést, eltávolítást és exportálást tartalmaz
segédeszközöket, amelyekhez választhatóan[pre-commit hook telepítő](tools/install_hook.py).
- **Explicit tradeoffs.**A magyar protokollállapot egyszerű fájlok, amelyeknek nincs futásiidőben való függősége.
Kanonikus érvényesség és CLI eszközök Python-t igényelnek, de csak
a standard könyvtárat használják, és nem igényelnek`pip`telepítést.

## Architektúra

Három réteg, szigorúan egyirányú függőségek:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

A Core nem függ a Maintenance-től: az autonóm fejlődés letiltása esetén, SAIPEN
még mindig teljes folytatási protokoll — a hideg ügynök továbbra is folytatja.

- **Core állapotgép** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Autonóm karbantartás**— lemez leállítva(semmit nem működőképes a`## TODO`,
semmi a`## DOING`)és nem`BLOCKED`? Automatikus átmenetek`HUNT` (hibák keresése)
  → `ADD` (funkciók fejlődése) → `HUNT`, nulla kérdés felteve. Egy munkamenet ülve
  `BLOCKED`soha nem indul automatikusan a vadászat
  ([Karbantartás § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Cél mód** — `/saipen goal <objective>`elfordítja a táblát, és futtatja a
célt előre a VERIFY/REVIEW-en keresztül, önálló karbantartásba esve
amíg a teljesítési szabály nem aktiválódik, vagy a futtatás el nem éri a korlátját(3 hullám / 20 jegy,
majd ellenőrzőpontokat és jelentést ad) ([Karbantartás § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Erősítés**— a csomagos bemenetet műtéti módon egyesével jegyekre bontják
  (CORE § 1.8); a szennyezett fa folytatása megőrzi a meg nem commitolt munkát(CORE § 1.5);
titokhoz hasonló értékek kihagyása a naplókból(`sk-***`) (CORE § 1.2).

## Általános parancsok

Naponta használt bejárati pontok; a teljes aktuális felület itt található
[Core § 1.10](saipen/CORE.md#110-command-surface).

|Parancs|Tesztiel|
|---|---|
| `/saipen set` |Projekt elfogadása: létrehozás`.saipen/`Állapot|
| `/saipen continue` |Folytassa a megtartott projektállapotból — újra nem kell bemutatni|
| `/saipen plan` |Átalakít egy kérés vagy nyers backlogot jegyekké|
| `/saipen goal <text>` |Autonóm hullám végrehajtása új cél szerint|
| `/saipen validate` |Futtassa a megfelelőségi ellenőrzéseket|
| `/saipen status` |Csak olvasható jelentés: fázis, jegyek, akadályok, elavulás|
| `/saipen stop` |Mentés és megállítás|

<details>
<summary><b>More commands</b></summary>

|Parancs|Tesztkör|
|---|---|
| `/saipen hunt` |Erőszakos hibakezelés/fejlesztési javítás most|
| `/saipen markhunt` |Száraz, korlátlan ellenőrzés — feljegyzi a találatokat, de semmit nem javít|
| `/saipen ship` |Felszabadítási kapuk; engedélyezés után commit, tag és push|
| `/saipen clean` |Tábla és állapot tisztítása|
| `/saipen translate` |Elválasztott fordítási gyára|
| `/saipen prepare` / `/saipen collect` |Csomagolás a továbbításhoz / integrálás kész csomaggal|
| `/saipen test` |Futtassa a deklarált tesztkészletet, csak jelentést adja|
| `/saipen crew` |Rögzített sorrendű csapatkör(vadászás → reprodukció → bevitel → építés → fordítás → dokumentáció → kiszállítás) |
| `/saipen improve` |Meta-vezérlési ellenőrzés a protokolljavításokra|
| `/saipen sub ...` |Létrehozás/adoptálás olvasó-only alárendelt ügynökök|

**Csomagkulcsok.** `ee`/`qq`Elkészít egy teljes fordítási/wiki csomagot anélkül, hogy
integrálná;`eee`/`qqq`csak kész csomagokat fogad el, majd integrálja, ellenőrzi,
felülvizsgálja, és elküldi.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)megjelenik az egész
beépített csapat fix sorrendben — érzékelők(saihunt, saitest, saipython, saiui),
termelők(saitranslate, saiwiki)és a Core mint a főfájlon lévő egyetlen író —
amíg egy új frissítés nem hagyja, hogy valóban változtasson. Pontosan egyet
saját mechanizmusát adja hozzá: a tartós szervezési cél(„execution_intent:
konvergál` with `konvergálási cél: csapat`)amely újraindíthatóvá teszi a köröket és
kivonható a bizonyítékokból.`saipen crew --dry-run --json`kivonja a
kör olvasáskor írhatatlan;`bootstrap/saipen_crew.*`egy KÖTELEZETTEN manuális
többablakos segédprogram, soha nem azt`saipen crew`jelenti. Lásd
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Mi az, amit a SAIPEN nem jelent

- **Egy LLM vagy egy modell**— ez egy protokoll, amelyet az ügynökök követnek, nem egy intelligencia.
- **Egy IDE vagy egy tárolt memória adatbázis**— az állapot egyszerű fájlok a projektben;
semmi nem kerül tárolásra.
- **Git helyettesítője**— a Git továbbra is birtokolja a verziókövetést; commitold
  `.saipen/`mint bármely más kód.
- **Elosztott konszenzus**— lásd az alábbi konkurrensiával határolt területet.
- **Egy garancia arra, hogy egy LLM megfelelő mérnöki döntéseket hoz**— ez
csökkenti a kontextusveszteséget és a viselkedési eltérést; nem teszi a sztochasztikus ügynököket
hibátlanokká.

SAIPEN feladata a folytatás/állapot szerződés, valamint a validáció és a eszközök —
egy gép által ellenőrzött kezdőpontot adni a következő ügynöknek, nem varázslatot.

**Konkurenciakorlát.**naplózott állapotváltozások(SAIOPS)használj egy
projekt-hatókörű operációs rendszer zárat és egy visszaállítási naplót([OPS § 5](saipen/OPS.md#5-locks)).
A normál projekt szerkesztések és a leválasztott írók ezen a záron kívül vannak. SAIPEN
nem elosztott konszenzus, ezért a leválasztott írók külső
koordinációt([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Egyéni rendszer

|Projekt|Kapcsolat a SAIPEN-rel|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Helyi Windows irányítóközpont SAIPEN projektekhez — automatikusan felfedezi`.saipen/`munkaterületeket, megjeleníti az élő állapotot és konformitási ítéleteket, kezeli a jegyeket, és indítja az AI CLIK-t. Társ, nem az ellenőrző hatóság.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Lefelé irányuló CodeNomad ágazat, amely integrálja a SAIPEN-t: beilleszti`BOOT.md`/`STYLE.md`az OpenCode indításokba, kitéve a SAIPEN rövidítéseket és projektállapot nézeteket, valamint hozzáad egy tartós prompt sorrendet.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Hordozható Windows jegyzetfüzete és kivágáskezelő, amely automatikusan észleli`.saipen/`mappákat, és hozzáad egy csak olvasható STATE/BOARD/LOG nézőt.|

## Dokumentáció

|Dokumentum|Mi az?|
|---|---|
| [SPEC.md](SPEC.md) |Formális architektúra, tervezési célok, litmus teszt|
| [CORE.md](saipen/CORE.md) |Normatív folytatás, állapotgép és parancs szerződés|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Autonóm karbantartás és Cél Mód|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Végrehajtható/viselkedési követelmények és validátor szabályok|
| [GUIDE.md](GUIDE.md) |Emberi oktatóanyag|
| [RFC.md](saipen/RFC.md) |Kompatibilitás átirányítás a különálló szabványos dokumentumokra|
| [STYLE.md](saipen/STYLE.md) |Ügynök kommunikációs stílusa és hangneme|
| [UI.md](saipen/UI.md) |Régi arany UI tervezési útmutatók|
|Brochure|Prezentációs brosúra —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Angol](guides/GUIDE_EN.md) · 🇪🇪 [Észt](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Német](guides/GUIDE_DE.md) · 🇫🇷 [Francia](guides/GUIDE_FR.md) · 🇪🇸 [Spanyol](guides/GUIDE_ES.md) · 🇮🇹 [Olasz](guides/GUIDE_IT.md)

🇵🇹 [Portugál](guides/GUIDE_PT.md) · 🇳🇱 [Holland](guides/GUIDE_NL.md) · 🇵🇱 [Lengyel](guides/GUIDE_PL.md) · 🇸🇪 [Svéd](guides/GUIDE_SV.md) · 🇩🇰 [Dán](guides/GUIDE_DA.md)

🇫🇮 [Finlandi](guides/GUIDE_FI.md) · 🇳🇴 [Norvég](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Vietnámi](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Orosz](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Indonéz](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Cseh](guides/GUIDE_CS.md) · 🇷🇴 [Román](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Szlovák](guides/GUIDE_SK.md) · 🇭🇷 [Horvát](guides/GUIDE_HR.md)

</details>

## Konfigurációs megjegyzések

**Válasz nyelve.**Az ügynök alapértelmezés szerint**estoni**nyelven válaszol — ez egy
beállítás, nem pedig protokollkövetelmény, és semmi más a SAIPEN-nél nem estoni.
A protokoll, a kód, a commitok és minden dokumentum minden
értéken angol marad.`reply_language:`Változtassa meg egy helyen: a
[`saipen/STYLE.md`](saipen/STYLE.md). `et`sor a tetején`en`estoni,`ru`angol,
`auto`orosz,

**kiválasztja az Ön által elküldött üzenetből.**A platform nem tartozik az injektor hatókörébe(DeepSeek, Qwen, önálló
OpenAI stb.)? Platform-specifikus megjegyzések itt találhatók`extensions/adapters/`.

## Képernyőképek

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
