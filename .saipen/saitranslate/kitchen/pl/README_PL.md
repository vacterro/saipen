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

**Protokół kontynuacji dla agentów kodowania AI.**Pamięć projektu znajduje się w plikach
Markdown wewnątrz projektu(`.saipen/`), więc każdy kompatybilny agent chłodny —
bez historii rozmów, bez pamięci sesji — może działać`/saipen continue`, odczytać
zapisany`next_action`, i wznowić pracę bez pytania użytkownika, by ponownie wytłumaczyć
nic. Stan należy do projektu, a nie do pamięci jednego dostawcy modeli.

**Jedno polecenie do wznowienia. Stan w plikach zwykłych. Umowy sprawdzane przez maszynę.**

Repozytorium waliduje się samo przy każdym push; instalacja, stan, sprawdzenia i
odinstalacja jest lokalna — brak usługi w chmurze, brak demona, brak bazy danych.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.248.0** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [Core](saipen/CORE.md) | [Maintenance](saipen/MAINTENANCE.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) |MIT

**Szybkie klawisze:** `cc` kontynuuje kontekst projektu do konwergencji (wznawia bieżący cel, jeśli jest ustawiony), `sss` pokazuje stan bez dotykania kodu, a `ss` zapisuje punkt kontrolny i zatrzymuje się. [Zobacz pełną mapę 19 klawiszy](saipen/RFC.md#110-command-surface). Cyrylickie bliźniaki też działają: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

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

## Co pozostaje

Żywa pamięć projektu żyje w`.saipen/`— zwykłe pliki, które możesz przeczytać, porównać i
zatwierdzić obok kodu. Zimny agent odpowiada na pięć pytań z plików
samodzielnie:

|Plik / pole|Odpowiedzi|
|---|---|
| `STATE.md` |Co się aktualnie dzieje?(faza, aktywny bilet, tryb pracy, blokada) |
| `BOARD.md` |Jakie prace istnieją / są aktywne?(graf biletów: DOING, TODO, DONE, BLOCKED) |
| `LOG.md` |Dlaczego projekt osiągnął ten stan?(graf zdarzeń typu append-only) |
| `KNOWLEDGE/` |Jakie trwałe fakty projektowe muszą przetrwać sesje?|
| `next_action` (w`STATE.md`) |Jaka dokładnie akcja powinna być wykonana przez następnego agenta?|

To jest kontrakt punktu kontrolnego, nie sugestia projektowa:`saipen stop`i każdy
przejście biletu zapisuje pliki w ustalonym porządku, a wynik jest sprawdzany przez
walidatora. Nic nie jest przechowywane w bazie danych hostowanej, a nic nie jest utracone, gdy
sesja kończy się.

## Szybki start

**1. Zainstaluj raz na maszynę**— uczy Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity, oraz każdy ogólny`~/.agents/skills`czytnik(FreeBuff, itp.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`blok do instrukcji agenta
pliki, które już masz(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— tworząc kopie zapasowe każdego z nich do`.bak`pierwszego —
i kopiuje protokół do odpowiednich folderów umiejętności. Nic poza tymi
ścieżki, bez demona, bez wywołań sieciowych.</sub>

**2. Uruchom projekt**— otwórz agenta w swoim folderze, wpisz:

> `saipen set`

**Bez instalacji?**Wklej jedną linię do dowolnego agenta:

> Przeczytaj&lt;clone&gt;/saipen/BOOT.md najpierw(jądro startu zimnego), a następnie&lt;clone&gt;/saipen/INDEX.md +&lt;klonuj&gt;/saipen/STYLE.md i postępuj zgodnie z nimi.

**Zmieniłeś zdanie?**Jedno polecenie wraca do poprzedniego stanu:

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Usuwa dokładnie zaznaczony blok(pozostawiając resztę pliku bez zmian), zapisuje
a `.uninstalled.bak`wykonaj kopię zapasową i usuń folder z umiejętnościami.

## Dlaczego nie po prostu historia rozmów?

SAIPEN skupia się na konkretnym błędzie: agent kodowania AI, który zapomina wszystko
po zakończeniu sesji. Inne narzędzia i nawyki obejmują część tego problemu:

|Metoda|Do czego służy|Co nie przenosi|
|---|---|---|
|Historia rozmowy / pamięć modelu|Udogodnione, zero konfiguracji|Zależne od sesji i dostawcy; nie przechowywane razem z projektem, więc agent zimny nigdy go nie widzi|
|Statyczne`AGENTS.md`Plik / instrukcja|Trwałe, stałe zasady i konwencje|Nie reprezentuje samodzielnie stanu zadania w trakcie działania`next_action`, ani historii odzyskiwania|
|Śledziciel problemów / TODO|Zarządzanie zadaniami i backlogiem|Nie definiuje samodzielnie semantyki kontynuacji agenta — co musi przeczytać i wykonać zimny agent po wznowieniu|
| **SAIPEN** |Stan wykonania w czasie rzeczywistym, kolejka pracy, historia zdarzeń, trwała wiedza oraz maszynowo sprawdzalne reguły kontynuacji — w zwykłych plikach obok kodu|Nic; to kombinacja jest kontraktem|

Różnica nie polega na żadnym jednym pliku. Polega na tym, że SAIPEN wykonuje krok wznowienia
maszynowo sprawdzalne: pierwszym działaniem zimnego agenta po`/saipen continue`jest
określone przez zapisany`next_action`i weryfikowane przez walidatora, a nie
odzyskiwane z pamięci.

## Dowody inżynierskie

SAIPEN łączy normatywny protokół w postaci zwykłych plików z wykonywalnym, skierowanym na awarie
sprawdzania. Repozytorium demonstruje projekt protokołu/maszyny stanów, Python
narzędzia, stan oparty na schemacie, rozumowanie o odzyskiwaniu, testy regresyjne,
granice przepływu pracy wielu agentów oraz dyscyplinę specyfikacji.

- **Zaprojektowany kontrakt.** [SPEC.md](SPEC.md)definiuje model kontynuacji oparty na plikach
i stabilny kontrakt na dysku;[CORE.md](saipen/CORE.md)
oraz[MAINTENANCE.md](saipen/MAINTENANCE.md)opisuje bieżące normatywne zachowanie.
- **Stan sprawdzany przez maszynę.**Wersja kanoniczna tylko z stdlib
  [walidator](tools/validate.py)czyta aktualny
  [stan schematu](extensions/schemas/state.schema.json)i sprawdza przejścia fazowe,
zależności biletów, łącza w grafie zdarzeń, niezmienniki międzydokumentowe
wewnętrzne, możliwości i stan odzyskiwania.
- **Zakres pokrycia awarii.** [CONFORMANCE.md](saipen/CONFORMANCE.md)mapuje
wymagania na[ustawienia scenariuszy](tests/scenarios/); the
  [uruchamiający scenariusze](tools/run_scenarios.py)wykonuje testy strukturalne na podstawie wyników (przechodzenie / nieprzechodzenie)
obejmujące uszkodzony stan odzyskiwania, nieprawidłowe przejścia, cykle zależności oraz
ograniczenia tylko do odczytu.
- **Kontrola regresji.** [audit_checks.py](tools/audit_checks.py)modyfikuje
znane dobre kopie i udowadnia, że sprawdzenia walidatora mogą nadal zakończyć się niepowodzeniem, zamiast
traktowania niezmiennego zielonego wyniku jako dowodu.
- **Warstwa wykonywalna.** [saipen.py](tools/saipen.py)dostarcza zapisanej stanu
operacje;[bootstrap/](bootstrap/)przechowuje instalację, deinstalację i eksport
pomocniki z opcjonalnym[instalatorem hooka pre-commit](tools/install_hook.py).
- **Jawne kompromisy.**Podstawowy stan protokołu to zwykłe pliki bez zależności uruchomieniowej
walidacja kanoniczna i narzędzia CLI wymagają Pythona, ale korzystają tylko z
jego standardowej biblioteki i nie wymagają`pip`instalacji.

## Architektura

Trzy warstwy, ściśle jednostronne zależności:

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Jądro nie zależy od utrzymania: z wyłączonym autonomicznym ewoluowaniem, SAIPEN
jest nadal pełnym protokołem kontynuacji — zimny agent nadal wznowia się.

- **Maszyna stanów jądra** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Autonomiczne utrzymanie**— plansza zatrzymana(nic funkcjonalnego w`## TODO`,
nic w`## DOING`)i nie`BLOCKED`? Auto-przejścia`HUNT` (skanuj błędy)
  → `ADD` (ewolucja funkcji) → `HUNT`, zero questions asked. A session sitting at
  `BLOCKED`nigdy nie auto-huntuje
  ([Konserwacja § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Tryb celowy** — `/saipen goal <objective>`obraca planszę i uruchamia
cel do przodu przez VERIFY/REVIEW, wpadając w autonomiczną konserwację
aż do momentu, gdy zostanie wywołane zasada zakończenia lub osiągnięto limit przebiegów(3 fale / 20 biletów,
następnie punkty kontrolne i raport) ([Konserwacja § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Wzmocnienie**— partia wejścia jest analizowana na jednostkowe bilety
  (CORE § 1.8); kontynuacja brudnego drzewa zachowuje niezaakceptowane zmiany(CORE § 1.5);
wartości podobne do sekretów są usuwane z logów(`sk-***`) (CORE § 1.2).

## Powszechne polecenia

Powszechne punkty wejścia; cała aktualna powierzchnia znajduje się w
[Core § 1.10](saipen/CORE.md#110-command-surface).

|Polecenie|Wykonuje|
|---|---|
| `/saipen set` |Zaadoptuj projekt: utwórz`.saipen/`stan|
| `/saipen continue` |Wznowienie z zapisanego stanu projektu — bez ponownego briefingu|
| `/saipen plan` |Przekształcenie żądania lub surowego backlogu w bilety|
| `/saipen goal <text>` |Autonomiczne wykonanie fali wobec nowego celu|
| `/saipen validate` |Uruchomienie sprawdzeń zgodności|
| `/saipen status` |Tylko do odczytu: etap, bilety, blokery, przestarzałość|
| `/saipen stop` |Zapis punktu kontrolnego i zatrzymanie|

<details>
<summary><b>More commands</b></summary>

|Komenda|Wykonuje|
|---|---|
| `/saipen hunt` |Wymuś teraz przegląd błędów/ulepszeń|
| `/saipen markhunt` |Suchy, nieograniczony audit — rejestruje wyniki, nie naprawia niczego|
| `/saipen ship` |Wzorce wypuszczenia; commit, tag i push, gdy dozwolone|
| `/saipen clean` |Wyczyszczenie płyty i stanu|
| `/saipen translate` |Oddzielna fabryka tłumaczeń|
| `/saipen prepare` / `/saipen collect` |Praca nad pakietem do przekazania / integracja gotowego pakietu|
| `/saipen test` |Uruchom deklarowany zestaw testów, raportuj tylko|
| `/saipen crew` |Obieg załogi w ustalonym porządku(szukaj → odtwórz → przyjmij → zbuduj → przetłumacz → dokumentuj → wyslij) |
| `/saipen improve` |Audit metakontroli poprawek protokołu|
| `/saipen sub ...` |Utwórz/zaadoptuj tylko do odczytu podagentów|

**Pakiet kluczy.** `ee`/`qq`przygotuj kompletny pakiet tłumaczenia/wiki bez
integracji;`eee`/`qqq`akceptuj tylko gotowe pakiety, a następnie zintegruj, zweryfikuj,
przeglądaj i wypchnij.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)przechodzi przez całość
wbudowanego zespołu w ustalonym porządku — czujniki(saihunt, saitest, saipython, saiui),
producentów(saitranslate, saiwiki)i Core jako jedynego głównego pisarza —
aż do kolejnego nowego przejścia, które nie ma niczego realnego do zmiany. Dodaje dokładnie jeden
mechanizm własny: trwały cel orkiestracji(`execution_intent:
zbiegać się` with `cel_zbieżności: zespół`)który czyni obwód wznowialny i
wyprowadzalny z wypowiedzi w przypadku awarii.`saipen crew --dry-run --json`wyprowadza
obwód tylko do odczytu;`bootstrap/saipen_crew.*`jest OPCJONALNYM ręcznym
pomocnikiem wielkościeniowym, nigdy nie to co`saipen crew`oznacza. Zobacz
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Co SAIPEN nie jest

- **Modelem LLM lub modelem**— jest to protokół, którego agentowie się śledzą, a nie inteligencją.
- **IDE lub bazą danych pamięci hostowaną**— stan to zwykłe pliki w Twoim projekcie;
nic nie jest hostowane.
- **Zamiennik Git**— Git nadal posiada historię wersji; zatwierdź swoje
  `.saipen/`tak jak każdy inny kod.
- **Konsensus rozproszony**— zobacz granicę współbieżności poniżej.
- **Gwarancja, że LLM podejmie poprawne decyzje inżynierskie**— on
zmniejsza utratę kontekstu i odchylenie zachowania; nie czyni agentów stochastycznych
nieomylnymi.

Zadaniem SAIPEN jest kontynuacja/umowa stanu plus walidacja i narzędzia —
przekazanie następnemu agentowi punktu wyjścia sprawdzanego przez maszynę, a nie magii.

**Granica współbieżności.**Zapisywane mutacje stanu(SAIOPS)użyj
blokady systemowej ograniczonej do projektu i dziennika odzyskiwania([OPS § 5](saipen/OPS.md#5-locks)).
Zwykłe edycje projektu i niepołączeni autorzy są poza tą blokadą. SAIPEN
nie jest konsensusem rozproszonym, więc niepołączeni autorzy wymagają zewnętrznej
koordynacji([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Ecosystem

|Projekt|Związek z SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Lokalne centrum sterowania w systemie Windows dla projektów SAIPEN — automatycznie wykrywa`.saipen/`przestrzenie robocze, wizualizuje stan i wyniki weryfikacji zgodności, zarządza zgłoszeniami oraz uruchamia AI CLIs. To towarzyszące narzędzie, nie autorytet.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Pochodna CodeNomad w dółstronie, która integruje SAIPEN: wstrzykuje`BOOT.md`/`STYLE.md`do uruchomień OpenCode, uwidacznia skróty SAIPEN i widoki stanu projektu oraz dodaje stałą kolejka promptów.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Przenośny Windowsowy notatnik i menedżer fragmentów kodu, który automatycznie wykrywa`.saipen/`foldery i dodaje tylko do odczytu widok STATE/BOARD/LOG.|

## Dokumentacja

|Dokument|Co to jest|
|---|---|
| [SPEC.md](SPEC.md) |Formalna architektura, cele projektowe, test litmusowy|
| [CORE.md](saipen/CORE.md) |Normatywny kontynuacja, maszyna stanów i kontrakt komendy|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Autonomiczna konserwacja i tryb celowy|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Wymagania wykonywalne/behawioralne i reguły walidatora|
| [GUIDE.md](GUIDE.md) |Humanistyczny tutorial|
| [RFC.md](saipen/RFC.md) |Przekierowanie zgodności do rozdzielonych dokumentów normatywnych|
| [STYLE.md](saipen/STYLE.md) |Styl i głos komunikacji agenta|
| [UI.md](saipen/UI.md) |Zasady projektowania klasycznych, złotych interfejsów użytkownika|
|Brochure|Prezentacja — broszura[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Angielski](guides/GUIDE_EN.md) · 🇪🇪 [Eesti](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Niemiecki](guides/GUIDE_DE.md) · 🇫🇷 [Francuski](guides/GUIDE_FR.md) · 🇪🇸 [Hiszpański](guides/GUIDE_ES.md) · 🇮🇹 [Włoski](guides/GUIDE_IT.md)

🇵🇹 [Portugalski](guides/GUIDE_PT.md) · 🇳🇱 [Holenderski](guides/GUIDE_NL.md) · 🇵🇱 [Polski](guides/GUIDE_PL.md) · 🇸🇪 [Szwedzki](guides/GUIDE_SV.md) · 🇩🇰 [Duński](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Uwagi dotyczące konfiguracji

**Język odpowiedzi.**Agent odpowiada w**estryjskim**domyślnie — to jest
ustawienie, a nie wymóg protokołu, i nic więcej w SAIPEN nie jest estryjskie.
Protokół, kod, commity i każdy dokument pozostają w języku angielskim przy każdym
wartościowaniu. Zmienia się to w jednym miejscu: w`reply_language:`linii na wierzchu
[`saipen/STYLE.md`](saipen/STYLE.md). `et`estryjskim,`en`angielskim,`ru`rosyjskim,
`auto`wybiera się z wiadomości, którą wysłałeś.

**Adapterzy.**Platforma nie objęta przez wstrzykiwacz(DeepSeek, Qwen, standalone
OpenAI, itp.)? Uwagi specyficzne dla platformy znajdują się w`extensions/adapters/`.

## Zrzuty ekranu

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
