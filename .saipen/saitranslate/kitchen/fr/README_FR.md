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

**Raccourcis clavier :** `cc` poursuit un Goal Mode actif, `sss` signale l’état sans toucher au code et `ss` enregistre un point de contrôle puis s’arrête. [Voir la carte complète des 13 touches](saipen/RFC.md#110-command-surface). Les jumeaux cyrilliques fonctionnent aussi : `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`.

**Langue de réponse.** L'agent répond par défaut **en estonien** — c'est un réglage, pas une lubie, et rien d'autre dans SAIPEN n'est en estonien. Cela se change à un seul endroit : la ligne `reply_language:` en haut de [`saipen/STYLE.md`](saipen/STYLE.md). `et` estonien, `en` anglais, `ru` russe, `auto` choisit selon la langue de votre message. Le protocole, le code, les commits et tous les documents restent en anglais, quelle que soit la valeur.

**v7.184.0** | [Spécification](SPEC.md) | [Guide](GUIDE.md) | [RFC](saipen/RFC.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformité](saipen/CONFORMANCE.md) | markdown brut | zéro dépendance | MIT

```text
Utilisateur -> /saipen continue
Agent       -> lit STATE ("Que dois-je faire maintenant ?")
Agent       -> lit BOARD ("Quelle tâche dois-je reprendre ?")
Agent       -> lit next_action (exécute la commande)
Agent       -> Travaille.
```

### État du projet > Mémoire du modèle
La mémoire réside dans le projet, pas dans la tête d'un modèle. `Projet -> Mémoire -> LLM` devient `Projet -> État SAIPEN -> LLM`.

### Logique clé du protocole et garanties
- **Machine d'état centrale** : `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`
- **Autonomie sans prompt** : Plus de to-dos ouvertes ? Transition automatique vers la boucle `HUNT` (analyse des bugs) → `ADD` (évolution des fonctionnalités) → `HUNT`. Zéro question posée.
- **Déclencheurs explicites** : `/saipen clean` (nettoyage de dépôt), `/saipen translate` (usine isolée `.saipen/saitranslate/`), `/saipen markhunt` (audit à sec non plafonné, enregistre uniquement), `/saipen prepare` (paquète le travail pour le passage de relais), `/saipen validate` (vérification de conformité), `/saipen goal` (exécution autonome par vagues). Méta/contrôle : `/saipen status` (rapport en lecture seule), `/saipen stop` (point de contrôle et arrêt). Liste complète : RFC.md § 1.10.
- **Fiabilité stricte** : Analyse des entrées par lots (tickets chirurgicaux 1 par 1), adoption d'arbre de travail non propre (ne supprime jamais le travail non validé), masquage des secrets (`sk-***`).
- **En développement -- saicrew** : une couche bonus optionnelle (`extensions/subs/`, sans changement au Core) pour faire tourner une équipe multi-agents -- un Core rédacteur plus des workers en lecture seule `saihunt`/`saipython`, qui rapportent via leur propre `OUTBOX.md`. En test actif en conditions réelles, pas encore vérifié de bout en bout -- voir `extensions/subs/crew.md`.

## Projets propulsés par SAIPEN
- ⚡ **[FastPrompter](https://github.com/vacterro/fastprompter)** — Outil de gestion de prompts haute performance nativement intégré avec le protocole de mémoire SAIPEN.

## Deux couches

| Couche | Requis | Objectif |
|---|---|---|
| **Core** | ✅ | Continuer le travail en toute sécurité |
| **Maintenance** | Au-dessus du Core | Faire évoluer le logiciel sans assignation de tâche |

**Évolution automatisée.** Plus de to-dos ouvertes, tapez `/saipen` : `HUNT` recherche les bugs, le code mort, les tests échoués. Propre ? `ADD` construit la prochaine capacité manquante évidente, la vérifie et lance à nouveau un hunt. Le produit est mûr -> s'arrête proprement.

**Mode GOAL.** `/saipen goal <ce que vous voulez>` pivote le tableau (anciens tickets rétrogradés, jamais supprimés) et fait avancer le nouvel objectif de manière autonome -- pas de « dois-je continuer ? » entre les tickets, VERIFY/REVIEW jamais ignorés. SHIP pousse automatiquement vers un dépôt distant existant ; un tout nouveau dépôt demande toujours une confirmation une fois. Livrer l'objectif n'est pas le point d'arrêt non plus -- il bascule directement dans la maintenance autonome HUNT/ADD jusqu'à ce que le produit soit mûr, bloqué ou que la session atteigne sa limite (3 vagues / 20 tickets, puis enregistre un point de contrôle et rapporte).

## Démarrage rapide

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
> Lire <clone>/saipen/RFC.md + <clone>/saipen/STYLE.md et les suivre.

Plateforme absente de la liste ci-dessus (DeepSeek, Qwen, OpenAI autonome, etc.) ?
Les notes par plateforme se trouvent dans `extensions/adapters/`.

## Liens de documentation & spécification
- **[SPEC.md](SPEC.md)** -- architecture formelle, objectifs de conception, test du tournesol.
- **[RFC.md](saipen/RFC.md)** -- spécification normative exécutée par les agents.
- **[GUIDE.md](GUIDE.md)** -- tutoriel humain & guides ELI5 :
  - 🇷🇺 [Русский](guides/GUIDE_RU.md) | 🇺🇸 [English](guides/GUIDE_EN.md) | 🇪🇪 [Eesti](guides/GUIDE_EE.md) | 🇯🇵 [日本語](guides/GUIDE_JA.md) | 👴 [Версия Деда](guides/GUIDE_DED.md)
  - 🇺🇦 [Українська](guides/GUIDE_UK.md) | 🇩🇪 [Deutsch](guides/GUIDE_DE.md) | 🇫🇷 [Français](guides/GUIDE_FR.md) | 🇪🇸 [Español](guides/GUIDE_ES.md) | 🇮🇹 [Italiano](guides/GUIDE_IT.md)
  - 🇵🇹 [Português](guides/GUIDE_PT.md) | 🇳🇱 [Nederlands](guides/GUIDE_NL.md) | 🇵🇱 [Polski](guides/GUIDE_PL.md) | 🇸🇪 [Svenska](guides/GUIDE_SV.md) | 🇩🇰 [Dansk](guides/GUIDE_DA.md)
  - 🇫🇮 [Suomi](guides/GUIDE_FI.md) | 🇳🇴 [Norsk](guides/GUIDE_NO.md) | 🇨🇳 [中文](guides/GUIDE_ZH.md) | 🇰🇷 [한국어](guides/GUIDE_KO.md) | 🇹🇭 [ไทย](guides/GUIDE_TH.md) | 🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) | 🇸🇦 [العربية](guides/GUIDE_AR.md) | 🇮🇱 [עברית](guides/GUIDE_HE.md)
  - 🇹🇷 [Türkçe](guides/GUIDE_TR.md) | 🇮🇳 [हिन्दी](guides/GUIDE_HI.md) | 🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) | 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) | 🇨🇿 [Čeština](guides/GUIDE_CS.md) | 🇷🇴 [Română](guides/GUIDE_RO.md)
  - 🇭🇺 [Magyar](guides/GUIDE_HU.md) | 🇧🇬 [Български](guides/GUIDE_BG.md) | 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) | 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)
- **[STYLE.md](saipen/STYLE.md)** -- style de communication de l'agent & définition de la voix.
- **[UI.md](saipen/UI.md)** -- directives de conception d'interface Win95 Doré Sombre.
- **[CONFORMANCE.md](saipen/CONFORMANCE.md)** -- scénarios de test comportemental & règles du validateur.

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

## ## Captures d'écran

<details>
<summary>Cliquez pour déplier</summary>

<img src="assets/screenshot-freebuff.png" alt="Instructions de l'agent FreeBuff" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set dans nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="Capture d'écran saipen 2026-08-01" width="600"/>

</details>
