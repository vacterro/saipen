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

**Pokračovací protokol pro AI kódovací agenty.**Paměť projektu existuje v prostém
souborech Markdown uvnitř projektu(`.saipen/`), takže jakýkoli kompatibilní chladný agent —
bez historie chatu, bez paměti relace — může běžet`/saipen continue`, přečíst
uložené`next_action`, a pokračovat ve práci bez nutnosti žádat uživatele, aby všechno znovu vysvětlil
. Stav patří projektu, nikoli paměti jednoho výrobce modelu.

**Jedna příkaz pro obnovení. Stav v prostém souboru. Kontrakty kontrolované strojem.**

Repositář se ověřuje sám na každém pushu; instalace, stav, kontroly a
odinstalace jsou všechny místní — žádná cloudu služba, žádný démon, žádná databáze.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.234.2** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [Core](saipen/CORE.md) | [Maintenance](saipen/MAINTENANCE.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) |MIT

**Rychlé klávesy:** `cc` pokračuje v konvergenci projektového kontextu (obnoví běžící cíl, pokud je nastaven), `sss` zobrazí stav bez dotyku kódu a `ss` uloží kontrolní bod a zastaví. [Podívej se na úplnou mapu 19 kláves](saipen/RFC.md#110-command-surface). Fungují i cyrilské dvojníky: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## Co zůstává

Živá paměť projektu žije v`.saipen/`— běžné soubory, které můžete číst, prověřit a
commitovat vedle kódu. Chladný agent odpovídá na pět otázek z souborů
sám:

|Soubor / pole|Odpovědi|
|---|---|
| `STATE.md` |Co se právě děje?(fáze, aktivní lístek, provozní režim, blokátor) |
| `BOARD.md` |Jaká práce existuje / co je aktivní?(graf lístků: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |Proč projekt dosáhl tohoto stavu?(pouze přidávající graf událostí) |
| `KNOWLEDGE/` |Jaké trvalé fakta projektu musí přežít relace?|
| `next_action` (v`STATE.md`) |Jaké přesné akce by měl další agent provést?|

Toto je smlouva o kontrolním bodě, nikoli návrh návrhu:`saipen stop`a každý
přechod lístku zapisuje soubory v pevném pořadí a výsledek je ověřován
ověřovatelem. Nic se ukládá do hostované databáze a nic se neztrácí, když
relace končí.

## Rychlé začátek

**1. Nainstalujte jednou na každém počítači**— vyučuje Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity a libovolný obecný`~/.agents/skills`čtečku(FreeBuff, atd.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`blok do instrukce agenta
soubory, které už máte(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— vytvoření zálohy každého do`.bak`nejprve —
a kopíruje protokol do odpovídajících složek dovedností. Nic mimo ty
cesty, žádný démon, žádné síťové volání.</sub>

**2. Spusťte projekt**— otevřete agenta ve svém adresáři, napište:

> `saipen set`

**Žádné instalace?**Vložte jednu řádku do libovolného agenta:

> Přečtěte si&lt;clone&gt;/saipen/BOOT.md nejprve(chladný start jádra), pak&lt;clone&gt;/saipen/INDEX.md +&lt;kloonovat&gt;/saipen/STYLE.md a následujte je.

**Změnil jste názor?**Jedna příkaz to vrátí zpět:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Odstraní přesně označený blok(nechává zbytek vašeho souboru beze změny), uloží
a `.uninstalled.bak`vytvoří kopii nejprve a odstraní složky s dovednostmi.

## Proč nechat jen historii chatu?

SAIPEN cílí na konkrétní selhání: AI kódovací agent, který zapomíná všechno
po ukončení sezení. Jiné nástroje a zvyky pokrývají část tohoto problému:

|Přístup|Co je dobré pro|Co neobsahuje|
|---|---|---|
|Historie chatu / paměť modelu|Pohodlné, bez nastavení|Závislé na relaci a poskytovateli; nejsou ukládány s projektem, takže studený agent je nikdy nevidí|
|Stálé`AGENTS.md`soubor / instrukce|Trvalé stojící pravidla a konvence|Samo o sobě neznamená živý stav úkolu`next_action`, nebo historii obnovy|
|Sledování problémů / TODO|Správa úkolů a zásobníku|Sám o sobě nevytváří sémantiku pokračování agenta — co musí chladný agent číst a provádět při obnovení|
| **SAIPEN** |Živý stav provádění, pracovní fronta, historie událostí, trvalé znalosti a pravidla pokračování ověřovaná strojem — v běžných souborech vedle kódu|Nic; tato kombinace je smlouva|

Rozdíl není v jednom souboru. Je v tom, že SAIPEN provádí krok obnovení
ověřitelné: první akce chladného agenta po`/saipen continue`je
diktována uchovávaným`next_action`a ověřená validátorem, nikoli
rekonstruovaná z paměti.

## Inženýrské důkazy

SAIPEN kombinuje normativní protokol ve formě běžných souborů s proveditelným, orientovaným na selhání
kontroly. Repozitář ukazuje návrh protokolu/stavového stroje, Python
nástroje, schéma-ový stav, odvození obnovy, regresní testování,
omezení pracovních toků víceagentních systémů a disciplína specifikace.

- **Navržený smlouva.** [SPEC.md](SPEC.md)definuje souborově podporovaný
model pokračování a stabilní smlouvu na disku;[CORE.md](saipen/CORE.md)
a[MAINTENANCE.md](saipen/MAINTENANCE.md)mají aktuální normativní chování.
- **Stav ověřený strojem.**Stdlib-only canonical
  [ověřovatel](tools/validate.py)čte živý
  [STAV schéma](extensions/schemas/state.schema.json)a ověřuje přechod fáze
přechody, závislosti vstupen, odkazy v grafu událostí, mezi-dokument
invarianty, možnosti a stav obnovy.
- **Pokrytí selhání.** [CONFORMANCE.md](saipen/CONFORMANCE.md)mapuje
požadavky na[scénářové přípravy](tests/scenarios/); the
  [spouštěč scénářů](tools/run_scenarios.py)provádí strukturální testy na úspěch/neúspěch
včetně poškozeného stavu obnovy, neplatných přechodů, závislostí cykly a
omezení jen pro čtení.
- **Kontrola regrese.** [audit_checks.py](tools/audit_checks.py)mění
známé dobré kopie a dokazuje, že ověřovací kontroly mohou stále selhat, místo toho
nezaměřuje se na trvale zelenou kontrolu jako důkaz.
- **Spustitelná vrstva.** [saipen.py](tools/saipen.py)poskytuje zapsaný stav
operace;[bootstrap/](bootstrap/)uchovejte instalaci, odinstalaci a export
pomocníci s volitelným[instalátorem předpříkazu](tools/install_hook.py).
- **Explicitní kompromisy.**Stav základního protokolu jsou běžné soubory bez runtime
závislosti. Kanonická ověřování a nástroje CLI vyžadují Python, ale používají pouze
jeho standardní knihovnu a nepotřebují žádné`pip`instalace.

## Architektura

Tři vrstvy, přísně jednocestné závislosti:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Jádro nezávisí na údržbě: s vypnutou autonomní evolucí, SAIPEN
je stále kompletní pokračovací protokol — chladný agent stále obnoví.

- **Stavový stroj jádra** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Autonomní údržba**— deska zastavena(nic funkčního v`## TODO`,
nic v`## DOING`)a ne`BLOCKED`? Automatické přechody`HUNT` (vyhledávání chyb)
  → `ADD` (rozvíjet funkce) → `HUNT`, bez jediného položeného otázky. Sezení sedí na
  `BLOCKED`nikdy neautomaticky lovuje
  ([Údržba § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Režim cíle** — `/saipen goal <objective>`otočí desku a spustí
cíl dopředu přes VERIFY/REVIEW, padne do autonomní údržby
dokud pravidlo dokončení nenastane nebo běh nedosáhne svého limitu(3 vlny / 20 lístků,
pak kontrolní body a hlášení) ([Údržba § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Zpevnění**— dávkový vstup je analyzován do chirurgických jednotlivých lístků
  (CORE § 1.8); pokračování nečistého stromu zachovává neodeslanou práci(CORE § 1.5);
hodnoty podobné tajným jsou vyříznuty z protokolů(`sk-***`) (CORE § 1.2).

## Běžné příkazy

Běžné vstupy; kompletní aktuální povrch žije v
[Core § 1.10](saipen/CORE.md#110-command-surface).

|Příkaz|Dělá|
|---|---|
| `/saipen set` |Přijmout projekt: vytvořit`.saipen/`stav|
| `/saipen continue` |Obnovit ze zachovaného stavu projektu — bez opětovného vysvětlování|
| `/saipen plan` |Převést požadavek nebo surový zásobník na tikety|
| `/saipen goal <text>` |Autonomní provádění vlny proti novému cíli|
| `/saipen validate` |Spustit kontroly shody|
| `/saipen status` |Pouze pro čtení: fáze, tikety, blokátory, zastaralost|
| `/saipen stop` |Zaznamenat a zastavit|

<details>
<summary><b>More commands</b></summary>

|Příkaz|Dělá|
|---|---|
| `/saipen hunt` |Nyní násilně spustit prohlídku vad/lepšení|
| `/saipen markhunt` |Suchá, neomezená auditace — zaznamenává nálezy, opravuje nic|
| `/saipen ship` |Kontroly uvolnění; potvrď, označ a pošli, když je povoleno|
| `/saipen clean` |Výčet a čištění desky a stavu|
| `/saipen translate` |Izolovaná překladová továrna|
| `/saipen prepare` / `/saipen collect` |Balíčkování pro předání / integrovat připravený balíček|
| `/saipen test` |Spusťte deklarovaný soubor testů, hlásit pouze|
| `/saipen crew` |Řetězec posádky v pevném pořadí(hledat → reprodukovat → přijmout → sestavit → přeložit → dokumentovat → odeslat) |
| `/saipen improve` |Meta-kontrolní audit zlepšení protokolu|
| `/saipen sub ...` |Vytvořit/adoptovat pouze čtenářské podagenty|

**Balíčkovat klíče.** `ee`/`qq`připravit kompletní překladové/wiki balíčky bez
integrování;`eee`/`qqq`přijmout pouze připravené balíčky, poté integrovat, ověřit,
zkoumat a poslat.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)prochází celým
vloženým týmem v pevném pořadí — senzory(saihunt, saitest, saipython, saiui),
výrobci(saitranslate, saiwiki)a Core jako jediný hlavní zapisovatel —
dokud další čerstvý průchod nemá nic skutečného, co by mohl změnit. Přidává přesně jedno
mechanismus vlastní: trvalý orchestrace cíl(„execution_intent:
konvergovat` with `converge_target: crew`)to způsobuje, že obvod je možné obnovit a
lze z něj odvodit závažný pád na základě důkazů.`saipen crew --dry-run --json`odvodí
obvod pouze pro čtení;`bootstrap/saipen_crew.*`je VOLITELNÝ ruční
nástroj pro více okenních funkcí, nikdy ne to, co`saipen crew`znamená. Viz
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Co SAIPEN není

- **LLM nebo model**— jedná se o protokol, kterým agenti dodržují, nikoli o inteligenci.
- **IDE nebo hostovaná paměťová databáze**— stav jsou běžné soubory ve vašem projektu;
nic není hostované.
- **Náhrada pro Git**— Git stále má kontrolu nad historií verzí; commitujte své
  `.saipen/`jako jakýkoli jiný kód.
- **Distribuovaný konsenzus**— viz níže uvedená hranice souběžnosti.
- **Záruka, že LLM provede správné inženýrské rozhodnutí**— on
snižuje ztrátu kontextu a chování odchylky; neznamená to, že stochastické agenty
jsou neomylné.

Úkolem SAIPEN je pokračovat ve smlouvě o stavu/činnosti plus ověřování a nástroje —
předání dalšímu agentovi počátečního bodu ověřeného strojem, nikoli magie.

**Hranice souběžnosti.**Záznam změn stavu(SAIOPS)použijte
označený systémový zámek a záznam pro obnovení([OPS § 5](saipen/OPS.md#5-locks)).
Běžné úpravy projektu a odpojení autoři jsou mimo tento zámek. SAIPEN
není distribuovaný konsenzus, takže odpojení autoři vyžadují externí
souhlas([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ekosystém

|Projekt|Vztah k SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Místní Windows ovládací středisko pro projekty SAIPEN — automaticky objevuje`.saipen/`pracovní prostředí, vizualizuje živý stav a výsledky konformity, spravuje lístky a spouští AI CLI. Společník, ne odborník.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Dolní tok CodeNomad fork, který integruje SAIPEN: vkládá`BOOT.md`/`STYLE.md`do spouštění OpenCode, zpřístupňuje krátkoutky SAIPEN a pohledy na stav projektu a přidává trvalou frontu příkazů.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Přenosný Windows náčrtník a správce fragmentů, který automaticky detekuje`.saipen/`složky a přidává čtenáře STATE/BOARD/LOG.|

## Dokumentace

|Dokument|Co to je|
|---|---|
| [SPEC.md](SPEC.md) |Formální architektura, cíle návrhu, litmusový test|
| [CORE.md](saipen/CORE.md) |Normativní pokračování, stavový stroj a smlouva o příkazu|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Samostatná údržba a režim cílů|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Vykonatelné/behaviorální požadavky a pravidla validátoru|
| [GUIDE.md](GUIDE.md) |Člověkem prováděný tutoriál|
| [RFC.md](saipen/RFC.md) |Přesměrování kompatibility na rozdělené normativní dokumenty|
| [STYLE.md](saipen/STYLE.md) |Styl komunikace agenta a hlas|
| [UI.md](saipen/UI.md) |Rámcové vedení pro návrh UI v designu Vintage Golden|
|Brožura|Prezentace brožury —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Angličtina](guides/GUIDE_EN.md) · 🇪🇪 [Eesti](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Německy](guides/GUIDE_DE.md) · 🇫🇷 [Francouzština](guides/GUIDE_FR.md) · 🇪🇸 [Španělština](guides/GUIDE_ES.md) · 🇮🇹 [Italština](guides/GUIDE_IT.md)

🇵🇹 [Portugalština](guides/GUIDE_PT.md) · 🇳🇱 [Holandština](guides/GUIDE_NL.md) · 🇵🇱 [Polština](guides/GUIDE_PL.md) · 🇸🇪 [Švédština](guides/GUIDE_SV.md) · 🇩🇰 [Dánština](guides/GUIDE_DA.md)

🇫🇮 [Finský](guides/GUIDE_FI.md) · 🇳🇴 [Norština](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Turečtina](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Indonéština](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Romština](guides/GUIDE_RO.md) · 🇭🇺 [Maďarština](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenština](guides/GUIDE_SK.md) · 🇭🇷 [Chorvatský](guides/GUIDE_HR.md)

</details>

## Poznámky k konfiguraci

**Jazyk odpovědi.**Agent odpovídá v**estonsky**ve výchozím nastavení — to je
nastavení, ne požadavek protokolu, a nic jiného ohledně SAIPEN není estonské.
Protokol, kód, commity a každý dokument zůstávají anglické v každém
hodnotě. Změňte to v jednom místě: v`reply_language:`řádku na začátku
[`saipen/STYLE.md`](saipen/STYLE.md). `et`estonsky,`en`anglicky,`ru`ruština,
`auto`vytahuje z zprávy, kterou jste poslali.

**Adaptéry.**Platforma není pokryta injektorem(DeepSeek, Qwen, standalone
OpenAI, atd.)? Poznámky pro jednotlivé platformy jsou v`extensions/adapters/`.

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
