<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Jätkuvusprotokoll AI koodimisagentidele.** SAIPEN hoiab projekti mälu tavalises markdown-vormingus, nii et külm agent ilma vestlusajaloota käivitab `/saipen continue`, loeb `STATE.md` -> `BOARD.md` -> aktiivse `LOG.md` lõpu -> `human_note` (kui on määratud), käivitab `next_action` ja jätkab tööd alla minutiga — ilma uuesti juhendamata, mis tahes tarnija, mis tahes päeval.

**Üks käsk. Null sõltuvust. Null amneesiat.**

**Kiirklahvid:** `cc` viib projekti konvergentsini (jätkab käimasolevat eesmärki, kui see on seatud), `sss` näitab olekut koodi puudutamata ja `ss` salvestab kontrollpunkti ning peatub. [Vaata täielikku 15 kiirklahvi kaarti](saipen/RFC.md#110-command-surface). Kirillitsa kaksikud töötavad ka: `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Vastuste keel.** Agent vastab vaikimisi **eesti keeles** — see on säte, mitte veidrus, ja miski muu SAIPEN-is ei ole eestikeelne. Muuda seda ühes kohas: rida `reply_language:` [`saipen/STYLE.md`](saipen/STYLE.md) alguses. `et` eesti, `en` inglise, `ru` vene, `auto` valib selle järgi, mis keeles sa kirjutasid. Protokoll, kood, commitid ja kõik dokumendid jäävad igal väärtusel inglise keelde.

**v7.223.2** | [Spetsifikatsioon](SPEC.md) | [Juhend](GUIDE.md) | [RFC](saipen/RFC.md) | [Stiil](saipen/STYLE.md) | [Kasutajaliides](saipen/UI.md) | [Vastavus](saipen/CONFORMANCE.md) | tavaline markdown | null sõltuvust | MIT
| [BROŠÜÜR](BROCHURE_DED.md) | PEAB TÕLKIMA saitranslate |

```text
Kasutaja ->  /saipen continue
Agent    ->  loeb STATE.md (faas, ülesanne, next_action, režiim, human_note)
Agent    ->  loeb BOARD.md (DOING / TODO / DONE / BLOCKED piletid)
Agent    ->  loeb aktiivse LOG.md lõpu (hiljutised sündmused)
Agent    ->  loeb human_note (kui on määratud, ühekordne juhis)
Agent    ->  käivitab koheselt next_action (käsk)
Agent    ->  laeb faasi dokumendi ainult siis, kui reegleid on vaja
Agent    ->  Töötab.
```

## Kuidas see töötab

**Projekti olek on tugevam kui mudeli mälu.** Mälu elab projektis, mitte mudeli peas. `Projekt -> Mälu -> LLM` muutub vormi `Projekt -> SAIPENi olek -> LLM`.

- **Olekumasina tuum** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Autonoomia ilma viipadeta** — tahvel peatatud (ühtegi teostatavat `TODO`-d pole, `DOING` on tühi) **ja ei ole `BLOCKED`**? Automaatne üleminek `HUNT` (otsib vigu) → `ADD` (arendab funktsioone) → `HUNT`, ühtegi küsimust esitamata. `BLOCKED` olekus olev sessioon ei käivita kunagi automaatset jahti -- ta ootab, kuni inimene lahendab blokaadi (RFC § 2.1).
- **Range töökindlus** — partii sisendi parsimine (kirurgilised 1-haaval piletid), määrdunud puu omaksvõtt (ei kustuta kunagi salvestamata tööd), saladuste redigeerimine (`sk-***`).

## Käsud

Kogu pind on 16 käsku; täielik üksikasjalik kirjeldus [RFC § 1.10](saipen/RFC.md#110-command-surface).

| Käsk | Mida teeb |
|---|---|
| `/saipen set` | Võta projekt omaks |
| `/saipen continue` | Jätka täpselt sealt, kus peatuti |
| `/saipen plan` | Muuda päring või toores tööjärg piletiteks |
| `/saipen goal <text>` | Autonoomne lainerünnak uue eesmärgi vastu |
| `/saipen hunt` | Sunni defektide/paranduste otsing kohe |
| `/saipen ship` | Versioonitõstmine, muudatuste logi, märgis, tõuge |
| `/saipen clean` | Hoidla puhastus |
| `/saipen validate` | Vastavuskontroll |
| `/saipen markhunt` | Kuiv piiramatu audit, ainult kirjed |
| `/saipen translate` | Isoleeritud tõlkevabrik |
| `/saipen prepare` | Paki töö üleandmiseks kokku |
| `/saipen collect` | Integreeri valmis pakett |
| `/saipen status` | Kirjutuskaitstud aruanne |
| `/saipen stop` | Kontrollpunkt ja peatus |

<sub>`saipen init` ja `saipen sub` lõpetavad kuueteistkümne; mõlemat kutsub protokoll, mitte igapäevaselt trükitud.</sub>

**Paketiklahvid.** `ee`/`qq` valmistavad täieliku tõlke- või vikipaketi ette ilma seda lõimimata; `eee`/`qqq` võtavad vastu ainult valmis paketi, seejärel lõimivad, kontrollivad, vaatavad üle ja lükkavad üles.

**Eksperimentaalne: saicrew.** Valikuline boonuskiht (`extensions/subs/`, Core'i muudatusteta) mitme agendiga meeskonna käivitamiseks — üks Core'i kirjutaja pluss kirjutuskaitstud `saihunt`/`saipython` töötajad, kes aruandlevad oma `OUTBOX.md` kaudu. Aktiivse reaalajas testimise all, lõpuni kinnitamata — vaata `extensions/subs/crew.md`.

## Kaks kihti

| Kiht | Nõutav | Eesmärk |
|---|---|---|
| **Tuum** | ✅ | Jätka tööd turvaliselt |
| **Hooldus** | Tuuma peal | Arenda tarkvara edasi ilma ülesanneteta |

**Automatiseeritud evolutsioon.** Avatud ülesandeid ei ole järel, trüki `/saipen`: `HUNT` auditeerib vigade, surnud koodi ja ebaõnnestunud testide suhtes. Puhas? `ADD` ehitab järgmise ilmse puuduva võimekuse, kontrollib seda ja jahib uuesti. Toode on valmis -> peatub sujuvalt.

**GOAL-režiim.** `/saipen goal <mida soovid>` pöörab tahvlit (vanad piletid viiakse madalamale prioriteedile, aga ei kustutata kunagi) ja viib uue eesmärgi edasi — ilma piletite vahel "kas ma peaksin jätkama?" küsimata, VERIFY/REVIEW ei jäeta kunagi vahele. SHIP teeb automaatse push-i olemasolevasse kaughoidlasse; täiesti uus hoidla küsib siiski ühe korra. Eesmärgi tarnimine pole samuti lõpp-punkt — see läheb otse autonoomse HUNT/ADD hoolduse alla, kuni toode on küps, blokeeritud või käivitus jõuab oma piirini (3 lainet / 20 piletit, seejärel teeb kontrollpunkti ja aruande).

## Kiire alustus

**1. Paigalda üks kord masina kohta** — õpetab Claude Code'i, Codex'i, Geminit, OpenCode'i, Aiderit, Antigravityt ja iga üldine `~/.agents/skills`-lugeja (FreeBuff, jne.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>Mida see puudutab, et üllatusi poleks: skript lisab märgistatud ploki `<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->` teie agendi juhendfailidesse (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`, `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`) — tehes enne varukoopia `.bak` — ja kopeerib protokolli vastavatesse oskuste kaustadesse. Mitte midagi väljaspool neid teid, ei deemonit, ei võrgukutseid.</sub>

**Kahetsed otsust?** Üks käsk võtab tagasi:
```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```
See eemaldab täpselt märgistatud ploki (jättes ülejäänud faili puutumata), salvestab enne koopia `.uninstalled.bak` ja eemaldab oskuste kaustad.

**2. Alusta projekti** — ava agent oma kaustas ja trüki:
> `saipen set`

Pole paigaldatud? Kleebi üks rida mis tahes agendile:
> Read <clone>/saipen/BOOT.md first (cold-start kernel), then <clone>/saipen/INDEX.md + <clone>/saipen/STYLE.md and follow them.

Platvormi pole ülaltoodud loendis (DeepSeek, Qwen, eraldiseisev OpenAI jne)?
Platvormipõhised märkused asuvad kaustas `extensions/adapters/`.

## Dokumentatsioon

| Dokument | Mis see on |
|---|---|
| [SPEC.md](SPEC.md) | Ametlik arhitektuur, disainieesmärgid, lakmustest |
| [RFC.md](saipen/RFC.md) | Normatiivne spetsifikatsioon, mida agendid täidavad |
| [GUIDE.md](GUIDE.md) | Inimetuutor ja ELI5 juhendid |
| [STYLE.md](saipen/STYLE.md) | Agendi suhtlusstiil ja hääle määratlus |
| [UI.md](saipen/UI.md) | Vintage Golden UI disainijuhised |
| [CONFORMANCE.md](saipen/CONFORMANCE.md) | Käitumuslikud testistsenaariumid ja validaatori reeglid |

<details>
<summary><b>Kõik 33 tõlgitud juhendit</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [English](guides/GUIDE_EN.md) · 🇪🇪 [Eesti](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Deutsch](guides/GUIDE_DE.md) · 🇫🇷 [Français](guides/GUIDE_FR.md) · 🇪🇸 [Español](guides/GUIDE_ES.md) · 🇮🇹 [Italiano](guides/GUIDE_IT.md)

🇵🇹 [Português](guides/GUIDE_PT.md) · 🇳🇱 [Nederlands](guides/GUIDE_NL.md) · 🇵🇱 [Polski](guides/GUIDE_PL.md) · 🇸🇪 [Svenska](guides/GUIDE_SV.md) · 🇩🇰 [Dansk](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Ehitatud SAIPEN-iga

- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Kõrge jõudlusega viipade haldamise tööriist, mis on ehitatud SAIPENi mäluprotokolli ümber.

## Ekraanitõmmised

<details>
<summary>Vajuta avamiseks</summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- source-digest: README.md sha256:7550073ecb7103b2b34a8a8214fb35b3daddfc5bddb641691f1355e40cf8cc7f -->



