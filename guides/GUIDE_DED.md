<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Инструкция SAIPEN (Версия Деда 👴)

Слышь, салажнюк. Чо расплёлся? Проблема у тебя одна: твои нейросети тупые как пробка и забывают всё через пять минут.

**SAIPEN** — это брезентовый планшет в папке `.saipen/` прямо у тебя в проекте.

**Короткие кнопки, чтоб пальцы не отсохли:** `cc` гонит активный Goal Mode дальше, `sss` докладывает статус и код не лапает, `ss` ставит чекпоинт и жмёт тормоз. [Вся карта из 11 шорткатов](../saipen/RFC.md#110-command-surface); на русской раскладке работают `сс`, `ссс`, `аа`, `ее`, `рр`.

## Шевелись

1. **Запихай правила в комп:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Вруби в проекте:**
> `saipen set`

3. **Паши:**
> `saipen`

## Приказы

| Команда | Чо делает |
|---|---|
| `saipen set` | Создать папку `.saipen/` (мозги) |
| `saipen continue` | Прочитать мозги и пахать |
| `saipen stop` | Тормознуть и записать где стал |
| `saipen status` | Глянуть че там по плану |
| `saipen goal <text>` | Закинуть новую хотелку |
| `saipen clean` | Выметает мусор (старые тикеты, висячие файлы, битые пути). Не трогает код. |
| `saipen translate` | Ребилдит 32-языковой пак в изолированной `saitranslate/`. Исходники не трогает. |
| `saipen markhunt` | Жесткий, сухой аудит базы. Записывает дыры, сам ничего не чинит. |
| `saipen prepare` | Собирает работу в сумку для сменщика, сверяет со свежим HEAD, чтоб не втюхать гнилье. |
| `saipen ship` | Дергает релиз руками (бамп, чейнджлог, тег, пуш). |
| `saipen sub spawn <name>` | Завести батрака-шпиона (read-only, только смотрит) |

## Ещё фишки
- Пришёл, а в папке грязь несохранённая? Норм -- коммитит только на `ship`, не на каждый чих. Сначала гляньте чья грязь, потом трогайте.
- Хочешь чтоб помнил серьёзное архитектурное решение -- пиши в `.saipen/KNOWLEDGE/`, файлом `decisions.md` или нумерованными `ADR-001.md`.
- Гита нет, шелла нет -- не гадает, прямо говорит (`mode`, `WAIT: <категория> -- <вопрос>`). (категория — одна из семи: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; она говорит, какой ответ разблокирует)
- Ссышь? `python <клон-saipen>/tools/install_hook.py` -- заслон перед каждым коммитом. Разонравилось -- `python <клон-saipen>/tools/uninstall_hook.py`, заслон долой, старый хук на место.
- Хочешь батраков под себя -- `saipen sub spawn saihunt`, сам притащит `.saipen/extensions/subs/` откуда надо. Свежак, не проверено в бою.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
