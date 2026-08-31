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

**Protocol de continuare pentru agenți de codificare AI.**Memoria proiectului se află în format plain
fișiere Markdown din interiorul proiectului(`.saipen/`), așadar orice agent rece compatibil —
fără istoric de chat, fără memorie de sesiune — poate rula`/saipen continue`, să citească
starea persistată`next_action`, și să reia munca fără a cere utilizatorului să-și explice din nou
ceva. Starea aparține proiectului, nu memoriei unui singur furnizor de modele.

**O comandă pentru a relua. Stare în fișiere plain. Contracte verificate de mașină.**

Repozitorul se validează singur la fiecare push; instalare, stare, verificări și
dezinstalare are loc local — nu există serviciu în cloud, nu există daemon, nu există bază de date.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.231.11** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [Core](saipen/CORE.md) | [Maintenance](saipen/MAINTENANCE.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) |MIT

**Comenzi rapide:** `cc` continuă contextul proiectului până la convergență (reia un obiectiv activ dacă este setat), `sss` afișează starea fără să atingă codul, iar `ss` salvează un punct de control și se oprește. [Vezi harta completă cu 19 taste](saipen/RFC.md#110-command-surface). Gemenii chirilici funcționează și ei: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## Ce persistă

Memoria proiectului live există în`.saipen/`— fișiere simple pe care le poți citi, compara și
comite alături de cod. Un agent rece răspunde la cinci întrebări din fișiere
singur:

|Fișier / câmp|Răspunsuri|
|---|---|
| `STATE.md` |Ce se întâmplă în prezent?(fază, ticket activ, mod de operare, blocant) |
| `BOARD.md` |Ce lucrări există / ce este activ?(grafic de tickete: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |De ce a ajuns proiectul în această stare?(grafic de evenimente append-only) |
| `KNOWLEDGE/` |Ce fapte durabile ale proiectului trebuie să supraviețuiască sesiunilor?|
| `next_action` (în`STATE.md`) |Ce acțiune exactă ar trebui să execute următorul agent?|

Aceasta este o contract de checkpoint, nu o sugestie de proiectare:`saipen stop`și fiecare
tranziție de ticket scrie fișierele într-un ordin fix, iar rezultatul este verificat de
un validator. Nimic nu este stocat într-un bază de date găzduită, și nimic nu se pierde când un
sesiunea se încheie.

## Pornire rapidă

**1. Instalează o dată pe mașină**— învață Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity, și orice altă`~/.agents/skills`cititor(FreeBuff, etc.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`bloc la instrucțiunea agentului
fișierele pe care le ai deja(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— salvând fiecare dintre ele în`.bak`primul pas —
și copiază protocolul în folderul corespunzător al abilităților. Nimic în afara acestora
cale, fără demon, fără apeluri de rețea.</sub>

**2. Începe un proiect**— deschide un agent în folderul tău, introdu:

> `saipen set`

**Fără instalare?**Lipiește o singură linie în orice agent:

> Citeste&lt;clone&gt;/saipen/BOOT.md întâi(nucleu de pornire rece), apoi&lt;clone&gt;/saipen/INDEX.md +&lt;clone&gt;/saipen/STYLE.md și urmați-le.

**V-ați schimbat părerea?**O comandă îl pune înapoi:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

El șterge exact blocul marcat(lăsând restul fișierului intact), salvează
a `.uninstalled.bak`face o copie, apoi șterge folderele de abilități.

## De ce nu istoria de chat?

SAIPEN țintește o problemă specifică: un agent de codare AI care nu-și amintește nimic
o dată ce sesiunea se încheie. Alte unelte și obiceiuri acoperă o parte din această problemă:

|Abordare|Ce este bun pentru|Ce nu transportă|
|---|---|---|
|Istoricul conversației / memoria modelului|Convenabil, fără configurare|Depinde de sesiune și de furnizor; nu este stocat cu proiectul, așadar un agent rece nu îl vede niciodată|
|Static`AGENTS.md`/fișier instrucțiuni|Reguli și convenții durabile|Nu reprezintă singur starea activă a sarcinii,`next_action`, sau istoricul de recuperare|
|Tracker de probleme / TODO|Gestionare sarcini și backlog|Nu definește singur semantica de continuitate a agentului — ceea ce trebuie să citească și să execute un agent rece la reluare|
| **SAIPEN** |Starea de execuție activă, coada de lucru, istoricul evenimentelor, cunoștințele durabile și regulile de continuitate verificate de mașină — în fișiere obișnuite alăturate codului|Nimic; acea combinație este contractul|

Diferența nu este niciun fișier. Este faptul că SAIPEN face pasul de reluare
verificabil de mașină: prima acțiune a unui agent rece după`/saipen continue`este
dictată de cel persistat`next_action`și verificat de un validator, nu
reconstruit din memorie.

## Evidență de inginerie

SAIPEN perechează un protocol obișnuit de fișiere simple cu unul executabil, orientat spre eșec
verificări. Repository-ul demonstrează proiectarea protocolului/machine-uri de stare, Python
tooling, stare condusă de schema, raționament de recuperare, testare de regresie,
granițe de lucru multi-agent, și disciplină de specificație.

- **Contract proiectat.** [SPEC.md](SPEC.md)definește modelul de continuitate susținut de fișier și contractul stabil pe disc;
CORE.md[și](saipen/CORE.md)
MAINTENANCE.md[definesc comportamentul normativ actual.](saipen/MAINTENANCE.md)Stare verificată de mașină.
- ****Validatorul bazat doar pe stdlib
  [validator](tools/validate.py)citește schema de stare live
  [schema de stare](extensions/schemas/state.schema.json)și verifică tranzițiile de fază
dependențele de bilete, legăturile dintre evenimente, legăturile interdocument
invariantele, capacitățile și starea de recuperare.
- **Acoperirea eșecurilor.** [CONFORMANCE.md](saipen/CONFORMANCE.md)mapează
cerințele la[fixture-uri de scenarii](tests/scenarios/); the
  [executor de scenarii](tools/run_scenarios.py)execută cazuri de trecere/echec structural
inclusiv stări de recuperare corupte, tranziții invalide, cicluri de dependență și
restricții de doar citire.
- **Controlul regresiei.** [audit_checks.py](tools/audit_checks.py)modifică
copii cunoscute ca fiind bune și dovedește că verificările validatorului pot totuși să devină roșii, în loc de
a considera o verificare permanent verde ca dovadă.
- **Stratul executabil.** [saipen.py](tools/saipen.py)oferă starea jurnalizată
operațiuni;[bootstrap/](bootstrap/)păstrează instalare, dezinstalare și export
ajutoare, cu un optional[instalator de hook pre-commit](tools/install_hook.py).
- **Compromise-uri explicite.**Starea protocolului de bază este formată din fișiere obișnuite fără execuție
dependentă. Validarea canonică și instrumentele CLI necesită Python, dar folosesc doar
biblioteca standard și nu necesită`pip`instalare.

## Arhitectură

Trei straturi, dependențe strict unidirecționale:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Nucleul nu depinde de întreținere: cu evoluție autonomă dezactivată, SAIPEN
totuși este un protocol complet de continuitate — un agent rece încă poate relua.

- **Mașina de stare nucleară** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Întreținere autonomă**— placa oprită(nimic funcțional în`## TODO`,
nimic în`## DOING`)și nu`BLOCKED`? Tranzitii automate`HUNT` (scanare buguri)
  → `ADD` (evoluție funcții) → `HUNT`, fără să se pună nicio întrebare. O sesiune care se află într-o poziție
  `BLOCKED`niciodată nu caută automat
  ([Măntenire § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Modul Obiectiv** — `/saipen goal <objective>`inversează tabla și execută
obiectivul înainte prin VERIFY/REVIEW, intrând în întreținere autonomă
până când se declanșează regula de finalizare sau execuția atinge limita sa(3 valuri / 20 de bilete,
apoi verifică punctele de control și raportează) ([Măntenire § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Întărirea**— intrarea în lot este analizată în bilete individuale precise
  (CORE § 1.8); continuitatea arborelui murdar păstrează munca neîncheiată(CORE § 1.5);
valorile asemănătoare cu secretele sunt șterse din jurnale(`sk-***`) (CORE § 1.2).

## Comenzi comune

Puncte de intrare obișnuite; suprafața completă actuală se află în
[Core § 1.10](saipen/CORE.md#110-command-surface).

|Comandă|Face|
|---|---|
| `/saipen set` |Adoptă un proiect: creează`.saipen/`stare|
| `/saipen continue` |Reia din starea proiectului persistată — fără rebriefing|
| `/saipen plan` |Transformă o cerere sau un backlog necorespunzător în tickete|
| `/saipen goal <text>` |Execuție autonomă a undei împotriva unei noi obiective|
| `/saipen validate` |Rulează verificările de conformitate|
| `/saipen status` |Raport doar pentru citire: fază, tickete, blocări, vechime|
| `/saipen stop` |Checkpoint și oprire|

<details>
<summary><b>More commands</b></summary>

|Comandă|Face|
|---|---|
| `/saipen hunt` |Forțează scanarea defectelor/îmbunătățirilor acum|
| `/saipen markhunt` |Audit uscat, fără limită — înregistrează găsirile, nu rezolvă nimic|
| `/saipen ship` |Găți de eliberare; comite, etichetează și pune la dispoziție când este permis|
| `/saipen clean` |Curățare de tablă și stare|
| `/saipen translate` |Fabrică de traducere izolată|
| `/saipen prepare` / `/saipen collect` |Lucrul cu pachete pentru transfer / integrare un pachet gata|
| `/saipen test` |Rulează suitea de teste declarată, raportează doar|
| `/saipen crew` |Circuit de echipă cu ordine fixă(căutare → reproducere → preluare → construire → traducere → documentare → livrare) |
| `/saipen improve` |Audit de meta-control pentru îmbunătățiri ale protocolului|
| `/saipen sub ...` |Generează/adoptă sub-agente doar pentru citire|

**Pachete de chei.** `ee`/`qq`pregătește pachete complete de traducere/wiki fără
integrare;`eee`/`qqq`acceptă doar pachete gata, apoi integrează, verifică,
revizuieste și trimite.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)parcurge întregul
echipă integrată într-un ordin fix — senzori(saihunt, saitest, saipython, saiui),
producători(saitranslate, saiwiki)și Core ca singurul scriitor principal —
până când o altă parcurgere nouă nu mai are nimic real de schimbat. Adaugă exact unul
mecanism propriu: ținta de orchestrare durabilă(„execution_intent:
converge` with `converge_target: crew`)care face ca circuitul să fie reușit și
derivabil din evidență.`saipen crew --dry-run --json`derivează
circuitul doar pentru citire;`bootstrap/saipen_crew.*`este un helper manual OPȚIONAL
multi-fereastră, niciodată ceea ce`saipen crew`înseamnă. Vezi
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Ce nu este SAIPEN

- **Un LLM sau un model**— este un protocol pe care agenții îl urmează, nu o inteligență.
- **Un IDE sau o bază de date de memorie găzduită**— starea este fișiere obișnuite în proiectul tău;
nimic nu este găzduit.
- **O alternativă pentru Git**— Git încă deține istoria versiunilor; efectuează commit-ul tău
  `.saipen/`ca orice altă cod.
- **Consens distribuit**— vezi granița de concurență de mai jos.
- **O garanție că un LLM va lua decizii corecte de inginerie**— el
reduce pierderea contextului și derapajul comportamental; nu face agenții stohastice
infailibile.

SAIPEN-ul are ca sarcină o continuare/contract de stare plus validare și instrumente —
predând următorului agent un punct de pornire verificat de mașină, nu magie.

**Limită de concurență.**Mutări de stare jurnalizate(SAIOPS)folosește un
loc de blocare pe proiect și un jurnal de recuperare([OPS § 5](saipen/OPS.md#5-locks)).
Editele obișnuite ale proiectului și scriitorii deconectați se află în afara acelui blocare. SAIPEN
nu este consens distribuit, așa că scriitorii deconectați necesită coordonare externă
coordonare([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ecosistem

|Proiect|Relația cu SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Centrul de control local Windows pentru proiecte SAIPEN — descoperă automat`.saipen/`spațiile de lucru, vizualizează starea live și verdictele de conformitate, gestionează biletele și lansează CLI-uri AI. Un companion, nu autoritatea.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Fork CodeNomad Downstream care integrează SAIPEN: injectează`BOOT.md`/`STYLE.md`în lansări OpenCode, expune scurteci de SAIPEN și vizualizări ale stării proiectului, și adaugă o coadă persistentă de prompturi.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Tableau de bord Windows portabil și manager de fragmente care detectează automat`.saipen/`foldere și adaugă un vizualizator de STATE/BOARD/LOG în modul de lectură.|

## Documentație

|Document|Ce este|
|---|---|
| [SPEC.md](SPEC.md) |Arhitectură formală, obiective de proiectare, test litmus|
| [CORE.md](saipen/CORE.md) |Continuare normativă, mașină de stare și contract de comandă|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Menținere autonomă și Modul de Obiectiv|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Cerințe executabile/comportamentale și reguli pentru validator|
| [GUIDE.md](GUIDE.md) |Tutoriale pentru om|
| [RFC.md](saipen/RFC.md) |Redirecționare compatibilitate către documentele normative separate|
| [STYLE.md](saipen/STYLE.md) |Stil și voce de comunicare a agentului|
| [UI.md](saipen/UI.md) |Linii directoare pentru designul UI Golden Vintage|
|Broșură|Broșură de prezentare —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Engleză](guides/GUIDE_EN.md) · 🇪🇪 [Eesti](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Germană](guides/GUIDE_DE.md) · 🇫🇷 [Franceză](guides/GUIDE_FR.md) · 🇪🇸 [Spaniolă](guides/GUIDE_ES.md) · 🇮🇹 [Italiană](guides/GUIDE_IT.md)

🇵🇹 [Portugheză](guides/GUIDE_PT.md) · 🇳🇱 [Olandeză](guides/GUIDE_NL.md) · 🇵🇱 [Poloneză](guides/GUIDE_PL.md) · 🇸🇪 [Suedeză](guides/GUIDE_SV.md) · 🇩🇰 [Daneză](guides/GUIDE_DA.md)

🇫🇮 [Finlandeza](guides/GUIDE_FI.md) · 🇳🇴 [Norvegiană](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Vietnameză](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Turcă](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Indoneziană](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Ceština](guides/GUIDE_CS.md) · 🇷🇴 [Româna](guides/GUIDE_RO.md) · 🇭🇺 [Maghiară](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovacă](guides/GUIDE_SK.md) · 🇭🇷 [Croată](guides/GUIDE_HR.md)

</details>

## Note de configurare

**Limba de răspuns.**Agentul răspunde în**estonian**implicit — adică este o
setare, nu o cerință a protocolului, iar nimic altceva despre SAIPEN nu este în estonian.
Protocolul, codul, commit-urile și fiecare document rămân în engleză la fiecare
valoare. Schimbați-l într-un singur loc: linia`reply_language:`de la începutul
[`saipen/STYLE.md`](saipen/STYLE.md). `et`estonian,`en`engleză,`ru`rusă,
`auto`alege din mesajul pe care l-ați trimis.

**Adaptorii.**Platforma nu este acoperită de injector(DeepSeek, Qwen, standalone
OpenAI, etc.)? Notele per-platformă se află în`extensions/adapters/`.

## Capture de ecran

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
