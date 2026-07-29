<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Протокол непрерывности для ИИ-агентов кодинга.** SAIPEN хранит память проекта в формате plain markdown, так что холодный агент без истории чата запускает `/saipen continue`, читает `STATE`, `BOARD` и `next_action` и возобновляет работу менее чем за минуту — без повторных инструкций, с любым провайдером, в любой день.

**Одна команда. Нуль амнезии.**

**v7.107.0** | [Спецификация](SPEC.md) | [Руководство](GUIDE.md) | [RFC](saipen/RFC.md) | [Стиль](saipen/STYLE.md) | [Интерфейс](saipen/UI.md) | [Соответствие](saipen/CONFORMANCE.md) | plain markdown | zero deps | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Пользователь ->  /saipen continue
Агент        ->  читает STATE ("Что я делаю прямо сейчас?")
Агент        ->  читает BOARD ("Какую задачу я беру?")
Агент        ->  читает next_action (выполняет команду)
Агент        ->  Работает.
```

### Состояние проекта > Память модели
Память живет в проекте, а не в голове модели. `Проект -> Память -> LLM` превращается в `Проект -> Состояние SAIPEN -> LLM`.

### Ключевая логика протокола и гарантии
- **Основной конечный автомат**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Автономия без подсказок**: Не осталось открытых задач? Автоматический переход в цикл `HUNT` (сканирование багов) → `ADD` (развитие функций) → `HUNT`. Без лишних вопросов.
- **Явные триггеры**: `/saipen plan` (превратить запрос или список задач в тикеты), `/saipen ship` (версионирование, чейнджлог, тег, пуш), `/saipen clean` (очистка репозитория), `/saipen translate` (изолированная фабрика `.saipen/saitranslate/`), `/saipen markhunt` (сухой аудит без ограничений, только запись), `/saipen prepare` (упаковка работы для передачи), `/saipen validate` (проверка соответствия), `/saipen goal` (автономное исполнение волны). Мета/управление: `/saipen status` (отчет только для чтения), `/saipen stop` (сохранение чекпоинта и остановка). Плюс `saipen set` и `saipen continue` — всего двенадцать команд, полный список: RFC.md § 1.10.
- **Строгая надежность**: Пакетный разбор ввода (хирургически по 1 тикету), принятие нечистого дерева (никогда не стирает незакоммиченную работу), скрытие секретов (`sk-***`).
- **Экспериментально -- saicrew**: опциональный бонусный слой (`extensions/subs/`, без изменений в Core) для запуска мультиагентной бригады — один Core-писатель плюс read-only воркеры `saihunt`/`saipython`, отчитывающиеся через свой `OUTBOX.md`. Под активным живым тестированием, ещё не проверено end-to-end — см. `extensions/subs/crew.md`.

## Проекты на базе SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Высокопроизводительный инструмент управления промптами, построенный вокруг протокола памяти SAIPEN.

## Два уровня

| Уровень | Обязателен | Назначение |
|---|---|---|
| **Ядро (Core)** | ✅ | Безопасное продолжение работы |
| **Обслуживание (Maintenance)** | Поверх Ядра | Развитие ПО без постановки задач |

**Автоматическая эволюция.** Не осталось открытых задач? Введите `/saipen`: `HUNT` проводит аудит на баги, мертвый код, упавшие тесты. Чисто? `ADD` создает следующую очевидную отсутствующую возможность, проверяет ее и снова запускает `HUNT`. Продукт созрел -> гармонично останавливается.

**Режим GOAL.** `/saipen goal <что вы хотите>` меняет приоритет доски (старые тикеты понижаются, но не удаляются) и продвигает новую цель вперед — никаких "продолжить?" между тикетами, VERIFY/REVIEW никогда не пропускаются. SHIP автоматически отправляет push в существующий удаленный репозиторий; абсолютно новый репозиторий спросит только один раз. Отправка (Ship) цели — это тоже не точка остановки: процесс сразу переходит в автономное обслуживание HUNT/ADD, пока продукт не станет зрелым, заблокированным или запуск не достигнет лимита (3 волны / 20 тикетов, затем чекпоинт и отчет).

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
> Прочитай <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md и следуй им.

Платформы нет в списке выше (DeepSeek, Qwen, автономный OpenAI и т.д.)?
Заметки по платформам находятся в `extensions/adapters/`.

## Ссылки на документацию и спецификацию
- **[SPEC.md](SPEC.md)** — формальная архитектура, цели проектирования, лакмусовый тест.
- **[RFC.md](saipen/RFC.md)** — нормативная спецификация, исполняемая агентами.
- **[GUIDE.md](GUIDE.md)** — руководство для человека и ELI5-гайды:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** — стиль общения агента и определение тона.
- **[UI.md](saipen/UI.md)** — руководства по дизайну интерфейса Vintage Golden.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** — сценарии поведенческого тестирования и правила валидатора.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>


