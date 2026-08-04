<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Протокол продовження роботи для AI-агентів кодингу.** Постійна пам'ять проєкту в чистому markdown, завдяки чому «холодний» агент без історії чату запускає `/saipen continue` і відновлює роботу менш ніж за хвилину — без повторних інструкцій, з будь-яким провайдером, у будь-який день.

**Одна команда. Нуль амнезії.**

**Швидкі клавіші:** `cc` продовжує активний Goal Mode, `sss` показує статус без правок коду, а `ss` зберігає контрольну точку і зупиняється. [Повна карта з 13 клавіш](saipen/RFC.md#110-command-surface). Кириличні двійники теж працюють: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Мова відповідей.** Агент за замовчуванням відповідає **естонською** — це налаштування, а не примха, і більше нічого в SAIPEN не естонське. Змінюється в одному місці: рядок `reply_language:` на початку [`saipen/STYLE.md`](saipen/STYLE.md). `et` естонська, `en` англійська, `ru` російська, `auto` обирає за мовою твого повідомлення. Протокол, код, коміти та всі документи за будь-якого значення залишаються англійською.

**v7.181.0** | [Специфікація](SPEC.md) | [Гайд](GUIDE.md) | [RFC](saipen/RFC.md) | [Стиль](saipen/STYLE.md) | [UI](saipen/UI.md) | [Відповідність](saipen/CONFORMANCE.md) | чистий markdown | нуль залежностей | MIT

```text
Користувач ->  /saipen continue
Агент      ->  читає STATE ("Що я роблю просто зараз?")
Агент      ->  читає BOARD ("За яку задачу я беруся?")
Агент      ->  читає next_action (виконує команду)
Агент      ->  Працює.
```

### Стан проєкту > Пам'ять моделі
Пам'ять живе в проєкті, а не в голові моделі. `Проєкт -> Пам'ять -> LLM` стає `Проєкт -> Стан SAIPEN -> LLM`.

### Ключова логіка та гарантії протоколу
- **Основний автомат станів**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Автономність без промптів**: Не залишилося відкритих задач? Автоматичний перехід у цикл `HUNT` (сканування багів) → `ADD` (розвиток функціоналу) → `HUNT`. Нуль запитань.
- **Явні тригери**: `/saipen clean` (очищення репозиторію), `/saipen translate` (ізольована фабрика `.saipen/saitranslate/`), `/saipen markhunt` (сухий необмежений аудит, лише записи), `/saipen prepare` (підготовка роботи для передачі), `/saipen validate` (перевірка відповідності), `/saipen goal` (автономне виконання хвилі). Мета/управління: `/saipen status` (звіт тільки для читання), `/saipen stop` (чекпоїнт і зупинка). Повний список: RFC.md § 1.10.
- **Сувора надійність**: Пакетний парсинг вхідних даних (хірургічні тикети 1-за-1), пристосування до "брудного" дерева (ніколи не стирає незакомічені зміни), приховування секретів (`sk-***`).
- **У розробці -- saicrew**: опціональний бонусний шар (`extensions/subs/`, без змін у Core) для запуску мультиагентної бригади -- один Core-письменник плюс read-only робітники `saihunt`/`saipython`, які звітують через свій `OUTBOX.md`. Під активним живим тестуванням, ще не перевірено end-to-end -- див. `extensions/subs/crew.md`.

## Проєкти на базі SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Високопродуктивний інструмент управління промптами, нативно інтегрований з протоколом пам'яті SAIPEN.

## Два рівні

| Рівень | Обов'язковий | Призначення |
|---|---|---|
| **Core** | ✅ | Безпечне продовження роботи |
| **Maintenance** | Понад Core | Розвиток ПЗ без постановки задач |

**Автоматизований розвиток.** Не залишилося відкритих задач? Введіть `/saipen`: `HUNT` проводити аудит на наявність багів, мертвого коду, непрацюючих тестів. Все чисто? `ADD` створює наступну очевидну відсутню можливість, перевіряє її та знову запускає `HUNT`. Продукт зрілий -> граційно зупиняється.

**Режим GOAL.** `/saipen goal <що ви хочете>` змінює пріоритети дошки (старі тикети понижуються, але ніколи не видаляються) і просуває нову ціль уперед — без запитань "чи продовжувати мені?" між тикетами, VERIFY/REVIEW ніколи не пропускаються. SHIP автоматично робить push у існуючий віддалений репозиторій; абсолютно новий репозиторій усе ще запитає один раз. Відправка (shipping) цілі також не є точкою зупинки — процес одразу переходить до автономного обслуговування HUNT/ADD, поки продукт не стане зрілим, блокованим або не досягне ліміту прогону (3 хвилі / 20 тикетів, після чого робиться чекпоїнт і звіт).

## Швидкий старт

**1. Встановіть один раз на машину** — навчає Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex і будь-який родовий читач `~/.agents/skills` (FreeBuff тощо):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Запустіть проєкт** — відкрийте агента у вашій папці та введіть:
> `saipen set`

Немає установки? Вставте один рядок будь-якому агенту:
> Прочитай <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md та дотримуйся їх.

Платформи немає у списку вище (DeepSeek, Qwen, автономний OpenAI тощо)?
Зауваження для кожної платформи знаходяться в `extensions/adapters/`.

## Посилання на документацію та специфікацію
- **[SPEC.md](SPEC.md)** — формальна архітектура, цілі дизайну, лакмусовий папірець.
- **[RFC.md](saipen/RFC.md)** — нормативна специфікація, що виконується агентами.
- **[GUIDE.md](GUIDE.md)** — навчальний посібник для людей та прості гайди (ELI5):
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** — стиль спілкування агента та визначення голосу.
- **[UI.md](saipen/UI.md)** — керівництво з дизайну інтерфейсу Vintage Golden.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** — сценарії тестування поведінки та правила валідатора.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

## ## Скріншоти

<details>
<summary>Натисни, щоб розгорнути</summary>

<img src="assets/screenshot-freebuff.png" alt="Інструкції для агента FreeBuff" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set у nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="Скріншот saipen 2026-08-01" width="600"/>

</details>
