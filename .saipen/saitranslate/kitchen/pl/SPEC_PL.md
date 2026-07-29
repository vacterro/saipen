# Specyfikacja SAIPEN

## Abstrakt
**Cel Projektowy #1: Zimny agent bez historii czatu musi być w stanie wykonać `/saipen continue` i wznowić produktywną pracę w ciągu minuty, bez pytania użytkownika o powtórzenie kontekstu.**

SAIPEN gwarantuje, że jakikolwiek kompatybilny agent AI może bezpiecznie kontynuować każdy projekt bez konieczności ponownego instruowania. Jest to ABI (Application Binary Interface) dla inżynieryjnych agentów AI — warstwa kompatybilności, która rozwiązuje problem amnezji. Niezależnie od tego, czy używasz Claude dzisiaj, Gemini jutro, a GPT pojutrze, wszystkie będą działać na tym samym stanie projektu bez wymagania od ciebie ponownego podawania kontekstu.

### Główna Filozofia: Stan Projektu > Pamięć Modelu
Pamięć powinna żyć blisko kodu, a nie wewnątrz głowy innego modelu. SAIPEN zmienia paradygmat z `Projekt -> Pamięć -> LLM` na `Projekt -> Stan SAIPEN -> LLM`. Pamięć należy do projektu.

U swych podstaw, SAIPEN używa przenośnego, opartego na plikach protokołu kontynuacji dla agentów LLM. Implementacje MOGĄ się różnić. Kontrakt dyskowy MUSI pozostać stabilny. Wszystko w tym protokole istnieje po to, by służyć Testowi Kontynuacji (Continuation Test).

SAIPEN jest ewolucyjny, nie kreatywny. Jego celem jest ukończenie oprogramowania, a nie odkrywanie go na nowo. ADD rozszerza istniejące wzorce projektowe, konwencje branżowe i oczywistą symetrię funkcji.

- **`STATE`**: Istnieje by odpowiedzieć *"Co mam zrobić w tej chwili?"*
- **`BOARD`**: Istnieje by odpowiedzieć *"Jakie zadanie podejmuję?"*
- **`LOG`**: Istnieje by odpowiedzieć *"Dlaczego doszliśmy do tego punktu?"*
- **`KNOWLEDGE`**: Istnieje by odpowiedzieć *"Jaka jest trwała prawda tego projektu?"*
- **`next_action`**: Serce SAIPEN. Odpowiada *"Jakie dokładnie polecenie mam wykonać w tej sekundzie, aby wznowić pracę?"*

## Test Litmus SAIPEN

Każda proponowana zmiana lub nowy pomysł dla protokołu MUSI przejść przez następujące trzy pytania:
1. Czy sprawia, że przejście między agentami jest bardziej niezawodne?
2. Czy ujednolica zachowanie różnych modeli?
3. Czy zmniejsza prawdopodobieństwo utraty kontekstu?

Jeśli odpowiedź brzmi "nie" na co najmniej dwa z tych pytań, pomysł jest odrzucany. SAIPEN przedkłada dyscyplinę, powtarzalność i niezawodność nad nowości.

## Architektura

Protokół jest ściśle normatywny. SAIPEN dzieli się konceptualnie na dwie warstwy: **Core** (Rdzeń) i **Maintenance** (Utrzymanie). 
- **Warstwa Core** gwarantuje bezpieczną, niezależną od dostawcy kontynuację zadań. 
- **Warstwa Maintenance** to model autonomicznej ewolucji oprogramowania zbudowany na wierzchu Core.

Pod dwiema warstwami SAIPEN oddziela trzy zagadnienia, które nigdy się nie mieszają:
**poprawność i kontynuacja** (Core -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, negocjacja
możliwości, punkty kontrolne - checkpointing), **nieobsługiwana ewolucja** (Maintenance -- `HUNT`/`ADD`/`CLEAN`,
w pełni funkcjonalna pod zwykłym ustawieniem domyślnym `saipen`/`saipen continue`), oraz **przepustowość**
(Goal Mode, Subagenci -- oba jawnie jako opcja do włączenia, §1.3/§2.4). Wyłącz Goal Mode:
protokół pozostaje niezmieniony, jedno zadanie na raz. Wyłącz Subagentów: `HUNT` uruchamia te same
sześć kategorii sekwencyjnie, z tym samym rezultatem. Użyj samego Core, bez warstwy Maintenance
w ogóle: to wciąż działa -- zimny agent wciąż wznawia pracę poprawnie. Każda warstwa buduje na
tej pod nią, przy czym odwrotność nigdy nie jest prawdą; nic z góry strumienia nie zależy od tego,
czy funkcja na dole strumienia istnieje.

