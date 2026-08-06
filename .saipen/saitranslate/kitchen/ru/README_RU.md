<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Протокол непрерывности для ИИ-агентов кодинга.** SAIPEN хранит память проекта в формате plain markdown, так что холодный агент без истории чата запускает `/saipen continue`, читает `STATE.md` -> `BOARD.md` -> хвост активного `LOG.md` -> `human_note` (если задан), исполняет `next_action` и возобновляет работу менее чем за минуту — без повторных инструкций, с любым провайдером, в любой день.

**Одна команда. Нуль зависимостей. Нуль амнезии.**

**Быстрые клавиши:** `cc` продолжает активный Goal Mode, `sss` показывает статус без правок кода, а `ss` сохраняет чекпоинт и останавливается. [Полная карта из 15 клавиш](saipen/RFC.md#110-command-surface). Кириллические близнецы тоже работают: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Язык ответов.** Агент по умолчанию отвечает **на эстонском** — это настройка, а не причуда, и больше ничего в SAIPEN не эстонского. Меняется в одном месте: строка `reply_language:` в начале [`saipen/STYLE.md`](saipen/STYLE.md). `et` эстонский, `en` английский, `ru` русский, `auto` выбирает по языку твоего сообщения. Протокол, код, коммиты и все документы при любом значении остаются на английском.

**v7.202.0** | [Спецификация](SPEC.md) | [Руководство](GUIDE.md) | [RFC](saipen/RFC.md) | [Стиль](saipen/STYLE.md) | [Интерфейс](saipen/UI.md) | [Соответствие](saipen/CONFORMANCE.md) | plain markdown | zero deps | MIT
| [БРОШЮРА](BROCHURE_DED.md) | ДОЛЖНО БЫТЬ ПЕРЕВЕДЕНО через saitranslate |

```text
Пользователь ->  /saipen continue
Агент        ->  читает STATE.md (фаза, задача, next_action, режим, human_note)
Агент        ->  читает BOARD.md (тикеты DOING / TODO / DONE / BLOCKED)
Агент        ->  читает хвост активного LOG.md (недавние события)
Агент        ->  читает human_note (если задан, одноразовый пинок)
Агент        ->  сразу исполняет next_action (команду)
Агент        ->  грузит док по фазе только когда нужны правила
Агент        ->  Работает.
```

## Как это работает

**Состояние проекта сильнее памяти модели.** Память живет в проекте, а не в голове модели. `Проект -> Память -> LLM` превращается в `Проект -> Состояние SAIPEN -> LLM`.

- **Основной конечный автомат** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Автономия без подсказок** — доска остановлена (нет рабочих `TODO`, ничего в `DOING`) **и нет `BLOCKED`**? Автопереход в `HUNT` (сканирование багов) → `ADD` (развитие функций) → `HUNT`, ноль вопросов. Сессия на `BLOCKED` никогда не хантит сама; ждет, пока человек разрешит блокер (RFC § 2.1).
- **Строгая надежность** — пакетный ввод разбирается на хирургические тикеты по одному, принятие грязного дерева никогда не стирает незакоммиченную работу, скрытие секретов (`sk-***`).

## Команды

Весь фасад — 16 команд; полные детали в [RFC § 1.10](saipen/RFC.md#110-command-surface).

| Команда | Что делает |
|---|---|
| `/saipen set` | Принять проект |
| `/saipen continue` | Возобновить ровно с места остановки |
| `/saipen plan` | Превратить запрос или бэклог в тикеты |
| `/saipen goal <text>` | Автономное исполнение волны под новую цель |
| `/saipen hunt` | Форсировать проход по дефектам/улучшениям сейчас |
| `/saipen ship` | Бамп версии, чейнджлог, тег, пуш |
| `/saipen clean` | Зачистка репозитория |
| `/saipen validate` | Проверка соответствия |
| `/saipen markhunt` | Сухой аудит без ограничений, только запись |
| `/saipen translate` | Изолированная фабрика переводов |
| `/saipen prepare` | Упаковать работу для передачи |
| `/saipen collect` | Внедрить готовый пакет |
| `/saipen status` | Отчет только для чтения |
| `/saipen stop` | Чекпоинт и остановка |

<sub>`saipen init` и `saipen sub` завершают шестнадцать; обе вызываются протоколом, а не набираются каждый день.</sub>

**Пакетные клавиши.** `ee`/`qq` готовят полные пакеты переводов/вики без внедрения; `eee`/`qqq` принимают только готовый пакет, затем внедряют, проверяют, ревьюят и пушат.

**Экспериментально: saicrew.** Опциональный бонусный слой (`extensions/subs/`, ноль изменений в Core) для мультиагентной бригады: один Core-писатель плюс read-only воркеры `saihunt`/`saipython`, отчитывающиеся через свой `OUTBOX.md`. Под активным живым тестированием, ещё не проверено end-to-end — см. `extensions/subs/crew.md`.

## Два уровня

| Уровень | Обязателен | Назначение |
|---|---|---|
| **Ядро (Core)** | ✅ | Безопасное продолжение работы |
| **Обслуживание (Maintenance)** | Поверх Ядра | Развитие ПО без постановки задач |

**Автоматическая эволюция.** Не осталось открытых задач? Введите `/saipen`: `HUNT` проводит аудит на баги, мертвый код, упавшие тесты. Чисто? `ADD` создает следующую очевидную отсутствующую возможность, проверяет ее и снова запускает `HUNT`. Продукт созрел -> гармонично останавливается.

**Режим GOAL.** `/saipen goal <что вы хотите>` меняет приоритет доски (старые тикеты понижаются, но не удаляются) и продвигает новую цель вперед — никаких "продолжить?" между тикетами, VERIFY/REVIEW никогда не пропускаются. SHIP автоматически отправляет push в существующий удаленный репозиторий; абсолютно новый репозиторий спросит только один раз. Отправка цели — тоже не точка остановки: процесс сразу переходит в автономное обслуживание HUNT/ADD, пока продукт не станет зрелым, заблокированным или запуск не достигнет лимита (3 волны / 20 тикетов, затем чекпоинт и отчет).

## Быстрый старт

**1. Установите один раз на машину** — обучает Claude Code, Codex, Gemini, OpenCode, Aider, Antigravity и любой родовой ридер `~/.agents/skills` (FreeBuff и т.п.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>Что это трогает, чтобы не было сюрпризов: скрипт добавляет размеченный блок `<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->` в ваши файлы инструкций для агентов (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`, `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`) — предварительно создав резервную копию `.bak` — и копирует протокол в соответствующие папки навыков. Ничего за пределами этих путей, никаких демонов, никаких сетевых вызовов.</sub>

**Передумали?** Одна команда всё откатывает:
```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```
Она удаляет ровно размеченный блок (оставляя остальной файл нетронутым), предварительно сохраняет копию `.uninstalled.bak` и удаляет папки навыков.

**2. Запустите проект** — откройте агента в папке вашего проекта и введите:
> `saipen set`

Без установки? Вставьте одну строку любому агенту:
> Read <clone>/saipen/BOOT.md first (cold-start kernel), then <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Платформы нет в списке выше (DeepSeek, Qwen, автономный OpenAI и т.д.)?
Заметки по платформам находятся в `extensions/adapters/`.

## Документация

| Документ | Что это |
|---|---|
| [SPEC.md](SPEC.md) | Формальная архитектура, цели проектирования, лакмусовый тест |
| [RFC.md](saipen/RFC.md) | Нормативная спецификация, исполняемая агентами |
| [GUIDE.md](GUIDE.md) | Руководство для человека и ELI5-гайды |
| [STYLE.md](saipen/STYLE.md) | Стиль общения агента и определение голоса |
| [UI.md](saipen/UI.md) | Дизайн-гайдлайны Vintage Golden UI |
| [CONFORMANCE.md](saipen/CONFORMANCE.md) | Сценарии поведенческих тестов и правила валидатора |

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

## Создано на SAIPEN

- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Высокопроизводительный инструмент управления промптами, построенный вокруг протокола памяти SAIPEN.

## Скриншоты

<details>
<summary>Нажми, чтобы развернуть</summary>

<img src="assets/screenshot-freebuff.png" alt="Инструкции для агента FreeBuff" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set в nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="Скриншот saipen 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- source-digest: README.md sha256:6e65f48b1f949596 -->
