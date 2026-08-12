<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
  <br>
  <img src="assets/__SAIPEN_Alpha.png" alt="SAIPEN Sticker" width="200"/>
</p>

# SAIPEN

**Protocole de continuation pour agents de codage IA.** Mémoire de projet persistante en
markdown brut, pour qu'un agent à froid sans historique de chat exécute `/saipen continue`
et reprenne le travail en moins d'une minute -- sans réexplication, quel que soit le fournisseur ou le jour.

**Une commande. Zéro amnésie.**

**Raccourcis clavier :** `cc` poursuit le contexte du projet jusqu'à la convergence (reprend un objectif actif s'il en existe un), `sss` signale l'état sans toucher au code et `ss` enregistre un point de contrôle puis s'arrête. [Voir la carte complète des 15 touches](saipen/RFC.md#110-command-surface). Les jumeaux cyrilliques fonctionnent aussi : `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Langue de réponse.** L'agent répond par défaut **en estonien** — c'est un réglage, pas une lubie, et rien d'autre dans SAIPEN n'est en estonien. Cela se change à un seul endroit : la ligne `reply_language:` en haut de [`saipen/STYLE.md`](saipen/STYLE.md). `et` estonien, `en` anglais, `ru` russe, `auto` choisit selon la langue de votre message. Le protocole, le code, les commits et tous les documents restent en anglais, quelle que soit la valeur.

**v7.223.8** | [Spécification](SPEC.md) | [Guide](GUIDE.md) | [RFC](saipen/RFC.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformité](saipen/CONFORMANCE.md) | markdown brut | zéro dépendance | MIT

```text

### État du projet > Mémoire du modèle

La mémoire réside dans le projet, pas dans la tête d'un modèle. `Projet -> Mémoire -> LLM` devient `Projet -> État SAIPEN -> LLM`.


## Commands

The full surface is 16 commands; complete details in [RFC § 1.10](saipen/RFC.md#110-command-surface).

| Command | What it does |
|---|---|
| `/saipen set` | Adopt a project |
| `/saipen continue` | Resume exactly where you left off |
| `/saipen plan` | Turn a request or raw queue into tickets |
| `/saipen goal <text>` | Autonomous wave assault on a new objective |
| `/saipen hunt` | Force an immediate defect/improvement scan |
| `/saipen ship` | Version bump, changelog, tag, push |
| `/saipen clean` | Repository cleanup |
| `/saipen validate` | Conformance check |
| `/saipen markhunt` | Dry uncapped audit, record only |
| `/saipen translate` | Isolated translation factory |
| `/saipen prepare` | Package work for handoff |
| `/saipen collect` | Integrate a ready package |
| `/saipen status` | Read-only report |
| `/saipen stop` | Checkpoint and halt |

<sub>`saipen init` and `saipen sub` complete the sixteen; both are called by the protocol, not typed daily.</sub>

**Package keys.** `ee`/`qq` prepare a complete translation or wiki package without integrating; `eee`/`qqq` accept only a ready package, then integrate, verify, review, and push.

**Experimental: saicrew.** Optional bonus layer (`extensions/subs/`, zero Core changes) for running a multi-agent crew — one Core writer plus read-only `saihunt`/`saipython` workers reporting through their own `OUTBOX.md`. Under active live testing, not finalised — see `extensions/subs/crew.md`.

## Two layers

| Layer | Required | Purpose |
|---|---|---|
| **Core** | ✅ | Resume work safely |
| **Maintenance** | On top of Core | Evolve software without task direction |

**Automated evolution.** No open tasks remain, type `/saipen`: `HUNT` audits for bugs, dead code, and failing tests. Clean? `ADD` builds the next obvious missing capability, verifies it, and hunts again. Product mature -> stops gracefully.

**GOAL Mode.** `/saipen goal <what you want>` pivots the board (deprioritises old tickets, never deletes them) and drives the new objective forward — no "should I continue?" between tickets, VERIFY/REVIEW never skipped. SHIP auto-pushes to the existing remote; a brand-new repository still asks once. Shipping a goal is not the end point either — it transitions straight into autonomous HUNT/ADD maintenance until the product is mature, blocked, or the run hits its cap (3 waves / 20 tickets, then checkpoints and reports).

## Quick Start


**1. Installer une fois par machine** -- enseigne à Claude Code, Gemini, OpenCode, Aider, Codex, Antigravity, et tout lecteur générique de `~/.agents/skills` (FreeBuff, etc.) :
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

**2. Démarrer un projet** -- ouvrez un agent dans votre dossier, tapez :
> `saipen set`

Pas d'installation ? Collez une ligne à n'importe quel agent :
> Lire <clone>/saipen/INDEX.md + <clone>/saipen/STYLE.md et les suivre.

Plateforme absente de la liste ci-dessus (DeepSeek, Qwen, OpenAI autonome, etc.) ?
Les notes par plateforme se trouvent dans `extensions/adapters/`.


## Documentation

| Document | What it is |
|---|---|
| [SPEC.md](SPEC.md) | Formal architecture, design goals, litmus test |
| [RFC.md](saipen/RFC.md) | Normative specification agents execute |
| [GUIDE.md](GUIDE.md) | Human tutor and ELI5 guides |
| [STYLE.md](saipen/STYLE.md) | Agent communication style and voice definition |
| [UI.md](saipen/UI.md) | Vintage Golden UI design guidelines |
| [CONFORMANCE.md](saipen/CONFORMANCE.md) | Behavioural test scenarios and validator rules |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [English](guides/GUIDE_EN.md) · 🇪🇪 [Eesti](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Deutsch](guides/GUIDE_DE.md) · 🇫🇷 [Français](guides/GUIDE_FR.md) · 🇪🇸 [Español](guides/GUIDE_ES.md) · 🇮🇹 [Italiano](guides/GUIDE_IT.md)

🇵🇹 [Português](guides/GUIDE_PT.md) · 🇳🇱 [Nederlands](guides/GUIDE_NL.md) · 🇵🇱 [Polski](guides/GUIDE_PL.md) · 🇸🇪 [Svenska](guides/GUIDE_SV.md) · 🇩🇰 [Dansk](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Built with SAIPEN

- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — High-performance prompt management tool built natively around the SAIPEN memory protocol.

## Screenshots

<details>
<summary>Click to expand</summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- source-digest: README.md sha256:7550073ecb7103b2b34a8a8214fb35b3daddfc5bddb641691f1355e40cf8cc7f -->


