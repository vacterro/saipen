<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Протокол доделывания за криворукими ИИ-кодерами.** SAIPEN хранит память проекта в обычном маркдауне. Холодный бот без истории чата вбивает `/saipen continue`, читает `STATE.md` -> `BOARD.md` -> хвост активного `LOG.md` -> `human_note` (если есть), исполняет `next_action` и за минуту продолбал работу дальше — без лишнего пиздежа, с любой нейронкой, в любой день.

**Одна команда. Ноль склероза.**

**Короткие кнопки, чтоб пальцы не отсохли:** `cc` гонит активный Goal Mode дальше, `sss` докладывает статус и код не лапает, `ss` ставит чекпоинт и жмёт тормоз. [Вся карта из 15 шорткатов](saipen/RFC.md#110-command-surface); на русской раскладке работают `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Язык ответов.** Агент по умолчанию отвечает на **эстонском** — это настройка, а не причуда, и больше ничего эстонского в SAIPEN нет. Меняется в одном месте: строка `reply_language:` в начале [`saipen/STYLE.md`](saipen/STYLE.md). `et` эстонский, `en` английский, `ru` русский, `auto` выбирает по языку твоего сообщения. Протокол, код, коммиты и все документы при любом значении остаются на английском.

**v7.206.9** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [RFC](saipen/RFC.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) | plain markdown | zero deps | MIT
| [БРОШЮРА](BROCHURE_DED.md) | ПЕРЕВЕСТИ через saitranslate ОБЯЗАТЕЛЬНО |

```text
Юзер  ->  /saipen continue
Бот   ->  читает STATE.md (фаза, задача, next_action, режим, human_note)
Бот   ->  читает BOARD.md (тикеты DOING / TODO / DONE / BLOCKED)
Бот   ->  читает хвост активного LOG.md (недавние события)
Бот   ->  читает human_note (если есть, одноразовый пинок)
Бот   ->  сразу рубит next_action (команду)
Бот   ->  грузит док по фазе только когда нужны правила
Бот   ->  Пашет.
```

## Как Это Работает

**Состояние Проекта бьет Мозги Нейросети.** Память должна жить в проекте, а не в дырявой башке модели. `Проект -> Память -> LLM` превращается в `Проект -> Состояние SAIPEN -> LLM`.

- **Основной Костяк Состояний** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Автономия Без Лишних Вопросов** — доска остановилась (нет рабочих `TODO`, пусто в `DOING`) **и нет `BLOCKED`**? Сам переключается: `HUNT` (выискивает баги и говнокод) → `ADD` (допиливает фичи) → цикл `HUNT`. И никаких тупых вопросов. Застрял на `BLOCKED` — сам не хантит, ждёт, пока человек разблокирует (RFC § 2.1).
- **Надежность Без Соплей** — парсинг задач поштучно (как хирург, по 1 тикету), подбор незакоммиченного дерьма (никогда не затирает чужой некоммит), замазывание секретов (`sk-***`).

## Команды

Весь фасад — 16 команд; полные детали в [RFC § 1.10](saipen/RFC.md#110-command-surface).

| Команда | Что делает |
|---|---|
| `/saipen set` | Принять проект |
| `/saipen continue` | Возобновить ровно с места остановки |
| `/saipen plan` | Превратить запрос или бэклог в тикеты |
| `/saipen goal <text>` | Автономный прогон волны под новую цель |
| `/saipen hunt` | Прогнать поиск дефектов/улучшений прямо сейчас |
| `/saipen ship` | Бамп версии, чейнджлог, тег, пуш |
| `/saipen clean` | Зачистка репозитория |
| `/saipen validate` | Проверка целостности |
| `/saipen markhunt` | Сухой аудит без ограничений, только запись |
| `/saipen translate` | Изолированная фабрика переводов |
| `/saipen prepare` | Упаковать работу для передачи |
| `/saipen collect` | Внедрить готовый пакет |
| `/saipen status` | Отчет только для чтения |
| `/saipen stop` | Чекпоинт и остановка |

<sub>`saipen init` и `saipen sub` добивают до шестнадцати; обе дергает протокол, а не ты каждый день.</sub>

**Пакетные кнопки.** `ee`/`qq` собирают полный пакет переводов/вики, но в проект лапы не суют; `eee`/`qqq` берут только готовый пакет, внедряют, проверяют, ревьюят и пушат.

**Экспериментально: saicrew.** Бонусный довесок (`extensions/subs/`, Core не трогает), чтоб гонять бригаду — один Core пашет, да два дармоеда read-only `saihunt`/`saipython` отчитываются через свой `OUTBOX.md`. Тестируем живьём прямо щас, от и до ещё не проверено — глянь `extensions/subs/crew.md`.

## Два Уровня

| Уровень | Обязателен | Накой хрен нужен |
|---|---|---|
| **Core (Ядро)** | ✅ | Безопасно продолжать пахать |
| **Maintenance (Обслуживание)** | Поверх ядра | Допиливать софт без подсказок человека |

**Автоматическая Доработка.** Задачи кончились — вбиваешь `/saipen`: `HUNT` шмонает баги, мертвый код и упавшие тесты. Всё чисто? `ADD` пилит следующую очевидную фичу, проверяет и опять идет искать баги. Продукт дозрел -> красиво останавливается.

**Режим GOAL.** `/saipen goal <чего тебе надо>` перестраивает доску (старые тикеты сдвигает вниз, но не удаляет, сука) и прет к новой цели — никаких тупых вопросов "продолжать ли мне?" между тикетами, VERIFY/REVIEW хрен пропустишь. SHIP сам заталкивает код в удаленный реп; если реп новый — спросит один раз для приличия. Но зашипить цель — это еще не конец: проект сразу валится в режим авто-обслуживания HUNT/ADD, пока софт не станет идеальным, не застрянет или не упрется в лимит (3 волны / 20 тикетов, после чего делает чекпоинт и отчитывается).

## Быстрый Старт (Для Тех Кто В Танке)

**1. Поставь один раз на тачку** — вбивает мозги Claude Code, Codex, Gemini, OpenCode, Aider, Antigravity, да любой левый читатель `~/.agents/skills` (FreeBuff и подобная шушера):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>Что это трогает, чтоб без сюрпризов: скрипт втыкает размеченный блок `<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->` в твои инструкционные файлы (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`, `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`) — предварительно сохранив резервную копию `.bak` — и копирует протокол в соответствующие папки скиллов. Ничего вне этих путей, никаких демонов, никаких сетевых вызовов.</sub>

**Передумал?** Одна команда всё откатывает:
```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```
Она выкусывает ровно размеченный блок (остальное не трогает), предварительно сохраняет копию `.uninstalled.bak` и сносит папки скиллов.

**2. Запусти в проекте** — открой бота в папке проекта и вбей:
> `saipen set`

Не поставил? Засовывай одну строчку любому боту:
> Read <clone>/saipen/BOOT.md first (cold-start kernel), then <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Твоей платформы нет в списке (DeepSeek, Qwen, голый OpenAI и прочая дичь)?
Заметки по платформам лежат в `extensions/adapters/`.

## Документация

| Документ | Что это |
|---|---|
| [SPEC.md](SPEC.md) | Строгая архитектура, цели дизайна и лакмусовый тест |
| [RFC.md](saipen/RFC.md) | Нормативная спецификация, которую обязаны исполнять боты |
| [GUIDE.md](GUIDE.md) | Туториал для людей и разжеванные гайды |
| [STYLE.md](saipen/STYLE.md) | Стиль общения бота и правила голоса |
| [UI.md](saipen/UI.md) | Дизайн-гайдлайны Vintage Golden UI |
| [CONFORMANCE.md](saipen/CONFORMANCE.md) | Сценарии тестов поведения и правила валидатора |

<details>
<summary><b>Все 33 переведенных гайда</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [English](guides/GUIDE_EN.md) · 🇪🇪 [Eesti](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Deutsch](guides/GUIDE_DE.md) · 🇫🇷 [Français](guides/GUIDE_FR.md) · 🇪🇸 [Español](guides/GUIDE_ES.md) · 🇮🇹 [Italiano](guides/GUIDE_IT.md)

🇵🇹 [Português](guides/GUIDE_PT.md) · 🇳🇱 [Nederlands](guides/GUIDE_NL.md) · 🇵🇱 [Polski](guides/GUIDE_PL.md) · 🇸🇪 [Svenska](guides/GUIDE_SV.md) · 🇩🇰 [Dansk](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Кто Пашет на SAIPEN

- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Высокопроизводительный менеджер промптов, построенный вокруг протокола памяти SAIPEN.

## Скриншоты (Картинки)

<details>
<summary>Жми сюда, чтоб развернуть</summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff инструкции" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set в nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen скриншот 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- source-digest: README.md sha256:535e0088a9f9fcb5b9dc4d0a6e1072ac643101e0083789f57d4850be564931ce -->




