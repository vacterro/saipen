# SAIHANDOFF: VAC Smart Cleaner Rule & Engine Enhancement

**From:** Incident Resolution Task (FFS Disk Overflow Catastrophe)  
**Date:** 2026-10-02  
**Target Project:** `V:\___VAC\__K\__CODE\_PY\_SMART_VAC_CLEANER`  
**Target Roles:** `saipython` / `saihunt` / `saibuilder`  
**Priority:** P1 (Preventing Multi-Drive Disk Exhaustion)

---

## 1. Контекст инцидента
В результате сбоя правил FreeFileSync на дисках бэкапов (`E:`, `G:`, `R:`, `S:`, `M:`, `K:`, `P:`) скопилось более **480 ГБ неутилизированного мусора**, что привело к заполнению диска `E:` до ровно 0 байт и критическому переполнению дисков `G:`, `R:`, `P:`. 

Утилита `_SMART_VAC_CLEANER` этот мусор не обнаруживала и не удаляла из-за ограниченных конфигураций корней и отсутствия сигнатур современного агентного/разработческого мусора.

---

## 2. Что необходимо улучшить агенту `_SMART_VAC_CLEANER`

### А. Расширить `cleaner_config.json` корнями `__K`
Текущий `cleaner_config.json` отслеживает только `__P`:
```json
"portable_roots": [
    "V:\\___VAC\\__P",
    "G:\\__SAVE_G\\__P",
    "P:\\__SAVE_P\\___VAC\\__P",
    "R:\\__SAVE_R\\__P",
    "U:\\___VAC\\__P"
]
```
**Задача:** Добавить поддержку корней бэкапов `__K`:
- `E:\__SAVE_E\__K`
- `R:\__SAVE_R\__K`
- `G:\__SAVE_G\__K`
- `S:\__SAVE_S\__K`
- `M:\__SAVE_M\__K`
- `K:\__SAVE_K\__K`
- `P:\__SAVE_P\_GDRIVE_SYNC\__K`
- `P:\__SAVE_P\___VAC\__K`

### Б. Внедрить новые сигнатуры мусора
Добавить в базу правил очистки (`_SMART_VAC_CLEANER.py`) следующие категории:
1. **Агентные и релизные артефакты:**
   - `.release-work/` (съедало 26+ ГБ в одном проекте)
   - `_vtmp/` (временные git worktree кэши субагентов)
   - `__TO_AUDIT/` (снапшоты архивов, висевшие по 34 ГБ)
2. **Сборки и веб-дистрибутивы:**
   - `dist/`, `dist-*/`, `build/`, `out/`, `mock-cdn/`
   - `coverage/`, `.nyc_output/`
   - `.eslintcache`, `*.tsbuildinfo`
3. **Пакетные менеджеры и компиляторы:**
   - `.pnpm-store/`, `.pnpm/`, `.yarn/`, `.bun/`
   - `.cargo/registry/`, `.cargo/git/`, `.rustup/`
   - `.nuget/packages/`, `.gradle/`, `.m2/repository/`
   - `.zig-cache/`, `zig-out/`
4. **Репозитории `.git` на бэкапах:**
   - В папках `__SAVE_*` папки `.git` дублируются сотнями, сжирая pack-файлами гигабайты. Создать правило для зачистки `.git` в корнях бэкапов (с защитой источников на `V:`).

### В. Исправить удаление файлов с атрибутами Read-Only/System на Windows
При удалении через `os.remove` / `shutil.rmtree` на NTFS часто возникает `[WinError 5] Access is denied` из-за атрибутов только для чтения или hidden/system у git-объектов.
**Решение для движка удаления:**
```python
import ctypes
import os
import stat

def force_delete_entry(func, path, excinfo):
    try:
        # Сброс Win32 атрибутов в FILE_ATTRIBUTE_NORMAL (0x80)
        ctypes.windll.kernel32.SetFileAttributesW(path, 0x80)
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        func(path)
    except Exception:
        pass
```

---

## 3. Критерии приёмки (Verification Gate)
1. Запуск сканирования `_SMART_VAC_CLEANER` на корнях `__K` видит все тестовые мусорные директории.
2. Безопасность: папки личных документов, фото, архивов и исходников на `V:` защищены whitelist/blacklist механикой.
3. Очистка не падает на readonly файлах и pack-файлах git.
