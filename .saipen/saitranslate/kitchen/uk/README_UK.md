<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Протокол продовження для ШІ агентів-кодерів.** Постійна пам'ять проєкту в чистому markdown, тому холодний агент без історії чату виконує `/saipen continue` і відновлює роботу менш ніж за хвилину -- без повторного інструктажу, будь-який постачальник, у будь-який день.

**Одна команда. Нуль амнезії.**

**v7.41.0** | [Специфікація](SPEC.md) | [Посібник](GUIDE.md) | [RFC](saipen/RFC.md) | [Стиль](saipen/STYLE.md) | [UI](saipen/UI.md) | [Відповідність](saipen/CONFORMANCE.md) | чистий markdown | нуль залежностей | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Користувач ->  /saipen continue
Агент ->  читає STATE ("Що мені робити прямо зараз?")
Агент ->  читає BOARD ("Яку задачу я беру?")
Агент ->  читає next_action (виконує команду)
Агент ->  Працює.
```

### Стан проєкту > Пам'ять моделі
Пам'ять живе в проєкті, а не в голові моделі. `Проєкт -> Пам'ять -> LLM` перетворюється на `Проєкт -> Стан SAIPEN -> LLM`.

### Ключова логіка та гарантії протоколу
- **Основний автомат станів**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Автономія без підказок**: Дошка порожня? Автоперехід `HUNT` (пошук багів) → `ADD` (розвиток функцій) → цикл `HUNT`. Нуль запитань.
- **Явні тригери**: `/saipen clean` (очищення репозиторію), `/saipen translate` (ізольована фабрика `.saipen/saitranslate/`), `/saipen validate` (перевірка відповідності), `/saipen goal` (автономне виконання хвилі).
- **Сувора надійність**: Пакетний розбір вводу (хірургічні тікети 1-за-1), адаптація брудного дерева (ніколи не знищує незакомічену роботу), редагування секретів (`sk-***`).

## Проєкти, що працюють на SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Високопродуктивний інструмент керування промптами, нативно інтегрований із протоколом пам'яті SAIPEN.

## Два шари

| Шар | Обов'язковий | Призначення |
|---|---|---|
| **Ядро (Core)** | ✅ | Безпечне продовження роботи |
| **Обслуговування (Maintenance)** | Поверх Ядра | Еволюція ПЗ без постановки задач |

**Автоматизована еволюція.** Дошка порожня, вводите `/saipen`: `HUNT` проводить аудит на наявність багів, мертвого коду, невдалих тестів. Чисто? `ADD` створює наступну очевидну відсутню можливість, перевіряє її, знову шукає. Продукт дозрів -> зупиняється коректно.

**Режим GOAL.** `/saipen goal <що ви хочете>` розвертає дошку (старі тікети знижуються в пріоритеті, ніколи не видаляються) і виконує нову ціль -- без питань "чи продовжувати?" між тікетами, VERIFY/REVIEW ніколи не пропускаються. SHIP автоматично пушить до існуючого remote; абсолютно новий репозиторій все ще запитує один раз. Поставка цілі також не є точкою зупинки -- вона відразу переходить до автономного обслуговування HUNT/ADD, поки продукт не дозріє, не заблокується, або виконання не досягне ліміту (3 хвилі / 20 тікетів, потім контрольна точка та звіт).

## Швидкий старт

**1. Встановіть один раз на машину** -- навчає Claude Code, Gemini, OpenCode, Aider, Antigravity:
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Почніть проєкт** -- відкрийте агента у вашій папці, введіть:
> `saipen set`

Немає встановлення? Вставте один рядок будь-якому агенту:
> Читати <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md і слідувати їм.

Платформи немає у списку вище (DeepSeek, Qwen, окремий OpenAI тощо)?
Нотатки для кожної платформи знаходяться у `extensions/adapters/`.

## Посилання на документацію та специфікацію
- **[SPEC.md](SPEC.md)** -- формальна архітектура, цілі дизайну, лакмусовий папірець.
- **[RFC.md](saipen/RFC.md)** -- нормативна специфікація, яку виконують агенти.
- **[GUIDE.md](GUIDE.md)** -- навчальний посібник для людей та гід ELI5:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- стиль спілкування агента та визначення голосу.
- **[UI.md](saipen/UI.md)** -- інструкції з дизайну інтерфейсу Dark Golden Win95.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- поведінкові тестові сценарії та правила валідатора.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>
