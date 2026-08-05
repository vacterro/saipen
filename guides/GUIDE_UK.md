<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Гід SAIPEN (Українська)

Слухай сюди, салага. Проблема проста: твої AI-агенти мають пам'ять як у золотої рибки.

**SAIPEN** — це блокнот у папці `.saipen/` прямо в твоєму проекті.

**Швидкі клавіші:** `cc` продовжує активний Goal Mode, `sss` показує статус без правок коду, а `ss` зберігає контрольну точку і зупиняється. [Повна карта з 15 клавіш](../saipen/RFC.md#110-command-surface). Кириличні двійники теж працюють: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

## Швидкий старт

1. **Встановити один раз на машину:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Запустити в проекті:**
> `saipen set`

3. **Працювати:**
> `saipen`

## Команди

| Команда | Дія |
|---|---|
| `saipen set` | Ініціалізувати папку пам'яті `.saipen/` |
| `saipen continue` | Відновити роботу за нотатками |
| `saipen stop` | Зберегти прогрес та зупинити |
| `saipen status` | Прочитати дошку та статус |
| `saipen goal <text>` | Перейти до нової мети |
| `saipen clean` | Глибоке очищення репозиторію |
| `saipen translate` | Ізольована збірка перекладів на 32 мови |
| `saipen markhunt` | Глибокий аудит без обмежень -- лише фіксує знахідки |
| `saipen prepare` | Пакує роботу для передачі наступному агенту |
| `saipen ship` | Запустити реліз |

## Корисно знати
- Повернувся, а в проекті незакомічені зміни? Це норма -- SAIPEN комітить лише на `ship`, не на кожному кроці. Агент спершу перевіряє, чиї це зміни, перш ніж щось чіпати.
- Хочеш, щоб він пам'ятав справжнє архітектурне рішення? Клади в `.saipen/KNOWLEDGE/` як файл `decisions.md` або нумеровані `ADR-001.md`.
- Немає git чи shell на машині? Агент прямо про це скаже (`mode`, `WAIT: <category> -- <питання>`), а не вгадуватиме (категорія — одна з семи: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; вона говорить, яка відповідь розблокує ситуацію)
- Хочеш підстраховку? `python <клон-saipen>/tools/install_hook.py` ставить перевірку перед кожним комітом.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
