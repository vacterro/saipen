<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Протокол доделывания за криворукими ИИ-кодерами.** SAIPEN хранит память проекта в обычном маркдауне. Холодный бот без истории чата вбивает `/saipen continue`, читает `STATE`, `BOARD` и `next_action` и за минуту продолбал работу дальше — без лишнего пиздежа, с любой нейронкой, в любой день.

**Одна команда. Ноль склероза.**

**v7.90.0** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [RFC](saipen/RFC.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) | plain markdown | zero deps | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Юзер  ->  /saipen continue
Бот   ->  читает STATE ("Какого хера я делаю прямо сейчас?")
Бот   ->  читает BOARD ("Какое задание мне, блин, брать?")
Бот   ->  читает next_action (исполняет команду без лишних соплей)
Бот   ->  Пашет.
```

### Состояние Проекта > Мозги Нейросети
Память должна жить в проекте, а не в дырявой башке модели. `Проект -> Память -> LLM` превращается в `Проект -> Состояние SAIPEN -> LLM`.

### Главная Логика Протокола и Гарантии
- **Основной Костяк Состояний**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Автономия Без Лишних Вопросов**: Кончились задачи? Сам переключается: `HUNT` (выискивает баги и говнокод) → `ADD` (допиливает фичи) → цикл `HUNT`. И никаких тупых вопросов.
- **Четкие Команды**: `/saipen plan` (превратить запрос или список в тикеты), `/saipen ship` (версионирование, чейнджлог, тег, пуш), `/saipen clean` (Зачистка репозитория от мусора), `/saipen translate` (Изолированная фабрика перевода в `.saipen/saitranslate/`), `/saipen markhunt` (Сухой аудит без ограничений, только запись), `/saipen prepare` (Упаковка работы для передачи), `/saipen validate` (Проверка целостности), `/saipen goal` (Автономный прогон волнами). Контроль: `/saipen status` (Только чтение отчета), `/saipen stop` (Сохранить чекпоинт и оторвать руки/остановить). Плюс `saipen set` и `saipen continue` — итого двенадцать команд, весь список: RFC.md § 1.10.
- **Надежность Без Соплей**: Парсинг задач поштучно (как хирург, по 1 тикету), подбор незакоммиченного дерьма (никогда не затирает чужой некоммит), замазывание секретов (`sk-***`).
- **Экспериментально -- saicrew**: бонусный довесок (`extensions/subs/`, Core не трогает), чтоб гонять бригаду — один Core пашет, да два дармоеда read-only `saihunt`/`saipython` отчитываются через свой `OUTBOX.md`. Тестируем живьём прямо щас, от и до ещё не проверено — глянь `extensions/subs/crew.md`.

## Проекты на Движке SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Высокопроизводительный менеджер промптов, построенный вокруг протокола памяти SAIPEN.

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
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Твоей платформы нет в списке (DeepSeek, Qwen, голый OpenAI и прочая дичь)?
Заметки по платформам лежат в `extensions/adapters/`.

## Ссылки На Документы И Спецификации
- **[SPEC.md](SPEC.md)** — строгая архитектура, цели дизайна и лакмусовый тест.
- **[RFC.md](saipen/RFC.md)** — нормативная спецификация, которую обязаны исполнять боты.
- **[GUIDE.md](GUIDE.md)** — туториал для людей и разжеванные гайды:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** — стиль общения бота и правила голоса.
- **[UI.md](saipen/UI.md)** — гайдлайн интерфейса в стиле Темного Золота Win95.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** — сценарии тестов поведения и правила валидатора.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>


