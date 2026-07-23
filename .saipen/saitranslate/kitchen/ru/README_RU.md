<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Протокол продолжения для ИИ-агентов программистов.** Постоянная память проекта в
обычном markdown, поэтому "холодный" агент без истории чата выполняет `/saipen continue`
и возобновляет работу менее чем за минуту — без повторных брифингов, для любого вендора, в любой день.

**Одна команда. Никакой амнезии.**

**v7.41.0** | [Спецификация](SPEC.md) | [Руководство](GUIDE.md) | [RFC](saipen/RFC.md) | [Стиль](saipen/STYLE.md) | [UI](saipen/UI.md) | [Соответствие](saipen/CONFORMANCE.md) | чистый markdown | ноль зависимостей | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Пользователь ->  /saipen continue
Агент        ->  читает STATE ("Что мне делать прямо сейчас?")
Агент        ->  читает BOARD ("Какую задачу я беру?")
Агент        ->  читает next_action (выполняет команду)
Агент        ->  Работает.
```

### Состояние проекта > Память модели
Память живет в проекте, а не в голове модели. `Проект -> Память -> LLM` превращается в `Проект -> Состояние SAIPEN -> LLM`.

### Ключевая логика протокола и гарантии
- **Базовый автомат состояний**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Автономность без промптов**: Доска пуста? Авто-переход `HUNT` (поиск багов) → `ADD` (развитие фич) → цикл `HUNT`. Никаких вопросов не задается.
- **Явные триггеры**: `/saipen clean` (очистка репозитория), `/saipen translate` (изолированная фабрика `.saipen/saitranslate/`), `/saipen validate` (проверка соответствия), `/saipen goal` (автономное выполнение серии задач).
- **Строгая надежность**: Пакетный парсинг ввода (хирургически точные задачи 1-за-1), принятие грязного дерева (никогда не стирает незакоммиченную работу), удаление секретов (`sk-***`).

## Проекты на базе SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Высокопроизводительный инструмент управления промптами, нативно интегрированный с протоколом памяти SAIPEN.

## Два слоя

| Слой | Обязательно | Назначение |
|---|---|---|
| **Core (Ядро)** | ✅ | Безопасное продолжение работы |
| **Maintenance (Обслуживание)** | Поверх Core | Развитие ПО без ручной постановки задач |

**Автоматизированная эволюция.** Доска пуста, введите `/saipen`: `HUNT` проверяет баги, мертвый код, падающие тесты. Чисто? `ADD` создает следующую очевидную недостающую возможность, проверяет ее, снова ищет (`HUNT`). Продукт зрел -> изящно останавливается.

**Режим GOAL (Цель).** `/saipen goal <что вы хотите>` перестраивает доску (старые тикеты понижаются в приоритете, никогда не удаляются) и запускает новую цель вперед — никаких "могу я продолжить?" между тикетами, VERIFY/REVIEW никогда не пропускаются. SHIP автоматически пушит в существующий remote; совершенно новый репозиторий все равно спросит один раз. Отправка (ship) цели также не является точкой остановки — она сразу переходит в автономное обслуживание HUNT/ADD, пока продукт не станет зрелым, не заблокируется или запуск не достигнет своего предела (3 волны / 20 тикетов, затем делает контрольную точку и отчитывается).

## Быстрый старт

**1. Установите один раз на машину** -- обучает Claude Code, Gemini, OpenCode, Aider, Antigravity:
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Начните проект** -- откройте агента в вашей папке, введите:
> `saipen set`

Нет установки? Вставьте одну строку любому агенту:
> Read <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md and follow them.

Платформы нет в списке выше (DeepSeek, Qwen, отдельный OpenAI и т.д.)?
Заметки для конкретных платформ живут в `extensions/adapters/`.

## Ссылки на документацию и спецификацию
- **[SPEC.md](SPEC.md)** -- формальная архитектура, цели дизайна, лакмусовая бумажка.
- **[RFC.md](saipen/RFC.md)** -- нормативная спецификация, исполняемая агентами.
- **[GUIDE.md](GUIDE.md)** -- руководство для людей и ELI5:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- определение стиля общения и голоса агента.
- **[UI.md](saipen/UI.md)** -- руководство по дизайну Dark Golden Win95 UI.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- сценарии поведенческих тестов и правила валидатора.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
