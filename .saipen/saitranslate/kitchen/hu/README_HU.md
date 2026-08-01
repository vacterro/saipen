<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Matrica" width="200"/>
</p>

# SAIPEN

**Folytatási protokoll AI kódoló ágensek számára.** Tartós projektmemória egyszerű
markdown formátumban, így egy előzmények nélküli ágens a `/saipen continue`
paranccsal egy percen belül folytatja a munkát -- újratájékoztatás nélkül, bármelyik szolgáltatóval, bármelyik nap.

**Egyetlen parancs. Zéró amnézia.**

**Gyorsbillentyűk:** a `cc` folytat egy aktív Goal Mode-ot, az `sss` kód érintése nélkül jelzi az állapotot, az `ss` pedig menti az ellenőrzőpontot és megáll. [Lásd a teljes 11 billentyűs térképet](saipen/RFC.md#110-command-surface). A cirill ikrek is működnek: `сс`, `ссс`, `аа`, `ее`, `рр`.

**v7.157.0** | [Spec](SPEC.md) | [Útmutató](GUIDE.md) | [RFC](saipen/RFC.md) | [Stílus](saipen/STYLE.md) | [UI](saipen/UI.md) | [Megfelelőség](saipen/CONFORMANCE.md) | egyszerű markdown | zéró függőség | MIT

[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Felhasználó ->  /saipen continue
Ágens       ->  beolvassa a STATE fájlt ("Mit csináljak most?")
Ágens       ->  beolvassa a BOARD fájlt ("Milyen feladatot vegyek át?")
Ágens       ->  beolvassa a next_action-t (végrehajtja a parancsot)
Ágens       ->  Dolgozik.
```

### Projektállapot > Modellmemória
Memória a projektben él, nem a modell fejében. `Projekt -> Memória -> LLM`-ből `Projekt -> SAIPEN Állapot -> LLM` lesz.

### Főbb protokoll-logika és garanciák
- **Core Állapotgép**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Prompt-mentes autonómia**: Nem maradt nyitott teendő? Automatikusan átlép a `HUNT` (hibák keresése) → `ADD` (funkciók fejlesztése) → `HUNT` ciklusba. Nulla kérdés.
- **Kifejezett indítók (Explicit Triggers)**: `/saipen clean` (repo tisztítás), `/saipen translate` (elkülönített `.saipen/saitranslate/` gyár), `/saipen markhunt` (száraz, korlátlan audit, csak rögzít), `/saipen prepare` (munka csomagolása átadáshoz), `/saipen validate` (megfelelőségi ellenőrzés), `/saipen goal` (autonóm hullám-végrehajtás). Meta/vezérlés: `/saipen status` (csak olvasható jelentés), `/saipen stop` (ellenőrzési pont rögzítése és leállítás). Teljes lista: RFC.md § 1.10.
- **Szigorú megbízhatóság**: Kötegelt bemenetfeldolgozás (sebészi pontosságú 1-esével jegyek), piszkos fa elfogadás (dirty-tree adoption - soha nem törli a nem commitolt munkát), titkok kitakarása (`sk-***`).

## SAIPEN által hajtott projektek
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Nagy teljesítményű promptkezelő eszköz, amely natívan integrálva van a SAIPEN memóriaprotokollal.

## Két réteg

| Réteg | Szükséges | Cél |
|---|---|---|
| **Mag (Core)** | ✅ | A munka biztonságos folytatása |
| **Karbantartás (Maintenance)** | A Mag tetején | A szoftver fejlesztése feladatkiosztás nélkül |

**Automatizált evolúció.** Nem maradt nyitott teendő? Írd be a `/saipen` parancsot: a `HUNT` átvizsgálja a rendszert hibák, halott kódok és meghiúsult tesztek után. Tiszta? Az `ADD` megépíti a következő egyértelműen hiányzó funkciót, ellenőrzi, majd újra vadászik (`HUNT`). A termék érett -> méltósággal leáll.

**GOAL Mód.** A `/saipen goal <amit szeretnél>` elforgatja a táblát (a régi jegyek háttérbe szorulnak, de soha nem törlődnek) és előre viszi az új célt -- nincs "folytassam?" a jegyek között, a VERIFY/REVIEW soha nem marad el. A SHIP automatikusan pushol egy meglévő távoli tárolóba; egy teljesen új repo még egyszer rákérdez. A cél leszállítása nem a végpont -- közvetlenül az autonóm HUNT/ADD karbantartásba lép, amíg a termék be nem érik, le nem blokkol, vagy a futás el nem éri a korlátot (3 hullám / 20 jegy, majd ellenőrzési pontot hoz létre és jelent).

## Gyors kezdés

**1. Telepítés gépenként egyszer** -- megtanítja a Claude Code, Gemini, OpenCode, Aider, Codex, Antigravity és bármely általános `~/.agents/skills`-olvasó (FreeBuff, stb.) eszközöket:
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Projekt indítása** -- nyiss meg egy ágenst a mappádban, és írd be:
> `saipen set`

Nincs telepítés? Másolj be egy sort bármelyik ágensnek:
> Beolvasni: <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md és követni őket.

A platformod nincs a fenti listában (DeepSeek, Qwen, önálló OpenAI stb.)?
Platformspecifikus megjegyzések az `extensions/adapters/` mappában találhatók.

## Dokumentáció és specifikációs linkek
- **[SPEC.md](SPEC.md)** -- formális architektúra, tervezési célok, lakmuszteszt.
- **[RFC.md](saipen/RFC.md)** -- normatív specifikáció, amelyet az ágensek hajtanak végre.
- **[GUIDE.md](GUIDE.md)** -- emberi útmutató és ELI5 leírások:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- az ágens kommunikációs stílusa és hangjának meghatározása.
- **[UI.md](saipen/UI.md)** -- Sötét Arany Win95 UI tervezési irányelvek.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- viselkedési tesztforgatókönyvek és ellenőrző szabályok.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>