```text
saipen/
  RFC.md                    normatywna specyfikacja (podzielona na Core i Maintenance)
  CONFORMANCE.md             wektory samokontroli + tabela pokrycia scenariuszy
  SKILL.md                  cienki punkt wejścia dla platform czytających umiejętności
  STYLE.md                  głosy: czat, LOG.md, artefakty
  UI.md                     specyfikacja UI Vintage Golden (obowiązkowa dla prac nad UI)
  BOOT.md                   ~jądro cold-start: szybka ścieżka, której potrzebuje
                             goły `continue`, zanim którekolwiek z powyższych zostanie załadowane
  phases/                   ściśle maszyna stanów -- 16 dokumentów, jeden na
                             każdą wartość wyliczenia RFC § 1.6 (sprawdzane
                             maszynowo w obu kierunkach przez tools/validate.py)
    [Core Phases]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Maintenance Phases]
    hunt.md / markhunt.md / add.md / clean.md / translate.md

    [Infrastructure]
    prepare.md              przygotuj pracę do przekazania następnemu agentowi
    validate.md             testowanie zgodności

extensions/                 <- WARSTWA ADAPTACYJNA
  adapters/                 mostki instrukcji na poszczególne modele, dla platform, których
                             injector nie wykrywa automatycznie (README.md wskazuje tutaj)
  schemas/                  state.schema.json jest czytany maszynowo przez tools/validate.py
                             (jedyne źródło prawdy dla kształtu STATE); schematy board/log
                             pozostają tylko referencyjne (patrz schemas/README.md)
  templates/                świeży szablon `.saipen/`
  security/                 PRZYKŁADOWY hook do skopiowania do projektu (RFC § 1.9, podpina się do VERIFY)
  performance/              PRZYKŁADOWY hook do skopiowania do projektu (RFC § 1.9, podpina się do REVIEW)
  subs/                     PRZYKŁADOWI read-only subagenci badawczy (RFC § 1.9) -- własny
                             STATE/BOARD/LOG na subagenta, znaleziska tylko via OUTBOX,
                             nigdy druga ścieżka zapisu do projektu

bootstrap/                  <- INSTALACJA/EKSPORT/ODINSTALOWANIE, jedna maszyna na raz
  inject.ps1 / .sh          instaluje blok SAIPEN + kopie umiejętności (Quick Start z README)
  uninstall.ps1 / .sh       odwraca inject -- usuwa bloki + kopie umiejętności
  export.ps1 / .sh          archiwizuje projektowy `.saipen/` jako backup
  saipen_crew.bat / .sh     otwiera układ 3-okienny crew (bonus, extensions/subs/crew.md)

tools/                      <- KANONICZNY WALIDATOR & NARZĘDZIA REPOZYTORIUM
  validate.py               kanoniczny walidator zgodności (stdlib Python, zero
                             instalacji; waliduje STATE przeciwko state.schema.json
                             bezpośrednio, plus sprawdzenia grafów, których para skryptów powłoki nie potrafi)
  install_hook.py           instaluje pre-commit hook uruchamiający validate.py
  uninstall_hook.py         usuwa dokładnie ten hook (przywraca ewentualny wcześniejszy)

tests/                      <- WARSTWA ZGODNOŚCI
  validate.ps1 / .sh        zamrożona przenośna baza dla hostów bez Pythona --
                             nowe sprawdziany lądują tylko w tools/validate.py
  scenarios/                makiety stanów (recovery po awarii, konflikty rezerwacji, itd.)
```

## Dwukierunkowa Negocjacja Możliwości
Agenci nie deklarują po prostu co potrafią zrobić; protokół wymaga tego, co jest niezbędne.
Projekt definiuje `requires: [filesystem, git, shell, python]` w swoim stanie. Agent weryfikuje swojego hosta pod kątem wymagań i blokuje się w odpowiednim `mode` (np. `full`, `read-only`).

## Rejestrowanie Zdarzeń Oparte na Grafach
Logi w SAIPEN to nie linijki tekstu. Tworzą one acykliczny graf decyzji używający ID Zdarzeń (`E-001`). To pozwala na złożone rozgałęzienia, łączenie agentów i precyzyjne ścieżki audytu.

## Architektoniczne Rejestry Decyzji (ADR)
Przemijające logi zdarzeń nie mieszczą stałej wiedzy. SAIPEN wymaga, by strukturalne decyzje architektoniczne były utrwalane jako pliki ADR (np. `KNOWLEDGE/ADR-001-use-sqlite.md`).

## Współbieżność & Granice Dystrybucji
SAIPEN zapewnia integralność stanu poprzez rezerwacje oparte na plikach (`owner`, `claim_time`) oraz sekwencyjne grafy (`LOG.md`). Jednakże, **SAIPEN jest protokołem stanu, nie rozproszonym algorytmem konsensusu.**
- **Lokalny/Dzielony System Plików**: Rozwiązywanie konfliktów opiera się na atomowych zapisach systemu plików ("pierwszy commit wygrywa").
- **Środowiska Sieciowe/Rozproszone**: Jeśli agenci operują na rozłączonych maszynach bez synchronizacji plików w czasie rzeczywistym, wystąpią warunki wyścigu na rezerwacjach `BOARD.md`. W środowiskach wysoce rozproszonych kontrakt na dysku SAIPEN MUSI pozostać stabilny -- sam stan projektu wciąż nieustannie mutuje, poprzez własne reguły SAIPEN (punkty kontrolne z § 1.5), ale nigdy nie zmienia się kształt protokołu, który te reguły realizują.


<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
