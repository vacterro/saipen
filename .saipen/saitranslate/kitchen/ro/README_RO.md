<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Protocol de continuare pentru agenți de codare IA.** Memorie persistentă a proiectului în
markdown simplu, astfel încât un agent nou fără istoric de chat execută `/saipen continue`
și reia munca în mai puțin de un minut -- fără re-briefing, orice furnizor, orice zi.

**O comandă. Zero amnezie.**

**v7.142.0** | [Spec](SPEC.md) | [Ghid](GUIDE.md) | [RFC](saipen/RFC.md) | [Stil](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformitate](saipen/CONFORMANCE.md) | markdown simplu | zero dependențe | MIT

[![Ghid în română](https://img.shields.io/badge/📖_Ghid_ELI5-ROMÂNĂ-blue?style=for-the-badge)](guides/GUIDE_RO.md)
[![Russian Guide](https://img.shields.io/badge/📖_ELI5_Guide-НА_РУССКОМ-red?style=for-the-badge)](guides/GUIDE_RU.md)
[![English Guide](https://img.shields.io/badge/📖_ELI5_Guide-IN_ENGLISH-blue?style=for-the-badge)](guides/GUIDE_EN.md)
[![Eesti Guide](https://img.shields.io/badge/📖_ELI5_Guide-EESTI-black?style=for-the-badge)](guides/GUIDE_EE.md)
[![Japanese Guide](https://img.shields.io/badge/📖_ELI5_Guide-日本語-red?style=for-the-badge)](guides/GUIDE_JA.md)
[![Ded Voice](https://img.shields.io/badge/👴_Guide-ВЕРСИЯ_ДЕДА-brown?style=for-the-badge)](guides/GUIDE_DED.md)

```text
Utilizator ->  /saipen continue
Agent      ->  citește STATE ("Ce fac chiar acum?")
Agent      ->  citește BOARD ("Ce sarcină preiau?")
Agent      ->  citește next_action (execută comanda)
Agent      ->  Lucrează.
```

### Starea Proiectului > Memoria Modelului
Memoria trăiește în proiect, nu în capul unui model. `Proiect -> Memorie -> LLM` devine `Proiect -> Stare SAIPEN -> LLM`.

### Logica Cheie a Protocolului și Garanții
- **Mașină de Stare Core**: `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Autonomie Zero-Prompt**: Nu au mai rămas to-do-uri deschise? Se tranziționează automat în bucla `HUNT` (scanare bug-uri) → `ADD` (evoluție funcționalități) → `HUNT`. Zero întrebări adresate.
- **Declanșatoare Explicite**: `/saipen clean` (curățare repo), `/saipen translate` (fabrică izolată `.saipen/saitranslate/`), `/saipen markhunt` (audit uscat fără limită, doar înregistrare), `/saipen prepare` (pachetizare muncă pentru predare), `/saipen validate` (verificare conformitate), `/saipen goal` (execuție autonomă pe valuri). Meta/control: `/saipen status` (raport doar-citire), `/saipen stop` (salvare punct de control și oprire). Lista completă: RFC.md § 1.10.
- **Fiabilitate Strictă**: Analiză de intrare în loturi (bilete chirurgicale 1-câte-1), adoptare dirty-tree (nu șterge niciodată munca nesalvată/necomituită), redactare secrete (`sk-***`).

## Proiecte Propulsate de SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Instrument de gestionare a prompt-urilor de înaltă performanță, integrat nativ cu protocolul de memorie SAIPEN.

## Două Straturi

| Strat | Necesar | Scop |
|---|---|---|
| **Core** | ✅ | Continuă munca în siguranță |
| **Maintenance** | Peste Core | Evoluează software-ul fără sarcini explicite |

**Evoluție Automatizată.** Când nu mai rămân to-do-uri deschise, tastează `/saipen`: `HUNT` auditează pentru bug-uri, cod mort, teste care eșuează. Curat? `ADD` construiește următoarea funcționalitate lipsă evidentă, o verifică, apoi caută din nou (`HUNT`). Produsul este matur -> se oprește elegant.

**Modul GOAL.** `/saipen goal <ce dorești>` pivotează panoul (biletele vechi sunt retrogradate, niciodată șterse) și avansează noul obiectiv -- fără întrebări de tipul „să continui?” între bilete, VERIFY/REVIEW nu sunt niciodată omise. SHIP face auto-push către un remote existent; un repo complet nou va întreba o singură dată. Livrarea (shipping) obiectivului nu este nici ea punctul de oprire -- trece direct în mentenanța autonomă HUNT/ADD până când produsul este matur, blocat sau runda își atinge limita (3 valuri / 20 de bilete, apoi salvează punctul de control și raportează).

## Start Rapid

**1. Instalează o singură dată pe aparat** -- învață Claude Code, Gemini, OpenCode, Aider, Antigravity, Codex ?i orice cititor generic de ~/.agents/skills (FreeBuff, etc.):
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Începe un proiect** -- deschide un agent în dosarul tău și tastează:
> `saipen set`

Fără instalare? Lipește o singură linie în orice agent:
> Citește <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md și urmează-le.

Platforma nu este în lista de mai sus (DeepSeek, Qwen, standalone OpenAI etc.)?
Notele specifice fiecărei platforme se află în `extensions/adapters/`.

## Linkuri de Documentație și Specificație
- **[SPEC.md](SPEC.md)** -- arhitectură formală, obiective de proiectare, test de turnesol.
- **[RFC.md](saipen/RFC.md)** -- specificație normativă executată de agenți.
- **[GUIDE.md](GUIDE.md)** -- tutorial pentru oameni și ghiduri ELI5:
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- stilul de comunicare al agentului și definirea vocii.
- **[UI.md](saipen/UI.md)** -- ghid de design UI Win95 Vintage Golden.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- scenarii de testare comportamentale și reguli de validare.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>


