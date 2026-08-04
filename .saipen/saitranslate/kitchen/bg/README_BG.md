<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Протокол за приемственост за AI агенти за кодиране.** Персистентна проектна памет в чист markdown, така че нов агент без история на чата да стартира `/saipen continue` и да възобнови работа за под минута -- без повторен брифинг, всеки доставчик, всеки ден.

**Една команда. Нула амнезия.**

**Бързи клавиши:** `cc` продължава активен Goal Mode, `sss` показва статус без допиране до кода, а `ss` запазва контролна точка и спира. [Виж пълната карта с 13 клавиша](saipen/RFC.md#110-command-surface). Кирилските близнаци също работят: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Език на отговорите.** Агентът по подразбиране отговаря **на естонски** — това е настройка, а не приумица, и нищо друго в SAIPEN не е на естонски. Променя се на едно място: редът `reply_language:` в началото на [`saipen/STYLE.md`](saipen/STYLE.md). `et` естонски, `en` английски, `ru` руски, `auto` избира според езика на твоето съобщение. Протоколът, кодът, комитите и всички документи остават на английски при всяка стойност.

**v7.180.0** | [Спецификация](SPEC.md) | [Ръководство](GUIDE.md) | [RFC](saipen/RFC.md) | [Стил](saipen/STYLE.md) | [UI](saipen/UI.md) | [Съответствие](saipen/CONFORMANCE.md) | чист markdown | нула зависимости | MIT

```text
Потребител ->  /saipen continue
Агент      ->  чете STATE ("Какво да правя точно сега?")
Агент      ->  чете BOARD ("За коя задача да се хвана?")
Агент      ->  чете next_action (изпълнява команда)
Агент      ->  Работи.
```

### Проектно състояние > Памет на модела
Паметта живее в проекта, а не в главата на модела. `Проект -> Памет -> LLM` става `Проект -> SAIPEN Състояние -> LLM`.

### Ключова логика на протокола & гаранции
- **Основен краен автомат**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Автономия без подкана**: Няма останали отворени задачи? Автоматично преминава `HUNT` (сканиране за бъгове) → `ADD` (развитие на функции) → `HUNT` цикъл. Нула зададени въпроси.
- **Явни тригери**: `/saipen clean` (почистване на хранилището), `/saipen translate` (изолирана `.saipen/saitranslate/` фабрика), `/saipen markhunt` (сух неограничен одит, само записва), `/saipen prepare` (пакетиране на работа за прехвърляне), `/saipen validate` (проверка за съответствие), `/saipen goal` (автономно изпълнение на вълни). Мета/контрол: `/saipen status` (доклад само за четене), `/saipen stop` (чекпойнт и спиране). Пълен списък: RFC.md § 1.10.
- **Строга надеждност**: Парсиране на групов вход (хирургични 1-по-1 тикети), приемане на замърсено дърво (никога не изтрива неподадена работа), заличаване на тайни (`sk-***`).
- **В процес на разработка -- saicrew**: опционален бонус слой (`extensions/subs/`, без промени в Core) за пускане на мултиагентна бригада -- един Core писател плюс read-only работници `saihunt`/`saipython`, докладващи през своя `OUTBOX.md`. Под активно живо тестване, все още не проверено от край до край -- виж `extensions/subs/crew.md`.

## Проекти, задвижвани от SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Високоефективен инструмент за управление на промпти, нативно интегриран с протокола за памет SAIPEN.

## Два слоя

| Слой | Задължителен | Цел |
|---|---|---|
| **Основен (Core)** | ✅ | Безопасно продължаване на работата |
| **Поддръжка (Maintenance)** | Върху Основния | Развитие на софтуера без възлагане на задачи |

**Автоматизирана еволюция.** Няма останали отворени задачи, напишете `/saipen`: `HUNT` одитира за бъгове, мъртъв код, падащи тестове. Всичко е чисто? `ADD` изгражда следващата очевидно липсваща възможност, верифицира я, търси отново. Продуктът е зрял -> спира плавно.

**Режим GOAL.** `/saipen goal <какво искате>` преориентира дъската (старите тикети се понижават, никога не се изтриват) и придвижва новата цел напред -- без "да продължа ли?" между тикетите, VERIFY/REVIEW никога не се прескачат. SHIP автоматично push-ва към съществуващо дистанционно хранилище; чисто ново хранилище все пак пита веднъж. Доставянето на целта също не е точка на спиране -- то преминава директно в autonomous HUNT/ADD поддръжка, докато продуктът стане зрял, блокиран или изпълнението достигне лимита си (3 вълни / 20 тикета, след което прави чекпойнт и докладва).

## Бърз старт

**1. Инсталирайте веднъж на машина** -- обучава Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex и всеки родов четец на `~/.agents/skills` (FreeBuff и др.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Стартирайте проект** -- отворете агент във вашата папка, напишете:
> `saipen set`

Нямате инсталация? Поставете един ред на всеки агент:
> Прочетете <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md и ги следвайте.

Платформата не е в списъка по-горе (DeepSeek, Qwen, самостоятелен OpenAI и т.н.)?
Бележките за отделните платформи са в `extensions/adapters/`.

## Връзки към документация & спецификации
- **[SPEC.md](SPEC.md)** -- формална архитектура, дизайн цели, лакмусов тест.
- **[RFC.md](saipen/RFC.md)** -- нормативна спецификация, изпълнявана от агенти.
- **[GUIDE.md](GUIDE.md)** -- ръководство за хора & ELI5 гайдове:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- стил на комуникация на агента & дефиниция на гласа.
- **[UI.md](saipen/UI.md)** -- Vintage Golden UI насоки за дизайн.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- поведенчески тестови сценарии & правила за валидатора.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

## ## Екранни снимки

<details>
<summary>Кликни, за да разшириш</summary>

<img src="assets/screenshot-freebuff.png" alt="Инструкции за агента FreeBuff" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set в nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="Екранна снимка saipen 2026-08-01" width="600"/>

</details>
