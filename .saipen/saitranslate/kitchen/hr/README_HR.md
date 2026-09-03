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

**Protokol za nastavak za AI kodne agente.**Projektova memorija se nalazi u običnom
Markdown datotekama unutar projekta(`.saipen/`), pa bilo koji kompatibilan hladni agent —
bez povijesti razgovora, bez memorije sesije — može pokrenuti`/saipen continue`, pročitati
pohranjeno`next_action`, i nastaviti rad bez pitanja korisnika da ponovno objasni
nešto. Stanje pripada projektu, a ne memoriji jednog proizvođača modela.

**Jedna naredba za nastavak. Stanje u običnim datotekama. Mašinsko provjereni ugovori.**

Repozitorij samosprema na svakom pushu; instalacija, stanje, provjere i
deinstalacija je lokalna — nema oblak, nema servis, nema bazu podataka.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.246.0** | [Spec](SPEC.md) | [Voditelj](GUIDE.md) | [Jezgra](saipen/CORE.md) | [Održavanje](saipen/MAINTENANCE.md) | [Stil](saipen/STYLE.md) | [UI](saipen/UI.md) | [Usljednost](saipen/CONFORMANCE.md) |MIT

**Brzi prečaci:** `cc` nastavlja kontekst projekta do konvergencije (nastavlja aktivni cilj ako je postavljen), `sss` prikazuje status bez diranja koda, a `ss` sprema kontrolnu točku i zaustavlja se. [Pogledaj punu kartu od 19 tipki](saipen/RFC.md#110-command-surface). Ćirilični blizanci također rade: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## Što ostaje

Živi projekt spremi se u`.saipen/`— obične datoteke koje možete čitati, usporediti i
commitati uz kod. Hladni agent odgovara na pet pitanja iz datoteka
samo:

|Datoteka / polje|Odgovori|
|---|---|
| `STATE.md` |Što se trenutno događa?(faza, aktivni ulaz, radni način, blokada) |
| `BOARD.md` |Što postoji za rad / što je aktivno?(graf ulaza: U TAKOĐER, NARUDŽBINA, ZAVRŠENO, BLOKIRANO) |
| `LOG.md` |Zašto je projekt dosegao ovaj stanje?(graf događaja koji se mogu dodati) |
| `KNOWLEDGE/` |Koje trajne činjenice projekta moraju preživjeti sesije?|
| `next_action` (u`STATE.md`) |Koja točno akcija treba da izvrši sljedeći agent?|

Ovo je ugovor o točki provjere, a ne prijedlog dizajna:`saipen stop`i svaki
prelazak ulaza pisaće datoteke u fiksnoj sekvenci, a rezultat provjerava
valider. Nije ništa pohranjeno u domaćem bazi podataka, a ništa se gubi kada se
session ends.

## Brzi početak

**1. Instalirajte jednom po stroju**— uči Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity, i bilo koji općeniti`~/.agents/skills`čitač(FreeBuff, itd.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`blok u instrukcije agentu
datoteke koje već imate(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— sigurnosno kopiranje svake od njih u`.bak`prvo —
i kopira protokol u odgovarajuće mape vještina. Nadao se van tih
putanje, bez demona, bez mrežnih poziva.</sub>

**2. Pokreni projekt**— otvori agent u svojoj mapi, unesi:

> `saipen set`

**Bez instalacije?**Zalijepi jednu liniju u bilo koji agent:

> Pročitaj&lt;clone&gt;/saipen/BOOT.md prvo(kernel za hladni start), zatim&lt;clone&gt;/saipen/INDEX.md +&lt;kloniraj&gt;/saipen/STYLE.md i slijedite ih.

**Promijenili ste mišljenje?**Jedna naredba vraća stvari na svoje mjesto:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Uklanja točno označeni blok(ostavljajući preostali dio vaše datoteke nepromijenjenim), spremi
a `.uninstalled.bak`napravi kopiju prvo, a zatim ukloni mape s vještinama.

## Zašto ne samo povijest razgovora?

SAIPEN cilja specifičnu grešku: AI agent za pisanje koda koji ne zapamti ništa
nakon što se sesija završi. Ostali alati i navike pokrivaju dio tog problema:

|Pristup|Što je dobro za|Što ne nosi|
|---|---|---|
|Povijest razgovora / memorija modela|Ugodno, bez postavke|Ovisno o sesiji i dobavljaču; ne pohranjuje se s projektom, pa hladni agent nikada ne vidi|
|Statično`AGENTS.md`/ datoteka uputa|Trajne stajalne pravila i konvencije|Neprestano ne predstavlja živi stanje zadatka`next_action`, ili povijest oporavka|
|Problem / bilježnica TODO|Upravljanje zadaćama i backlogom|Ne samostalno definira semantiku nastavka agenta — što hladni agent mora pročitati i izvršiti pri nastavku|
| **SAIPEN** |Živi stanje izvršavanja, radna reda, povijest događaja, trajna znanja i pravila nastavka provjerljiva računalom — u običnim datotekama pored koda|Ništa; ta kombinacija je ugovor|

Razlika nije u jednoj datoteci. Razlika je u tome što SAIPEN izvršava korak nastavka
provjerljivo računalom: prvo djelovanje hladnog agenta nakon`/saipen continue`je
određeno trajno`next_action`i provjereno validatorom, a ne
ponovno konstruirano iz memorije.

## Inženjerska dokaznica

SAIPEN kombinira normativni protokol u običnim datotekama s izvršivim, usmjerjenim prema neuspješnim ishodima
provjere. Repozitorij pokazuje dizajn protokola/mašine stanja, Python
alatstvo, shemama vodene stanja, razumijevanje oporavka, regresijsko testiranje,
graničnici radnih tokova s više agenata, i disciplinu specifikacije.

- **Kontrakt dizajniran.** [SPEC.md](SPEC.md)definira model nastavka koji je podržan datotekama
i stabilni učvršćeni kontrakt na disku;[CORE.md](saipen/CORE.md)
i[MAINTENANCE.md](saipen/MAINTENANCE.md)imaju trenutno normativno ponašanje.
- **Mašinsko provjereni stanja.**Stdlib-isključivo kanonski
  [valider](tools/validate.py)čita živi
  [STANJE shema](extensions/schemas/state.schema.json)i provjerava fazu
prijelaze, ovisnosti o biljećima, povezivanja grafa događaja, međudokument
invarijante, mogućnosti i stanje oporavka.
- **Pokrivenost neuspješnih slučajeva.** [CONFORMANCE.md](saipen/CONFORMANCE.md)preslikava
zahtjeve na[scenario fiksne točke](tests/scenarios/); the
  [izvršitelj scenarija](tools/run_scenarios.py)izvršava strukturne slučajeve prolaza/ne prolaza
uključujući oštećeno stanje oporavka, nevažeće prijelaze, cikluse ovisnosti i
ograničenja samočitanja.
- **Kontrole regresije.** [audit_checks.py](tools/audit_checks.py)mijenja
poznate dobre kopije i pokazuje da se provjere validera mogu i dalje pokazati kao crvene, umjesto
da trajno zelene provjere tretiraju kao dokaz.
- **Izvršna sloj.** [saipen.py](tools/saipen.py)pruža zapisivanje stanja
operacije;[bootstrap/](bootstrap/)drži instalaciju, deinstalaciju i izvoz
pomoćnici s opcijom[instalatora pre-commit hooka](tools/install_hook.py).
- **Otvoreni izbori.**Ključno protokolno stanje su obične datoteke bez izvršnog
ovisnosti. Kanonska validacija i alati naredbenog retka zahtijevaju Python, ali koriste samo
njegovu standardnu biblioteku i ne zahtijevaju`pip`instalaciju.

## Arhitektura

Tri sloja, strogo jednosmjerne ovisnosti:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Jezgra ne ovisi o održavanju: s onemogućenim samostalnim evolucijama, SAIPEN
i dalje je potpuno protokol za nastavak — hladni agent i dalje nastavlja.

- **Stanje mašine jezgre** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Samostalno održavanje**— ploča zaustavljena(ništa funkcijsko u`## TODO`,
ništa u`## DOING`)i ne`BLOCKED`? Automatski prijelazi`HUNT` (pretraživanje grešaka)
  → `ADD` (razvijanje značajki) → `HUNT`, nijedna pitanja postavljena. Sesija sjednje na
  `BLOCKED`nikada ne automatski lovi
  ([Održavanje § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Način ciljanja** — `/saipen goal <objective>`okreće ploču i pokreće
cilj unaprijed kroz VERIFY/REVIEW, padajući u autonomno održavanje
dok se pravilo završavanja ne aktivira ili dok se pokretanje ne udari u svoj krov(3 valova / 20 karata,
zatim kontrolne točke i izvještaj) ([Održavanje § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Ojačavanje**— serija ulaznih podataka analizira se u kirurške jedan-po-jedan karte
  (JEZGRO § 1.8); nepotpuna kontinuacija drvo očuvava nepotpisani rad(JEZGRO § 1.5);
tajne slične vrijednosti su izbrisane iz logova(`sk-***`) (JEZGRO § 1.2).

## Uobičajeni naredbe

Uobičajeni ulazne točke; potpuni trenutni površina nalazi se u
[JEZGRO § 1.10](saipen/CORE.md#110-command-surface).

|Naredba|Radi|
|---|---|
| `/saipen set` |Uzima projekt: stvara`.saipen/`stanje|
| `/saipen continue` |Nastavi iz trajno pohranjenog stanja projekta — bez ponovnog obrazovanja|
| `/saipen plan` |Pretvori zahtjev ili surovi backlog u kartice|
| `/saipen goal <text>` |Autonomna izvršavanja valova prema novom cilju|
| `/saipen validate` |Pokreni provjere konformnosti|
| `/saipen status` |Samočitanje prijave: faza, kartice, blokatori, starih podataka|
| `/saipen stop` |Kontrolna točka i zaustavi|

<details>
<summary><b>More commands</b></summary>

|Naredba|Radi|
|---|---|
| `/saipen hunt` |Silovito pokreni pregled nedostataka/ponovnih poboljšanja sada|
| `/saipen markhunt` |Sušenje, neograničena revizija — zapisuje pronalaze, ne popravlja ništa|
| `/saipen ship` |Vrata za objavu; potvrdi, označi i pošalji kada je dopušteno|
| `/saipen clean` |Ploča i čišćenje stanja|
| `/saipen translate` |Isolirana prijevodna tvornica|
| `/saipen prepare` / `/saipen collect` |Rad s paketima za prelazak / integracija spremnog paketa|
| `/saipen test` |Pokreni deklarirani set testova, izvještaj samo|
| `/saipen crew` |Cirkuit posade s fiksnom redom(lovi → reproduciraj → prihvat → gradnja → prijevod → dokumentacija → isporuka) |
| `/saipen improve` |Meta-kontrolna revizija poboljšanja protokola|
| `/saipen sub ...` |Stvaranje/uzimanje samočitljivih podagenta|

**Paket ključeva.** `ee`/`qq`Priprema potpunih prijevodnih/wiki paketa bez
integracije;`eee`/`qqq`prihvatiti samo spremne pakete, zatim integrirati, provjeriti,
pregledati i objaviti.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)prolazi kroz cijelo
uključeni tim u fiksnom redoslijedu — senzori(saihunt, saitest, saipython, saiui),
proizvođači(saitranslate, saiwiki)i Core kao jedini glavni pisač —
dok ne dolazi do nove potpune prolaznice koja više ništa stvarno ne može promijeniti. Dodaje točno jedan
mehanizam vlastitog: trajna organizacija cilja(„execution_intent:
konvergiraj` with `converge_target: crew`)koji čini krug ponovno pokretljivim i
izvodljivim iz dokaza.`saipen crew --dry-run --json`izvodi
krug samo za čitanje;`bootstrap/saipen_crew.*`je NEOBRAZLOŽENI ručni
pomoćnik s više prozora, nikada nešto što`saipen crew`znači. Pogledajte
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Što SAIPEN nije

- **LLM ili model**— to je protokol kojeg agenti slijede, a ne inteligencija.
- **IDE ili baza podataka za pohranu u memoriji**— stanje su obične datoteke u vašem projektu;
ništa nije posluženo.
- **Zamjena za Git**— Git još uvijek vlasnički ima povijest verzija; commitajte
  `.saipen/`kao bilo koja druga koda.
- **Distribuirano saglasje**— pogledajte granicu koncurentnosti ispod.
- **Zaključak da će LLM napraviti ispravne inženjerske odluke**— on
smanjuje gubitak konteksta i drift ponašanja; ne čini stohastične agente
neosporne.

SAIPENova je posla nastavak/ugovor o stanju plus validacija i alati —
preusmjeravanje sljedećem agentu strojno provjerenog početnog točke, a ne magije.

**Granica koncurrentnosti.**Dnevnik promjena stanja(SAIOPS)korištenje
operacijskog zaključka ograničenog na projekt i dnevnik oporavka([OPS § 5](saipen/OPS.md#5-locks)).
Obične promjene u projektu i odvojeni pisači nalaze se van tog zaključka. SAIPEN
nije distribuirano konsenzusno računanje, pa odvojeni pisači zahtijevaju vanjsku
koordinaciju([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ekosustav

|Projekt|Odnos prema SAIPEN-u|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Lokalni Windows kontrolni centar za projekte SAIPEN — automatski otkriva`.saipen/`radne površine, prikazuje živi status i odluke o usklađenosti, upravlja kartama i pokreće AI CLI-je. Pratioca, a ne autoritet.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Nizakodni CodeNomad fork koji integrira SAIPEN: ubacuje`BOOT.md`/`STYLE.md`u pokretanje OpenCode-a, prikazuje kratice SAIPEN-a i pogled na stanje projekta, te dodaje trajnu redovnicu za upite.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Nosiv Windows blok za brzo pisanje i upravljanje isječcima koji automatski prepoznaje`.saipen/`mape i dodaje pregledač za STATE/BOARD/LOG u samočitanom režimu.|

## Dokumentacija

|Dokument|Što je|
|---|---|
| [SPEC.md](SPEC.md) |Formalna arhitektura, ciljevi dizajna, litmus test|
| [CORE.md](saipen/CORE.md) |Normativna nastavak, stanje mašine, i ugovor o naredbi|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Samostalna održavanje i Režim cilja|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Izvršivi/poševni zahtjevi i pravila valjatora|
| [GUIDE.md](GUIDE.md) |Ljudski tutorijal|
| [RFC.md](saipen/RFC.md) |Pretoka u kompatibilnosti prema razdvojenim normativnim dokumentima|
| [STYLE.md](saipen/STYLE.md) |Stil komunikacije agenta i glas|
| [UI.md](saipen/UI.md) |Vječna zlatna UI dizajnerska vodnica|
|Brošura|Predstavna brošura —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Engleski](guides/GUIDE_EN.md) · 🇪🇪 [Eesti](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Njemački](guides/GUIDE_DE.md) · 🇫🇷 [Francuski](guides/GUIDE_FR.md) · 🇪🇸 [Španjolski](guides/GUIDE_ES.md) · 🇮🇹 [Talijanski](guides/GUIDE_IT.md)

🇵🇹 [Portugalski](guides/GUIDE_PT.md) · 🇳🇱 [Nizozemski](guides/GUIDE_NL.md) · 🇵🇱 [Poljski](guides/GUIDE_PL.md) · 🇸🇪 [Švedski](guides/GUIDE_SV.md) · 🇩🇰 [Danski](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Napomene o konfiguraciji

**Jezik odgovora.**Agenata odgovara na**estonski**po defaultu — to je
postavka, a ne zahtjev protokola, a ništa drugo u vezi s SAIPEN nije na estonskom.
Protokol, kod, commiti i svaki dokument ostaju na engleskom jeziku za svaku
vrijednost. Promijenite ga u jednom mjestu:`reply_language:`linija na vrhu
[`saipen/STYLE.md`](saipen/STYLE.md). `et`estonski,`en`engleski,`ru`ruseki,
`auto`odabire iz poruke koju ste poslali.

**Adapteri.**Platforma nije pokrivena injektorom(DeepSeek, Qwen, standalone
OpenAI, itd.)? Napomene po platformama nalaze se u`extensions/adapters/`.

## Snimke zaslona

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
