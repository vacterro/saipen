<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Przewodnik SAIPEN (Polski)

SAIPEN to notatnik pamięci w folderze `.saipen/` dla agentów AI.

**Szybkie klawisze:** `cc` kontynuuje aktywny Goal Mode, `sss` pokazuje stan bez dotykania kodu, a `ss` zapisuje punkt kontrolny i zatrzymuje się. [Zobacz pełną mapę 14 klawiszy](../saipen/RFC.md#110-command-surface). Cyrylickie bliźniaki też działają: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

## Szybki Start

1. **Zainstaluj raz na maszynę:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Uruchom w projekcie:**
> `saipen set`

3. **Praca:**
> `saipen`

## Polecenia

| Polecenie | Akcja |
|---|---|
| `saipen set` | Zainicjuj folder pamięci `.saipen/` |
| `saipen continue` | Wznów pracę z notatek |
| `saipen stop` | Zapisz postęp i zatrzymaj |
| `saipen status` | Odczytaj tablicę i status |
| `saipen goal <text>` | Przejdź do nowego celu |
| `saipen clean` | Głębokie czyszczenie repozytorium |
| `saipen translate` | Izolowana kompilacja tłumaczeń w 32 językach |
| `saipen markhunt` | Głęboki, nieograniczony audyt -- tylko zapisuje ustalenia |
| `saipen prepare` | Pakuje pracę do przekazania następnemu agentowi |
| `saipen ship` | Uruchom przepływ wydania |

## Warto wiedzieć
- Niezacommitowane zmiany po powrocie do projektu? Normalka -- SAIPEN commituje dopiero przy `ship`, nie na każdym kroku. Agent najpierw sprawdza, czyje to zmiany, zanim czegokolwiek dotknie.
- Chcesz, żeby pamiętał prawdziwą decyzję architektoniczną? Wrzuć ją do `.saipen/KNOWLEDGE/`, jako plik `decisions.md` albo ponumerowane pliki `ADR-001.md`.
- Brak gita albo shella na tej maszynie? Agent mówi to wprost (`mode`, `WAIT: <category> -- <pytanie>`), zamiast zgadywać (kategoria jest jedną z siedmiu: `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init`; mówi, jaka odpowiedź odblokowuje sytuację)
- Chcesz siatkę bezpieczeństwa? `python <klon-saipen>/tools/install_hook.py` instaluje sprawdzenie przed commitem.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
