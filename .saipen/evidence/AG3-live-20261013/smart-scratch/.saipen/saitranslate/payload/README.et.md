# Smart VAC Cleaner

[English](README.md) · [Русский](README.ru.md) · [Eesti](README.et.md) · [Дед](README.ded.md)

![Smart VAC Cleaner GUI](assets/screenshot.png)

Kaasaskantav, ohutu, kaasaegne prügipuhastaja Windowsile. GUI + CLI + Tegumihaldur.

Ohutu vaikimisi: dry-run, kuni pole antud `--delete`. Kõik kaasaskantavate
rakenduste juured on alati konfigis kirjas; puhastatakse ainult need, mis
selles arvutis reaalselt olemas on, ja ainult tuntud prügimustrid nende sees.
Puuduvad kettad jäetakse vaikselt vahele, vigu ei teki kunagi.

## Mida puhastatakse

| Kiht | Mida | Kus |
|---|---|---|
| Süsteem | Temp, krahhi-dumbid, Exploreri pisipildid, Windows Update'i vahemälu, DNS-vahemälu, prügikast, 100+ rakenduste vahemälusid (brauserid, Node/uv/pip vahemälud, VS Code pere, Eagle, OBS, Discord...) | `%TEMP%`, `%LOCALAPPDATA%`, `%APPDATA%` |
| Deep C: Junk | Uuendajate jäänused, `*.exe.tmp`, Viber QmlWebCache, Yandex.Disk varukoopiad, ODIS logid, `app.asar.bak` jms | `%LOCALAPPDATA%`, `%TEMP%` |
| Kaasaskantavad juured | Tuntud prügimustrid seadistatud juurte sees | `portable_roots` konfigis |
| Kasutaja reeglid | Oma teed + glob-mustrid | `custom_rules` konfigis |

## Ohutus (kaitse sügavuti)

- **Dry-run on füüsiliselt read-only** — GUI nupp "Puhasta" kustutab päriselt (küsib eelnevalt kinnitust), CLI nõuab selgesõnalist `--delete`; dry-run ainult plaanib, ei muta kunagi (mitte unlink/chmod/rmdir, mitte DNS flush, teenuse peatust, prügikasti väljakutset)
- **Must nimekiri**: `C:\`, `C:\Windows`, `USERPROFILE`, Program Files, programmi enda kaust — need on **kasutaja-antud** juured (portable/custom), need lükatakse tagasi: ükski kasutaja juur ei tohi olla kaitstud tee ega selle alam, isegi kui konfig seda küsib. Sisemised ülevaadatud süsteemi sihtmärgid (System Temp, AppData vahemälud, …) ei ole kasutaja juured: neil on oma selgesõnaline ulatus ja oma SafetyGuard juur
- **Kõvakodeeritud portatiivseid juuri pole**: värske konfigi vaikeväärtus on `portable_roots: []`
- **Minimaalne tee sügavus**: madalad teed (vähem kui 5 komponenti) lükatakse tagasi
- **Käivate protsesside kontroll**: rakendus, mis sihtmärki kasutab, jäetakse vahele (rakendusepõhiste protsessinimekirjade järgi); kui protsessitabelit ei saa pärida, jäetakse ka rakendustundlikud sihtmärgid vahele (fail closed); hetkeseis värskendatakse enne iga hävitavat rakenduste gruppi
- **Omaniku katvus**: igal AppData sihtmärgil on tõestatud protsessiomanik või on see selgesõnaliselt process-agnostic (ühised paketi/kompilaatori/draiveri vahemälud) — puudub kaudne `owner=None` väljapääs
- **Sümbollingid / junctions / reparse-punktid lükatakse tagasi**; `..` segmendid kanoniseeritakse ning saadud tee piiratakse sihtmärgijuuriga ja kontrollitakse uuesti — juurest välja viiv `..` lükatakse tagasi
- **Never-delete nimed**: `login data`, `bookmarks`, `cookies`, `history`, `trusted_vault.pb` ja muud — nummerdatud (`Cookies (2)`) ja liit-journali (`Cookies (2)-wal`) variandid taanduvad mehhaaniliselt kaitstud baasnimeks
- **Erandid**: `exclude_patterns` / `exclude_paths` konfigis rakenduvad igale kustutamisele (portable, system, custom, deep sweep)
- **Varukoopiafailid**: üldisi `.bak` taasteartefakte ei kustutata kunagi automaatselt
- Iga kustutamine läbib oma juure `SafetyGuard`i; iga sõlm kustutatava kausta all valideeritakse, nii et kaitstud/erandite all olevad alampuud jäävad alles; loendurid liiguvad ainult pärast kinnitatud kustutamist; vead loendatakse, pole kunagi saatuslikud
- GUI töölõimed ei puuduta kunagi Tk-d; sulgumine puhastuse ajal katkestab ja ootab töölõime enne väljumist

## Nõuded

- Windows 10/11
- Python 3.10+

## Paigaldus

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Paketina (lisab käsu `vac-cleaner`):

```bat
pip install .
vac-cleaner --status
```

Pole Pythonit? Võtke `SmartVACCleaner.exe` GitHubi
[Releases](https://github.com/vacterro/SMART-VAC-CLEANER/releases) lehelt —
täiesti kaasaskantav, konfig ja logid elavad exe kõrval. Release'd
luuakse automaatselt märgistatud buildetist `build-exe` töövoo kaudu;
kui versioon on märgistatud, aga Release lehte pole, töövoog pole veel
lõpetanud (või ebaõnnestus).

## Exe ise ehitamine

```bat
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```

Tulemus: `dist\SmartVACCleaner.exe` (PyInstaller onefile). Iga `v*` teegi
peale ehitab CI exe ja laeb selle artefaktina automaatselt üles.

## GUI

```bat
python _SMART_VAC_CLEANER.py
```

Seitse nuppu: **Puhasta** (päris kustutamine — küsib eelnevalt kinnitust),
**Peata**, **Eelvaade** (füüsiliselt read-only dry-run, näitab, mis kustutataks),
**Paigalda autopuhastuse ülesanne**, **Käivita taustal** (käivitab
eraldiseisva peidetud täispuhastuse taustal), **Välistused** (ära-kustuta
mustrite ja teede muutmine), **Süsteemi sihtmärgid** (riskantsete sihtmärkide
sisse lülitamine — Prügikast, DNS-i vahemälu, Windows Update'i vahemälu;
valik salvestatakse konfigi). Progressiribad kategooriate kaupa, täielik
logiakken; iga käivitus jõuab ka `logs\clean_*.log` faili.

## CLI

CLI on **vaikimisi dry-run** — ainult aruanne, mis kustutataks. Päris
kustutamiseks lisage `--delete`. `--dry-run` sunnib eelvaate ka `--delete`
juures.

| Lipp | Mõju |
|---|---|
| `--cli` | Sundida konsoolirežiim |
| `--portable` / `--system` / `--custom` | Puhastuskihtide valik (vaikimisi dry-run) |
| `--all` | Kõik kihid korraga kasutades **ohutuid** süsteemsihtmärkide vaikeväärtusi (Prügikast / DNS / Windows Update jäävad välja) |
| `--delete` | **Päris kustutamine** (ilma selleta ainult eelvaade) |
| `--dry-run` | Sunnitud eelvaade ka `--delete` juures |
| `--status` | Näita prügi mahtu eesmärkide kaupa; midagi ei kustutata |
| `--analyze-caches` | Otsi AppData vahemälu kaustu > 5 MB |
| `--sys-targets` | Süsteemsihtmärkide loend komadega (`System Temp`, `User Temp`, `Recycle Bin`, ...); tundmatud nimed annavad vea |
| `--exclude` | Lisamustrid eranditeks komadega (`--exclude "*.db,*.tmp"`) |
| `--hidden` | Peida konsooliaken (Tegumihaldurile) |
| `--install-task` | Paigalda igapäevane vaikne täispuhastus |
| `--time HH:MM` | Ülesande käivitusaeg (vaikimisi `09:00`) |

Näited:

```bat
REM kõige eelvaade
python _SMART_VAC_CLEANER.py --cli --all

