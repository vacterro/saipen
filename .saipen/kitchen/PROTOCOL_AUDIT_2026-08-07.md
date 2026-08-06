## Логические дыры SAIPEN — аудит 2026-08-07

### 1. RFC-ссылки указывают на несуществующий файл
Все документы ссылаются "RFC § X.Y", но `RFC.md` — 3-строчный стаб.
Агент должен понять: §1.X → CORE.md, §2.X → MAINTENANCE.md.
Слабая модель откроет RFC.md, увидит стаб, и либо зависнет, либо прочитает оба файла целиком (нарушение lazy-load).
**Фикс:** везде заменить `RFC § 1.X` → `CORE.md § 1.X`, `RFC § 2.X` → `MAINTENANCE.md § 2.X`.
Или в INDEX.md строкой: "RFC § N ссылается на CORE.md (N=1.x) или MAINTENANCE.md (N=2.x)".

### 2. BOOT.md дважды повторяет STYLE.md контракт
Шаг 1: "Read STYLE.md before any output."
Конец файла: "Chat voice & compression" — снова те же hard bans, preambles, etc.
Правило протокола: "не рестейтить правило" (CORE.md §1.1). Две копии дрифтуют.
**Фикс:** удалить секцию "Chat voice & compression" из BOOT.md. Оставить только шаг 1.
Там же: "The operative contract is repeated below" — убрать эту фразу, больше нигде не repeated.

### 3. saipen_home с обратными слешами Windows не парсится
`STATE.md` хранит `saipen_home: "V:\\\\___VAC\\\\..."`.
Агент читает YAML, видит `\\`, интерпретирует как экранированный бэкслеш → ломается путь при `Path()`.
BOOT.md шаг 8: `<saipen_home>/phases/<phase>.md` — на Windows с прямыми слешами не работает без нормализации.
**Фикс:** в BOOT.md шаг 8 добавить: "Normalise the path for the host OS before resolving."

### 4. "OPEN § 1.10" не говорит КАКОЙ файл открыть
BOOT.md шаг 7: "OPEN § 1.10 and read the row."
Агент не знает, в каком файле §1.10. INDEX.md говорит не читать CORE.md слепо.
**Фикс:** "OPEN § 1.10 in CORE.md and read the row."

### 5. `task: none` валидатор WARN без контекста
`STATE.md` с `task: none` в SCOUT/BUILD/VERIFY/REVIEW/SHIP даёт WARN.
Но в PLAN/INIT/BLOCKED/DONE `task: none` — правильно.
Валидатор выдаёт одинаковый WARN для всех.
Агент видит WARN, пытается "починить" → ломает правильное состояние.
**Фикс:** валидатор должен WARN только для ticket-bearing фаз (SCOUT/BUILD/VERIFY/REVIEW/SHIP).

### 6. Phase doc load error — позднее обнаружение
BOOT.md шаг 8: "Load the phase doc from `<saipen_home>/phases/<phase>.md`."
Если saipen_home мёртв — агент узнает только когда ВХОДИТ в первую фазу, не при загрузке.
А до этого уже прочитал STATE/BOARD/LOG, проверил STYLE.md, сделал checkpoint.
**Фикс:** BOOT.md шаг 2: после чтения STATE.md проверить `saipen_home` на существование. Мёртв → сразу BLOCKED.

### 7. `ccc` shortcut = undefined command surface entry
`ccc` → `saipen continue` then `saipen ship`.
`saipen continue` определён в §1.10 (строка 299). OK.
Но слабая модель читает таблицу shortcuts (строка 325-341) ДО того как дочитала §1.10 до строки 299 (таблица раньше).
Видит `ccc → saipen continue` → ищет в command surface → не находит (потому что continue определён ПОСЛЕ таблицы команд).
**Фикс:** переместить определение `saipen continue` (строка 299) ДО таблицы shortcuts (строка 323).

