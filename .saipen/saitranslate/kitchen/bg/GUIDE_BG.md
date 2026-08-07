<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Ръководство SAIPEN (Български)

[TRANSLATED BG]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN** е бележник в папката `.saipen/` във вашия проект.

## Бърз старт

## Команди

## Добре е да знаете
- Некомитнати промени, когато се върнете към проекта? Нормално -- SAIPEN прави commit само при `ship`, не на всяка стъпка. Агентът първо проверява чии са тези промени, преди да пипне каквото и да е.
- Искате да помни истинско архитектурно решение? Сложете го в `.saipen/KNOWLEDGE/`, като един файл `decisions.md` или номерирани файлове `ADR-001.md`.
- Няма git или shell на тази машина? Агентът казва това ясно (`mode`, `WAIT: <category> -- <въпрос>`) вместо да гадае (категорията е една от седем: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; тя показва какъв отговор ще отключи ситуацията)
- Искате предпазна мрежа? `python <saipen-клонинг>/tools/install_hook.py` инсталира проверка преди commit.