REM kõige päris kustutamine
python _SMART_VAC_CLEANER.py --cli --all --delete

REM eelvaade, siis kustutamine; --dry-run võidab alati
python _SMART_VAC_CLEANER.py --cli --all --delete --dry-run
```

Kui palju prügi on kogunenud:

```bat
python _SMART_VAC_CLEANER.py --status
```

### Autopuhastus (Tegumihaldur)

```bat
python _SMART_VAC_CLEANER.py --install-task --time 09:00
```

Paigaldab ülesande `SmartVACCleaner` (maksimaalsed õigused, peidetud aken). Eemaldamine:

```bat
schtasks /Delete /TN SmartVACCleaner /F
```

## Konfiguratsioon

`cleaner_config.json` luuakse automaatselt skripti (või exe) kõrvale esimesel
käivitamisel, vaikimisi väärtustega. Kõik teed kanoniseeritakse laadimisel:
kaldkriipsude stiil, lõpuseparaatorid ja `..` segmendid normaliseeritakse,
duplikaadid liidetakse, kaitstud teed (`C:\`, Windows, Program Files, profiil,
programmi enda kaust) ja pesastunud juured lükatakse tagasi hoiatusega.
Näide:

```json
{
  "portable_roots": ["D:\\Portable"],
  "custom_rules": [{"path": "D:\\Apps\\TestApp", "pattern": "*.log"}],
  "exclude_patterns": ["*.db"],
  "exclude_paths": ["C:\\Users\\me\\AppData\\Local\\Important"],
  "auto_clean_interval_hours": 0,
  "lang": "en"
}
```

- `portable_roots`: kaustad, mille tuntud prügialamkaustad pühitakse (nt `Cache`, `Temp`, `Logs`, nummerdatud varukoopiad). Kõik, mis prügimustritele ei sobi, jääb puutumata.
- `custom_rules`: `path` (kaust) + `pattern` (glob, `*` = kogu sisu).
- `exclude_patterns` / `exclude_paths`: täiendavad keelatud kataloogid.
- `lang`: liidese keel — `en` (vaikimisi), `ru`, `et`, `ded`. Sisseehitatud `strings/*.json` asuvad skripti kõrval (või on exe sisse pakitud); oma keele lisamiseks pane sinna `<lang>.json`.

## Testid

```bat
python -m pytest -q
```

Töötab võrguühenduseta, puudutab ainult ajutisi katalooge.

## Dokumentatsioon

Täielik dokumentatsioon [docs/](docs/Home.md): [Ohutus](docs/Safety.md), [CLI Reference](docs/CLI-Reference.md), [Konfiguratsioon](docs/Configuration.md), [Ehitamine ja paigaldus](docs/Build-and-Install.md), [FAQ](docs/FAQ.md).

## Märkused

- Tegumihalduri ülesande paigaldamine nõuab administraatori õigusi (`/rl HIGHEST`).
- Kaasaskantavad juured mittesüsteemsetel ketastel puhastatakse ka ilma adminita (VAC-skeem).
- Projekt pole seotud ühegi müüjaga; kõik teed on tuntud vahemälu/logikataloogid, mida rakendused taastavad.
<!-- source-digest: README.md sha256:0e75f3cd673d01f8f6a5080a4d789367a1122c9dce45ec707a1b9e7b73c14fed -->