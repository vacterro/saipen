<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

<div align="center">
  <h3>🔥 <a href="README.ee.md">🇪🇪 LOE SEDA EESTI KEELES / ESTONIAN 🇪🇪</a> 🔥</h3>
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp; 
  <a href="README.ded.md">👴 Дед-Версия (Russian)</a> &nbsp;|&nbsp; 
  <a href="README.ja.md">🇯🇵 日本語 (Japanese)</a>
</div>

# SAIPEN

**Протокол-шпаргалка, чтоб нейронка не забывала, что делает.** SAIPEN держит память проекта в простом markdown'е. Холодный агент без истории чата дёргает `/saipen continue`, читает `STATE.md` -> `BOARD.md` -> хвост активного `LOG.md` -> `human_note` (если есть), исполняет `next_action` и снова в бою за минуту — без занудных брифингов, с любой моделью, в любой день.

**Одна команда. Ноль зависимостей. Ноль амнезии. Всё по хардкору.**

**Короткие кнопки, чтоб пальцы не отсохли:** `cc` гонит активный Goal Mode дальше, `sss` докладывает статус и код не лапает, `ss` ставит чекпоинт и жмёт тормоз. [Вся карта из 14 шорткатов](saipen/RFC.md#110-command-surface); на русской раскладке работают `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Язык ответов.** Агент по умолчанию отвечает на **эстонском** — это настройка, а не причуда, и больше ничего эстонского в SAIPEN нет. Меняется в одном месте: строка `reply_language:` в начале [`saipen/STYLE.md`](saipen/STYLE.md). `et` эстонский, `en` английский, `ru` русский, `auto` выбирает по языку твоего сообщения. Протокол, код, коммиты и все документы при любом значении остаются на английском.

**v7.176.0** | [Спека](SPEC.md) | [Гайд](GUIDE.md) | [RFC](saipen/RFC.md) | [Стиль](saipen/STYLE.md) | [UI](saipen/UI.md) | [Контроль](saipen/CONFORMANCE.md) | MIT

```text
Юзер   ->  /saipen continue
Агент  ->  читает STATE.md (фаза, таска, next_action, мод, human_note)
Агент  ->  читает BOARD.md (тикеты DOING / TODO / DONE / BLOCKED)
Агент  ->  читает хвост LOG.md (что было недавно)
Агент  ->  читает human_note (если есть, пинок от юзера)
Агент  ->  сразу рубит next_action (команду)
Агент  ->  грузит док по фазе только если нужны правила
Агент  ->  Пашет как проклятый.
```

## Как Это Работает

**Состояние Проекта > Память Модели.** Память живёт в проекте, а не в башке LLM. `Проект -> Память -> LLM` становится `Проект -> SAIPEN State -> LLM`.

- **Базовый Стейт-Машин** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Автономия Без Нытья** — доска встала (нет рабочих `TODO`, пусто в `DOING`) **и нет `BLOCKED`**? Автоматом прёт в `HUNT` (ищет баги) → `ADD` (пилит фичи) → `HUNT`, вообще без лишних вопросов. Если сессия встала на `BLOCKED`, она сама не пойдёт в охоту — будет ждать, пока кожаный мешок не разберётся (RFC § 2.1).
- **Драконовская Надёжность** — парсинг по одному тикету, берёт грязное дерево как есть (никогда не трёт несохранённый труд), глушит секреты (`sk-***`).

## Команды

Весь фасад — 16 команд; полные детали в [RFC § 1.10](saipen/RFC.md#110-command-surface).

| Команда | Что делает |
|---|---|
| `/saipen set` | Принять проект |
| `/saipen continue` | Возобновить ровно с места остановки |
| `/saipen plan` | Рубит хотелку на тикеты |
| `/saipen goal <text>` | Автономный прогон волны под новую цель |
| `/saipen hunt` | Прогнать поиск дефектов/улучшений щас |
| `/saipen ship` | Бамп версии, чейнджлог, тег, пуш |
| `/saipen clean` | Драит репо |
| `/saipen validate` | Проверка по ГОСТу |
| `/saipen markhunt` | Аудит без лимитов, просто пишет |
| `/saipen translate` | Изолированный завод `.saipen/saitranslate/` |
| `/saipen prepare` | Пакует работу для передачи |
| `/saipen collect` | Внедряет готовый пакет |
| `/saipen status` | Отчёт только на чтение |
| `/saipen stop` | Сохранился и вырубился |

<sub>`saipen init` и `saipen sub` добивают до шестнадцати; обе дёргает сам протокол, а не ты каждый день.</sub>

**Пакетные кнопки.** `ee`/`qq` собирают полный пакет переводов/вики, но в проект лапы не суют; `eee`/`qqq` берут только готовый пакет, внедряют, проверяют, ревьюят и пушат.

**Эксперимент -- saicrew.** Опциональная приблуда (`extensions/subs/`, ядро не трогает) для бригады агентов — один писатель-Ядро плюс read-only `saihunt`/`saipython` пахари, отчитывающиеся через свои `OUTBOX.md`. Тестируется в бою, пока не зацементировано — см. `extensions/subs/crew.md`.

## Два Слоя

| Слой | Обязателен | Суть |
|---|---|---|
| **Core (Ядро)** | ✅ | Продолжай пахать безопасно |
| **Maintenance** | Поверх Ядра | Развивай софт сам, без пинков |

**Авто-Эволюция.** Тикетов не осталось, пишешь `/saipen`: `HUNT` ищет баги, мёртвый код, упавшие тесты. Всё чисто? `ADD` пилит следующую нужную фичу, проверяет, снова на охоту. Софт созрел -> тормозит по-красоте.

**Режим GOAL (ЦЕЛЬ).** `/saipen goal <че надо>` переворачивает доску (старые тикеты понижаются, но не трутся) и гонит новую цель впёрёд — никаких "продолжать?" между тикетами, VERIFY/REVIEW пропускать запрещено. SHIP сам пушит в готовый ремоут; в новом репо один раз спросит. Релиз цели — не конец. Сразу падает в авто-HUNT/ADD пока софт не созреет, не словит блок, или не упрётся в лимит (3 волны / 20 тикетов, потом бэкап и отчёт).

## Быстрый Старт (Для Чайников)

**1. Ставишь один раз на тачку** -- учит Claude Code, Codex, Gemini, OpenCode, Aider, Antigravity и любую читалку `~/.agents/skills` (FreeBuff и т.д.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Для винды
bash bootstrap/inject.sh                                            # Для мака / линуха
```

<sub>Что он там трогает, чтоб без инфарктов: дописывает блок
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->` в твои файлы инструкций агентов (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`) -- предварительно бэкапя каждый в `.bak` -- и копирует протокол в их папки навыков. Ничего за пределами этих путей, никаких демонов, никаких сетевых вызовов. Всё чисто.</sub>

**Передумал?** Одна команда всё сносит обратно:
```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Для винды
bash bootstrap/uninstall.sh                                         # Для мака / линуха
```
Сносит только этот блок (остальное не трогает), бэкапит `.uninstalled.bak` и удаляет папки протокола.

**2. Запустил проект** -- открыл агента в папке, пишешь:
> `saipen set`

Не ставил глобально? Закинь эту строчку любому агенту:
> Read <clone>/saipen/BOOT.md first (cold-start kernel), then <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Платформы нет в списке выше (DeepSeek, Qwen, чистый OpenAI)?
Заметки по платформам валяются в `extensions/adapters/`.

## Документация

| Документ | Что это |
|---|---|
| [SPEC.md](SPEC.md) | Формальная архитектура, зачем всё это, лакмусовая бумажка |
| [RFC.md](saipen/RFC.md) | ГОСТ-спека для агентов. Выполнять беспрекословно |
| [GUIDE.md](GUIDE.md) | Гайды для людей (ELI5) |
| [STYLE.md](saipen/STYLE.md) | Стиль базара агента |
| [UI.md](saipen/UI.md) | Дизайн-гайдлайны Vintage Golden UI |
| [CONFORMANCE.md](saipen/CONFORMANCE.md) | Сценарии тестов и правила валидации |

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

- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Лютый инструмент управления промптами, построенный вокруг протокола памяти SAIPEN.

## Скриншоты (Картинки)

<details>
<summary>Жми сюда, чтоб развернуть</summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff инструкции" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set в nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen скриншот 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="Печать Деда" width="120"/>
</p>
