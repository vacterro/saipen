# Współtworzenie SAIPEN

SAIPEN to przede wszystkim specyfikacja, a dopiero w drugiej kolejności implementacja. Większość wkładów
to zmiany w `saipen/RFC.md`, plikach `phases/*.md` lub narzędziach
zgodności w `tests/` -- nie w kodzie aplikacji.

## Zanim zaproponujesz zmianę

Przeprowadź [Test Litmus SAIPEN](SPEC.md#the-saipen-litmus-test) dla swojego
pomysłu:
1. Czy sprawia, że przejście między agentami jest bardziej niezawodne?
2. Czy ujednolica zachowanie różnych modeli?
3. Czy zmniejsza prawdopodobieństwo utraty kontekstu?

Jeśli odpowiedź brzmi "nie" na co najmniej dwa z nich, twój pomysł jest poza zakresem dla tego
protokołu, bez względu na to, jak bardzo mógłby być przydatny gdzie indziej.

## Zgłaszanie luki

Otwórz zgłoszenie opisujące:
- w którym pliku/sekcji znajduje się luka (RFC.md, dokument fazy, schemat, test)
- konkretny dowód (cytat, polecenie i jego wynik, scenariusz, gdzie
  obecne zachowanie się łamie)
- czego oczekiwałbyś w zamian

Niejasne raporty ("to wydaje się dziwne") są trudniejsze do podjęcia niż konkretny
`grep`/reprodukcja. Zobacz szablon zgłoszenia błędu, aby dowiedzieć się, jaki kształt powinno
to przybrać.

## Wprowadzanie zmiany

1. Przeczytaj `saipen/RFC.md` i odpowiednie pliki `phases/*.md` w całości przed
   edycją -- większość pozornie brakujących elementów okazuje się już ujęta gdzie indziej,
   lub celowo ma określony zakres z udokumentowanego powodu.
2. Sprawdź `CHANGELOG.md` i `.saipen/KNOWLEDGE/decisions.md` w poszukiwaniu dotychczasowego stanu sztuki.
   Nie otwieraj po cichu ponownie decyzji, która została już podjęta i odrzucona --
   jeśli masz nowe dowody na to, że wcześniejsze odrzucenie było błędem, powiedz to wyraźnie
   w opisie PR.
3. Każda zmiana normatywna (MUST/MUST NOT/SHOULD) wymaga wpisu w `CHANGELOG.md`
   i, tam gdzie to praktyczne, pokrycia w `tests/validate.sh` +
   `tests/validate.ps1` (obie platformy) lub testu (fixture) w
   `tests/scenarios/`.
4. Uruchom kanoniczny walidator przed otwarciem PR:
   ```bash
   python tools/validate.py
   ```
   To jest ten, który ma znaczenie -- sprawdza `STATE.md` względem `extensions/schemas/state.schema.json`, przechodzi przez graf zdarzeń `LOG.md` w poprzek zapieczętowanych segmentów oraz weryfikuje manifest wykonawczy i okablowanie wstrzykiwacza. `tests/validate.sh` / `validate.ps1` to **zamrożone przenośne minimum** dla hostów bez Pythona (jest to napisane na górze każdego pliku): mniej kontroli, utrzymywane tylko po to, aby host bez Pythona nie został z niczym. Uruchom je również, jeśli twoja zmiana dotyczy któregokolwiek z nich, ale nigdy *zamiast* -- samo przejście minimum dowodzi znacznie mniej, niż się wydaje. CI uruchamia kanoniczny walidator przy każdym pushu i PR, niezależnie od tego (`.github/workflows/validate.yml`).
5. Podnieś `VERSION` zgodnie ze schematem w `phases/ship.md` (patch dla
   wyjaśnień tylko w dokumentacji, minor dla nowych zachowań normatywnych, major dla łamiących
   zmian kontraktu) i utrzymuj odznakę wersji w `README.md` zsynchronizowaną --
   `tests/validate.sh`/`.ps1` sprawdzają to automatycznie po uruchomieniu z
   klonu tego repozytorium.

## Styl

- Dokumenty protokołu i faz: zwięzłe, słowa kluczowe RFC-2119 tam, gdzie mają znaczenie, żadnych
  wypełniaczy. Zobacz `saipen/STYLE.md`.
- Wszystko w tym pliku, wiadomości z commitów, komentarze w kodzie i
  CHANGELOG: proste i profesjonalne. Własne głosy czatu/LOG projektu
  (`saipen/STYLE.md`) nie mają zastosowania do artefaktów.

## Co jest poza zakresem

- Przekształcenie SAIPEN w rozproszony system konsensusu. Zobacz
  sekcję Concurrency & Distribution Boundaries w `SPEC.md`.
- Gramatyka markerów LOG analizowalna maszynowo wykraczająca poza istniejący szkielet.
  `LOG.md` pozostaje prozą ułożoną wokół ustalonego kształtu.
- Polecenie `saipen doctor` lub podobne zbędne w świetle `saipen validate` +
  `saipen status`.

Każde z nich było już wcześniej proponowane i oceniane; ich ponowne otwarcie wymaga
nowych dowodów, a nie tylko ponownego zapytania.
