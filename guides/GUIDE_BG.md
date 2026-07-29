<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Ръководство SAIPEN (Български)

Слушай, новобранец. Проблемът е прост: твоите AI агенти имат памет на златна рибка.

**SAIPEN** е бележник в папката `.saipen/` във вашия проект.

## Бърз старт

1. **Инсталирайте веднъж на машина:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Стартиране на проект:**
> `saipen set`

3. **Работа:**
> `saipen`

## Команди

| Команда | Действие |
|---|---|
| `saipen set` | Инициализиране на папка за памет |
| `saipen continue` | Възобновяване на работата от бележки |
| `saipen stop` | Запазване на напредъка и спиране |
| `saipen status` | Четене на таблото |
| `saipen goal <text>` | Преминаване към нова цел |
| `saipen clean` | Почистване на хранилището |
| `saipen translate` | Изолирано изграждане на превод на 32 езика |
| `saipen markhunt` | Дълбок, неограничен одит -- само записва находки |
| `saipen prepare` | Пакетира работата за предаване на следващия агент |
| `saipen ship` | Стартиране на поток за пускане |

## Добре е да знаете
- Некомитнати промени, когато се върнете към проекта? Нормално -- SAIPEN прави commit само при `ship`, не на всяка стъпка. Агентът първо проверява чии са тези промени, преди да пипне каквото и да е.
- Искате да помни истинско архитектурно решение? Сложете го в `.saipen/KNOWLEDGE/`, като един файл `decisions.md` или номерирани файлове `ADR-001.md`.
- Няма git или shell на тази машина? Агентът казва това ясно (`mode`, `WAIT: <category> -- <въпрос>`) вместо да гадае (категорията е една от седем: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; тя показва какъв отговор ще отключи ситуацията)
- Искате предпазна мрежа? `python <saipen-клонинг>/tools/install_hook.py` инсталира проверка преди commit.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
