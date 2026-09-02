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

**Pokračovacie protokoly pre AI kódovacie agenti.**Pamäť projektu žije v bežnom
Markdown súboroch vo vnútri projektu(`.saipen/`), takže akýkoľvek kompatibilný chladný agent —
bez histórie chatu, bez pamäte relácie — môže bežať`/saipen continue`, čítať
uložené`next_action`, a pokračovať v práci bez toho, aby sa používateľ musel znova vysvetľovať
niečo. Stav patrí projektu, nie pamäti jedného výrobcu modelu.

**Jedna komanda na obnovenie. Stav v bežných súboroch. Kontrakty kontrolované strojom.**

Repositár sa overuje sám pri každom push; inštalácia, stav, kontroly a
odinštalácia sú všetky lokálne — žiadna clúdová služba, žiadny démon, žiadna databáza.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.241.1** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [Core](saipen/CORE.md) | [Maintenance](saipen/MAINTENANCE.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) |MIT

**Rýchle klávesy:** `cc` pokračuje v konvergencii projektového kontextu (obnoví bežiaci cieľ, ak je nastavený), `sss` zobrazí stav bez dotyku kódu a `ss` uloží kontrolný bod a zastaví. [Pozri si úplnú mapu 19 kláves](saipen/RFC.md#110-command-surface). Fungujú aj cyrilské dvojníky: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## Čo pretrváva

Živá pamäť projektu žije v`.saipen/`— bežné súbory, ktoré môžete čítať, rozdielovať a
commitovať vedľa kódu. Chladný agent odpovedá na päť otázok z súborov
sám:

|Súbor / pole|Odpovede|
|---|---|
| `STATE.md` |Čo sa práve deje?(fáza, aktívny lístok, režim prevádzky, blokátor) |
| `BOARD.md` |Aká práca existuje / aká je aktívna?(graf lístkov: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |Prečo sa projekt dostal do tohto stavu?(pridávajúci sa graf udalostí) |
| `KNOWLEDGE/` |Aké trvalé fakty projektu musia prežiť relácie?|
| `next_action` (v`STATE.md`) |Aká presná akcia by mala vykonávať nasledujúci agent?|

Toto je zmluva o kontrolnom bode, nie odporúčanie návrhu:`saipen stop`a každý
prechod lístka zapíšte súbory v pevnom poradí a výsledok overí
validátor. Nič sa ukladá do hostovaného databázového systému a nič sa neztráca keď
relácia sa ukončí.

## Rýchly štart

**1. Nainštalujte raz na každý stroj**— vyučuje Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity a akýkoľvek obecný`~/.agents/skills`čitateľ(FreeBuff atď.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`blok do inštrukcie agenta
súbory, ktoré už máte(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— ich zálohovanie do`.bak`najskôr —
a kopíruje protokol do zodpovedajúcich zložiek dovedností. Nič mimo týchto
cesty, žiadny démon, žiadne sieťové volania.</sub>

**2. Začnite projekt**— otvorte agenta vo svojom zložku, napíšte:

> `saipen set`

**Žiadna inštalácia?**Vložte jednu riadok do akéhokoľvek agenta:

> Prečítajte si&lt;clone&gt;/saipen/BOOT.md najskôr(chladný štart jadro), potom&lt;clone&gt;/saipen/INDEX.md +&lt;kópiu&gt;/saipen/STYLE.md a dodržiavajte ich.

**Zmenil si názor?**Jedna príkaz všetko vráti späť:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Odstráni presne označený blok(necháva zvyšok súboru nedotknutý), uloží
a `.uninstalled.bak`skopíruj najprv a odstráň priečinky s výkonnosťami.

## Prečo by ste nemohli len chatovú históriu?

SAIPEN sa sústredzuje na konkrétny zlyhávajúci prípad: AI kódovací agent, ktorý si nič nepamätá
po ukončení relácie. Iné nástroje a zvyky pokryjú časť tohto problému:

|Prístup|Na čo je dobré|Čo neobsahuje|
|---|---|---|
|História chatu / pamäť modelu|Pohodlné, žiadne nastavenie|Závislé od relácie a poskytovateľa; nie je uložené s projektom, takže chladný agent ho nikdy nevidí|
|Stále`AGENTS.md`súbor / inštrukcie|Trvalé stojace pravidlá a konvencie|Sám o sebe nezastupuje živý stav úlohy`next_action`, alebo históriu obnovy|
|Sledovanie problémov / TODO|Správa úloh a zásobníka|Sám o sebe nevytvára sémantiku pokračovania agenta — čo musí chladný agent prečítať a vykonať pri obnovení|
| **SAIPEN** |Živý stav vykonávania, pracovný zoznam, história udalostí, trvalé poznanie a pravidlá pokračovania overené strojom — v bežných súboroch vedľa kódu|Nič; toto kombinácie je zmluva|

Rozdiel nie je v žiadnom jednom súbore. Je to v tom, že SAIPEN robí krok obnovenia
overiteľné strojom: prvá akcia chladného agenta po`/saipen continue`je
určená trvalým`next_action`a overená overovačom, nie
rekonštrukovaná z pamäte.

## Inžinierske dôkazy

SAIPEN kombinuje normatívny bežný súborový protokol s vykonateľným, orientovaným na chyby
kontroly. Repozitár demonštruje návrh protokolu/stavového stroja, Python
nástroje, špecifikácia stavu, odôvodnenie obnovy, regresné testovanie,
hranice pracovných tokov pre viacagentné prostredie a disciplína špecifikácií.

- **Navrhnutý zmluvný dokument.** [SPEC.md](SPEC.md)definuje súborové podporované
model pokračovania a stabilnú zmluvu na disku;[CORE.md](saipen/CORE.md)
a[MAINTENANCE.md](saipen/MAINTENANCE.md)majú aktuálne normatívne správanie.
- **Stav overený strojom.**Stdlib-only kanonický
  [ověřovatel](tools/validate.py)čte živý
  [STAV šablony](extensions/schemas/state.schema.json)a kontroluje fázu
prestupov, závislosti vstupen, odkazy grafu událostí, mezi-dokument
invarianty, možnosti a stav obnovy.
- **Pokrytie chýb.** [CONFORMANCE.md](saipen/CONFORMANCE.md)mapuje
požiadavky na[scénárové zariadenia](tests/scenarios/); the
  [spustiteľný scenár](tools/run_scenarios.py)vykonáva štrukturálne prípady pre schválenie/neschválenie
vrátane poškodeného stavu obnovy, neplatných prechodov, závislostí v cykloch a
čítacieho len obmedzenia.
- **Kontroly regresie.** [audit_checks.py](tools/audit_checks.py)upravuje
známe dobré kópie a dokazuje, že kontroly overovateľa stále môžu byť červené, namiesto toho
aby trvalo zelená kontrola bola dôkazom.
- **Spustiteľná vrstva.** [saipen.py](tools/saipen.py)poskytuje journaled stav
operácie;[bootstrap/](bootstrap/)udržiava inštaláciu, odinštaláciu a export
pomocníci so voliteľným[inštalátorom pre-commit hooku](tools/install_hook.py).
- **Explicitné kompromisy.**Stav jadrového protokolu sú bežné súbory bez behúceho prostredia
závislosti. Kanonická validácia a nástroje pre príkazový riadok vyžadujú Python, ale používajú len
jeho štandardnú knižnicu a nevyžadujú žiadne`pip`inštalácie.

## Architektúra

Tri vrstvy, striktne jednostranné závislosti:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Jadro nezávisí na údržbe: so vypnutou samostatnou evolúciou, SAIPEN
stále je úplným pokračovaním protokolu — chladný agent stále pokračuje.

- **Stavová mašina jadra** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Samostatná údržba**— dosaďte zastavený(nič funkčné v`## TODO`,
nič v`## DOING`)a nie`BLOCKED`? Auto-prechod`HUNT` (skenovanie chýb)
  → `ADD` (rozvoj funkcií) → `HUNT`, žiadne otázky položené. Session sedí na
  `BLOCKED`nikdy sa automaticky nevyhľadáva
  ([Údržba § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Režim cieľa** — `/saipen goal <objective>`otočí dosku a spustí
cieľ dopredu cez VERIFY/REVIEW, kde sa dostane do samostatnej údržby
až do momentu, keď sa spustí pravidlo dokončenia alebo sa dosiahne limit behu(3 vlny / 20 lístkov,
potom kontrolné body a správy) ([Údržba § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Zosilnenie**— dáta v batche sa analyzujú na jednotlivé lístky
  (JÁDRO § 1.8); pokračovanie znečisteného stromu zachováva nevykonanú prácu(JÁDRO § 1.5);
hodnoty podobné tajomstvám sú v logoch vynechané(`sk-***`) (JÁDRO § 1.2).

## Bežné príkazy

Bežné vstupy; celá súčasná povrchová úroveň sa nachádza v
[JÁDRO § 1.10](saipen/CORE.md#110-command-surface).

|Príkaz|Robí|
|---|---|
| `/saipen set` |Prijmúť projekt: vytvoriť`.saipen/`stav|
| `/saipen continue` |Obnoviť z uchovanej stavu projektu — žiadne opätovné informovanie|
| `/saipen plan` |Prepojiť žiadosť alebo hrubý zoznam úloh na tikety|
| `/saipen goal <text>` |Autonomné vykonávanie vlny proti novému cieľu|
| `/saipen validate` |Spustiť kontroly zhodnosti|
| `/saipen status` |Povolený záznam: fáza, tikety, blokátory, starosť|
| `/saipen stop` |Checkpoint a zastavenie|

<details>
<summary><b>More commands</b></summary>

|Príkaz|Robí|
|---|---|
| `/saipen hunt` |Vyhnite sa skenovaniu chýb/lepšením teraz|
| `/saipen markhunt` |Sušiaca, neobmedzená auditácia — zaznamenáva nálezy, neopravuje nič|
| `/saipen ship` |Čiary pre uvoľnenie; commit, tag a push, keď je povolené|
| `/saipen clean` |Tabuľa a čistenie stavu|
| `/saipen translate` |Izolovaná prekladačka|
| `/saipen prepare` / `/saipen collect` |Práca s balíčkami na prenos / integrovať pripravený balíček|
| `/saipen test` |Spustiť deklarovaný súbor testov, hlásiť len|
| `/saipen crew` |Cirkuľ posádky v pevnom poradí(hľadať → reprodukovať → prijímať → zostaviť → preložiť → dokumentovať → odoslať) |
| `/saipen improve` |Meta-kontrolná auditácia zlepšení protokolu|
| `/saipen sub ...` |Vytvoriť/adoptovať len čitateľných podagentov|

**Balíčky kľúčov.** `ee`/`qq`pripraviť kompletné preklady/wiki balíčky bez
integrácie;`eee`/`qqq`prijímať len pripravené balíčky, potom integrovať, overiť,
prezrieť a odoslať.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)prechádza celým
vnútorne v pevnom poradí — senzory(saihunt, saitest, saipython, saiui),
výrobcovia(saitranslate, saiwiki)a Core ako jediný hlavný zápisník —
pokiaľ sa ďalšia čerstvá prechodná operácia nič skutočné už nemôže zmeniť. Pridáva presne jedno
mechanizmus vlastný: trvalý cieľ orchestrácie(``execution_intent:
konvergovať` with `konvergovať_cieľ: crew`)ktorý robí obvody obnoviteľné a
vyvoditeľné z dôkazov pri páde.`saipen crew --dry-run --json`vyvodí
obvod len na čítanie;`bootstrap/saipen_crew.*`je DOPOROČENÝ ručný
nástroj na viacokniové okná, nikdy niečo čo`saipen crew`znamená. Pozri
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Čo SAIPEN nie je

- **LLM alebo model**— ide o protokol, ktorý agenti sledujú, nie o inteligenciu.
- **IDE alebo hostovaná pamäťová databáza**— stav je bežné súbory vo vašom projekte;
nič nie je hostované.
- **Nahradenie Gitu**— Git stále vlastní históriu verzí; commitujte
  `.saipen/`ako ľubovolný iný kód.
- **Distribuovaný konsenzus**— pozrite sa na hranicu súčasnosti nižšie.
- **Záruka, že LLM bude robiť správne inžinierske rozhodnutia**— ono
zníži stratu kontextu a odchýlku od správania; nezaručuje neomylnosť stochastických agentov
neomylné.

Úlohou SAIPEN je pokračovanie/štátne zmluva plus overovanie a nástroje —
dávajú ďalšiemu agentovi začiatočný bod overený strojom, nie čarovného.

**Hranica súbežnosti.**Záznamované mutácie stavu(SAIOPS)použite
osový zámok s rozsahom projektu a záznam pre obnovenie([OPS § 5](saipen/OPS.md#5-locks)).
Bežné úpravy projektu a odpojení písma sú mimo tohto zámku. SAIPEN
nie je distribuovaná súhlasnosť, takže odpojené písma vyžadujú externé
súhlasenie([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ekosystém

|Projekt|Vzťah k SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Lokálne Windows centrum pre správu projektov SAIPEN — automaticky objavuje`.saipen/`pracovné prostredia, vizualizuje živý stav a výsledky konformity, spravuje lístky a spúšťa AI CLI. Spoločník, nie autorita.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Nástroj CodeNomad pre downstream vývoj, ktorý integruje SAIPEN: vkladá`BOOT.md`/`STYLE.md`do spustení OpenCode, zverejňuje krátkecie SAIPEN a zobrazenia stavu projektu, a pridáva trvalý front žiadostí.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Priesvitný Windows blok pre poznámky a správu úryvkov, ktorý automaticky detekuje`.saipen/`zložky a pridáva čitateľný prehliadač STATE/BOARD/LOG.|

## Dokumentácia

|Dokument|Čo to je|
|---|---|
| [SPEC.md](SPEC.md) |Formálna architektúra, ciele návrhu, litmusový test|
| [CORE.md](saipen/CORE.md) |Normatívne pokračovanie, stavový stroj a zmluva o príkaze|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Autonomická údržba a režim cieľa|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Vykonateľné/povahové požiadavky a pravidlá overovateľa|
| [GUIDE.md](GUIDE.md) |Človekovo výukové materiály|
| [RFC.md](saipen/RFC.md) |Kompatibilita presmeruje na rozdelené normatívne dokumenty|
| [STYLE.md](saipen/STYLE.md) |Štýl komunikácie agenta a hlas|
| [UI.md](saipen/UI.md) |Starodávne zlaté UI návrhové pokyny|
|Brožúra|Prezentácia brožúry —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Angličtina](guides/GUIDE_EN.md) · 🇪🇪 [Eesti](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Nemecky](guides/GUIDE_DE.md) · 🇫🇷 [Francúzsky](guides/GUIDE_FR.md) · 🇪🇸 [Španielsky](guides/GUIDE_ES.md) · 🇮🇹 [Taliansky](guides/GUIDE_IT.md)

🇵🇹 [Portugalský](guides/GUIDE_PT.md) · 🇳🇱 [Holandčina](guides/GUIDE_NL.md) · 🇵🇱 [Poľština](guides/GUIDE_PL.md) · 🇸🇪 [Švédsky](guides/GUIDE_SV.md) · 🇩🇰 [Dánsky](guides/GUIDE_DA.md)

🇫🇮 [Fínsky](guides/GUIDE_FI.md) · 🇳🇴 [Norvština](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Vietnamský jazyk](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Turecký jazyk](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Indonézsky jazyk](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Český jazyk](guides/GUIDE_CS.md) · 🇷🇴 [Rumunský jazyk](guides/GUIDE_RO.md) · 🇭🇺 [Maďarský jazyk](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Chorvátsky jazyk](guides/GUIDE_HR.md)

</details>

## Poznámky k nastaveniu

**Jazyk odpovede.**Agent odpovedá v**estónštine**ako predvolený — to je
nastavenie, nie požiadavka protokolu, a nič iné o SAIPEN nie je estónské.
Protokol, kód, commity a všetky dokumenty zostávajú anglické pri každom
hodnote. Zmena sa vykonáva v jednom mieste: v`reply_language:`riadku na vrchole
[`saipen/STYLE.md`](saipen/STYLE.md). `et`estónština,`en`angličtina,`ru`ruština,
`auto`vyberie sa z správy, ktorú ste poslali.

**Adapteri.**Platforma nie je pokrytá injektorm(DeepSeek, Qwen, standalone
OpenAI, atď.)? Poznámky na platformu živé v`extensions/adapters/`.

## Snímky obrazovky

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
