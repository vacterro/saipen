<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Naklejka" width="200"/>
</p>

# SAIPEN

**Protokół kontynuacji dla agentów programujących AI.** Trwała pamięć projektu w
zwykłym markdownie, dzięki czemu zimny agent bez historii czatu uruchamia `/saipen continue`
i wznawia pracę w mniej niż minutę -- bez ponownego wprowadzania, dowolny dostawca, dowolny dzień.

**Jeden nakaz. Zero amnezji.**

**Szybkie klawisze:** `cc` kontynuuje aktywny Goal Mode, `sss` pokazuje stan bez dotykania kodu, a `ss` zapisuje punkt kontrolny i zatrzymuje się. [Zobacz pełną mapę 13 klawiszy](saipen/RFC.md#110-command-surface). Cyrylickie bliźniaki też działają: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Język odpowiedzi.** Agent domyślnie odpowiada **po estońsku** — to ustawienie, a nie dziwactwo, i nic więcej w SAIPEN nie jest estońskie. Zmienia się to w jednym miejscu: linia `reply_language:` na początku [`saipen/STYLE.md`](saipen/STYLE.md). `et` estoński, `en` angielski, `ru` rosyjski, `auto` wybiera na podstawie języka Twojej wiadomości. Protokół, kod, commity i wszystkie dokumenty pozostają angielskie przy każdej wartości.

**v7.190.0** | [Spec](SPEC.md) | [Przewodnik](GUIDE.md) | [RFC](saipen/RFC.md) | [Styl](saipen/STYLE.md) | [UI](saipen/UI.md) | [Zgodność](saipen/CONFORMANCE.md) | zwykły markdown | zero zależności | MIT

```text
Użytkownik ->  /saipen continue
Agent      ->  czyta STATE ("Co robię w tej chwili?")
Agent      ->  czyta BOARD ("Jakie zadanie podejmuję?")
Agent      ->  czyta next_action (wykonuje polecenie)
Agent      ->  Pracuje.
```

### Stan Projektu > Pamięć Modelu
Pamięć żyje w projekcie, nie w głowie modelu. `Projekt -> Pamięć -> LLM` staje się `Projekt -> Stan SAIPEN -> LLM`.

### Kluczowa Logika Protokółu i Gwarancje
- **Główna Maszyna Stanów**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Autonomia Bez Promptów**: Brak otwartych zadań do wykonania? Automatyczne przejście w pętlę `HUNT` (skanowanie błędów) → `ADD` (rozwój funkcji) → `HUNT`. Zero pytań.
- **Jawne Wyzwalacze**: `/saipen clean` (czyszczenie repo), `/saipen translate` (izolowana fabryka `.saipen/saitranslate/`), `/saipen markhunt` (suchy nieograniczony audyt, tylko zapisuje), `/saipen prepare` (pakowanie pracy do przekazania), `/saipen validate` (sprawdzenie zgodności), `/saipen goal` (autonomiczne wykonanie fali). Meta/kontrola: `/saipen status` (raport tylko do odczytu), `/saipen stop` (punkt kontrolny i zatrzymanie). Pełna lista: RFC.md § 1.10.
- **Ścisła Niezawodność**: Przetwarzanie wsadowe wejścia (chirurgiczne zadania 1-po-1), przejmowanie brudnego drzewa (nigdy nie usuwa niezatwierdzonej pracy), redagowanie sekretów (`sk-***`).

## Projekty Napędzane Przez SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Wysokowydajne narzędzie do zarządzania promptami natywnie zintegrowane z protokołem pamięci SAIPEN.

## Dwie Warstwy

| Warstwa | Wymagana | Cel |
|---|---|---|
| **Rdzeń (Core)** | ✅ | Bezpieczne kontynuowanie pracy |
| **Utrzymanie (Maintenance)** | Na Rdzeniu | Rozwijanie oprogramowania bez przydzielania zadań |

**Zautomatyzowana Ewolucja.** Brak otwartych zadań do wykonania, wpisz `/saipen`: `HUNT` audytuje pod kątem błędów, martwego kodu, usuwających się testów. Czysto? `ADD` buduje kolejną oczywistą brakującą funkcjonalność, weryfikuje ją, ponownie prowadzi `HUNT`. Produkt jest dojrzały -> zatrzymuje się z wdziękiem.

**Tryb GOAL.** `/saipen goal <czego chcesz>` przestawia tablicę (stare zadania zdegradowane, nigdy nieskasowane) i prowadzi nowy cel do przodu -- bez "czy mam kontynuować?" między zadaniami, VERIFY/REVIEW nigdy nie pomijane. SHIP automatycznie wysyła (push) do istniejącego zdalnego repozytorium; fabrycznie nowe repozytorium wciąż pyta raz. Wysyłka celu to również nie koniec -- wpada bezpośrednio w autonomiczną konserwację HUNT/ADD, aż produkt stanie się dojrzały, zablokowany lub bieg osiągnie limit (3 fale / 20 zadań, potem zapisuje punkt kontrolny i raportuje).

## Szybki Start

**1. Zainstaluj raz na maszynie** -- uczy Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex i dowolny ogolny czytnik ~/.agents/skills (FreeBuff, itp.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Rozpocznij projekt** -- otwórz agenta w swoim folderze, wpisz:
> `saipen set`

Brak instalacji? Wklej jedną linię do dowolnego agenta:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Platforma nie znajduje się na powyższej liście (DeepSeek, Qwen, samodzielne OpenAI itp.)?
Uwagi dla poszczególnych platform znajdują się w `extensions/adapters/`.

## Linki do Dokumentacji i Specyfikacji
- **[SPEC.md](SPEC.md)** -- formalna architektura, cele projektowe, test lakmusowy.
- **[RFC.md](saipen/RFC.md)** -- specyfikacja normatywna wykonywana przez agentów.
- **[GUIDE.md](GUIDE.md)** -- samouczek dla ludzi i przewodniki ELI5:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- styl komunikacji agenta i definicja głosu.
- **[UI.md](saipen/UI.md)** -- wytyczne projektowe UI Vintage Golden.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- scenariusze testów behawioralnych i reguły walidatora.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Pieczęć" width="120"/>
</p>

## ## Zrzuty ekranu

<details>
<summary>Kliknij, aby rozwinąć</summary>

<img src="assets/screenshot-freebuff.png" alt="Instrukcje agenta FreeBuff" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set w nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="Zrzut ekranu saipen 2026-08-01" width="600"/>

</details>

<!-- source-digest: README.md sha256:951d8044313a6456 -->
