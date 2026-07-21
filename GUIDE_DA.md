<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# SAIPEN Guide (Dansk)

SAIPEN er en hukommelsesnotesbog i mappen `.saipen/` til AI-agenter.

## Quick Start / Быстрый старт

1. **Install once per machine / Установить один раз:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Start project / Запустить в проекте:**
> `saipen set`

3. **Work / Работать:**
> `saipen`

## Commands / Команды

| Command | Action |
|---|---|
| `saipen set` | Initialize memory folder `.saipen/` |
| `saipen continue` | Resume work from notes |
| `saipen stop` | Save progress & stop |
| `saipen status` | Read board & state |
| `saipen goal <text>` | Pivot to new objective wave |
| `saipen clean` | Deep repository cleanup |
| `saipen translate` | Isolated 22-language translation build |
| `saipen ship` | Trigger release flow |