### 8. LOG→BOARD→STATE write order создаёт окно паники
Checkpoint: LOG пишется ПЕРВЫМ, STATE ПОСЛЕДНИМ.
После LOG: работа записана. После BOARD: тикет обновлён. STATE ещё старый.
Агент крашится между LOG и STATE. Recovery видит LOG новее STATE → rebuild.
Но слабый агент, делающий ручную инспекцию: "LOG says DONE but STATE says BUILD — corruption!"
**Фикс:** в BOOT.md шаг 3 добавить: "LOG ahead of STATE after a crash is the NORMAL recovery condition (§ 1.5), not corruption."

### 9. STYLE.md `reply_language: et` как дефолт
Дефолт — эстонский. 99% пользователей говорят на английском/русском.
Слабый агент должен парсить YAML, найти `reply_language:`, прочитать значение, obey.
Но BOOT.md шаг 1 говорит "Read STYLE.md before any output" — агент может ответить на английском ДО прочтения, если платформа уже инжектировала system prompt.
**Фикс:** OK как есть. STYLE.md — обязательное чтение до первого токена. Дрифт на платформе — не проблема протокола.

### 10. Две секции "BLOCKED" с одинаковым именем но разным смыслом
`STATE.phase: BLOCKED` (сессия заблокирована) vs `## BLOCKED` (тикет заблокирован на доске).
Переходная таблица §1.6 говорит `-> BLOCKED` в каждой строке.
Слабый агент читает "BLOCKED" → думает про тикет, а не про сессию.
**Фикс:** в таблице переходов заменить `BLOCKED` на `SESSION_BLOCKED` или добавить сноску: "every `BLOCKED` in this table means STATE.phase: BLOCKED, not ## BLOCKED ticket."

### 11. BOOT.md шаг 9 требует schema_version: 3 явно
"write STATE using schema_version: 3, last_event: N"
Схема когда-нибудь станет 4. Это захардкожено.
**Фикс:** "write STATE using the current schema_version (read from state.schema.json's x-current-schema-version)".

### 12. "saipen continue" reply must name blocked — но не говорит ГДЕ именно
§1.10 line 299: "A resume MUST also name what is stuck, in its reply, in one line."
Агент должен просканировать `## BLOCKED` секцию доски. Но текст не говорит "read BOARD.md ## BLOCKED".
Слабая модель будет искать блокировки в STATE.md или LOG.md.
**Фикс:** добавить "scan BOARD.md ## BLOCKED section".

### 13. CORE.md §1.6 "Phase enum" не используется напрямую
16 фаз перечислены. Но таблица переходов ниже использует те же имена. А OK-сообщение валидатора говорит "16 phases".
Агент читает enum → запоминает 16 → видит phase: SCOUT → OK.
Но если фаза в STATE.md не из этого enum — валидатор FAIL. Агент не проверяет enum перед выполнением.
**Фикс:** BOOT.md шаг 3: добавить "confirm STATE.phase is in the enum (CORE.md §1.6)".

### 14. INDEX.md запрещает читать CORE.md но BOOT.md требует его
INDEX.md: "Load CORE.md only if you have a specific rule question."
BOOT.md шаг 7: "OPEN § 1.10" (= открыть CORE.md).
Противоречие. Шаг 7 — исключение из правила INDEX, но оно не описано.
**Фикс:** INDEX.md строка про CORE.md: добавить "(exception: BOOT.md step 7 is an explicit read of §1.10 for command resolution)".

### 15. Сценарий `saiui-adoption` требует `expect:` строку но README.md протокола не документирует формат
run_scenarios.py парсит `expect: pass|fail` из первой строки README.
Но ни один документ протокола не описывает этот формат. Только код.
Агент, создающий новый сценарий, должен реверс-инжинирить формат из run_scenarios.py.
**Фикс:** в tests/scenarios/README.md (или создать его) документировать формат: первая строка = `expect: pass|fail`.
