<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Гід SAIPEN (Українська)

[TRANSLATED UK]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN** — це блокнот у папці `.saipen/` прямо в твоєму проекті.

## Швидкий старт

## Команди

## Корисно знати
- Повернувся, а в проекті незакомічені зміни? Це норма -- SAIPEN комітить лише на `ship`, не на кожному кроці. Агент спершу перевіряє, чиї це зміни, перш ніж щось чіпати.
- Хочеш, щоб він пам'ятав справжнє архітектурне рішення? Клади в `.saipen/KNOWLEDGE/` як файл `decisions.md` або нумеровані `ADR-001.md`.
- Немає git чи shell на машині? Агент прямо про це скаже (`mode`, `WAIT: <category> -- <питання>`), а не вгадуватиме (категорія — одна з семи: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; вона говорить, яка відповідь розблокує ситуацію)
- Хочеш підстраховку? `python <клон-saipen>/tools/install_hook.py` ставить перевірку перед кожним комітом.