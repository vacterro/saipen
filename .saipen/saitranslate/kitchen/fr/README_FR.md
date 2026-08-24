<p align="center">
  <img src="assets/SAIPEN_TEXT1.png" alt="SAIPEN Logo"/>
</p>

<div align="center">
  <h3><a href="README.ee.md">🇪🇪 LOE SEDA EESTI KEELES / ESTONIAN 🇪🇪</a></h3>
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="README.ded.md">👴 Дед-Версия (Russian)</a> &nbsp;|&nbsp;
  <a href="README.ja.md">🇯🇵 日本語 (Japanese)</a>
</div>

# SAIPEN

**Protocole de continuation pour les agents d'écriture de code AI.**La mémoire du projet vit en clair
dans des fichiers Markdown à l'intérieur du projet(`.saipen/`), donc tout agent froid compatible —
aucun historique de chat, aucune mémoire de session — peut exécuter`/saipen continue`, lire le
persisté`next_action`, et reprendre le travail sans demander à l'utilisateur de tout réexpliquer
rien. L'état appartient au projet, pas à la mémoire d'un seul fournisseur de modèles.

**Une seule commande pour reprendre. État en fichiers plats. Contrats vérifiés par machine.**

Le dépôt se valide lui-même à chaque push ; install, état, vérifications, et
l'installation est locale — aucun service cloud, aucun démon, aucune base de données.

[![Validation](https://github.com/vacterro/saipen/actions/workflows/validate.yml/badge.svg)](https://github.com/vacterro/saipen/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
[![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)

**v7.228.0** | [Spécifications](SPEC.md) | [Guide](GUIDE.md) | [Noyau](saipen/CORE.md) | [Maintenance](saipen/MAINTENANCE.md) | [Style](saipen/STYLE.md) | [Interface utilisateur](saipen/UI.md) | [Conformité](saipen/CONFORMANCE.md) |MIT

**Raccourcis clavier :** `cc` poursuit le contexte du projet jusqu'à la convergence (reprend un objectif actif s'il en existe un), `sss` signale l'état sans toucher au code et `ss` enregistre un point de contrôle puis s'arrête. [Voir la carte complète des 19 touches](saipen/RFC.md#110-command-surface). Les jumeaux cyrilliques fonctionnent aussi : `сс`, `ссс`, `аа`, `ее`, `еее`, `рр`. `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.

```text
Project
  |
  +-- .saipen/STATE.md ------ what is happening right now (phase, ticket, mode, next_action)
  +-- .saipen/BOARD.md ------ what work exists (DOING / TODO / DONE / BLOCKED)
  +-- .saipen/LOG.md -------- why the project reached this state (event history)
  +-- .saipen/KNOWLEDGE/ ---- what durable facts must survive sessions
          |
          v
   /saipen continue
          |
          v
      cold agent
          |
          v
     next_action -> work -> checkpoint -> next ticket
```

## Ce qui persiste

La mémoire du projet en cours de vie se trouve dans`.saipen/`— des fichiers simples que vous pouvez lire, comparer et
commettre à côté du code. Un agent froid répond à cinq questions provenant des fichiers
seul :

|Fichier / champ|Réponses|
|---|---|
| `STATE.md` |Qu'est-ce qui se passe actuellement ?(phase, ticket actif, mode d'exploitation, blocage) |
| `BOARD.md` |Quel travail existe / quel travail est actif ?(graphique des tickets : EN COURS, À FAIRE, TERMINÉ, BLOQUÉ) |
| `LOG.md` |Pourquoi le projet a-t-il atteint cet état ?(graphique d'événements append-only) |
| `KNOWLEDGE/` |Quelles faits durables du projet doivent survivre aux sessions ?|
| `next_action` (dans`STATE.md`) |Quelle action exacte l'agent suivant doit-il exécuter ?|

C'est un contrat de point de contrôle, pas une suggestion de conception :`saipen stop`et chaque
transition de ticket écrit les fichiers dans un ordre fixe, et le résultat est vérifié par
un validateur. Rien n'est stocké dans une base de données hébergée, et rien n'est perdu lorsque
la session se termine.

## Démarrage rapide

**1. Installez une seule fois par machine**— enseigne à Claude Code, Codex, Gemini, OpenCode,
Aider, Antigravity, et tout lecteur générique`~/.agents/skills`reader(FreeBuff, etc.):

```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

<sub>What that touches, so nothing is a surprise: it appends a marked
`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->`bloc vers l'instruction de l'agent
fichiers que vous avez déjà(`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`)— en les sauvegardant dans`.bak`d'abord —
et copie le protocole dans les dossiers de compétences correspondants. Rien en dehors de ceux-ci
chemins, pas de démon, pas d'appels réseau.</sub>

**2. Démarrer un projet**— ouvrir un agent dans votre dossier, taper :

> `saipen set`

**Aucune installation ?**Coller une seule ligne dans n'importe quel agent :

> Lire&lt;clone&gt;/saipen/BOOT.md d'abord(noyau de démarrage froid), puis&lt;clone&gt;/saipen/INDEX.md +&lt;cloner&gt;/saipen/STYLE.md et suivez-les.

**Vous avez changé d'avis ?**Une seule commande le remet en place :

```bash
powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
bash bootstrap/uninstall.sh                                         # macOS / Linux
```

Il supprime exactement le bloc marqué(en laissant le reste de votre fichier intact), enregistre
a `.uninstalled.bak`faites d'abord une copie, puis supprimez les dossiers de compétences.

## Pourquoi ne pas utiliser simplement l'historique des conversations ?

SAIPEN cible un échec spécifique : un agent de codage IA qui ne se souvient de rien
une fois que la session se termine. D'autres outils et habitudes couvrent en partie ce problème :

|Approche|À quoi il sert|Ce qu'il ne transporte pas|
|---|---|---|
|Historique des conversations / mémoire du modèle|Convenant, sans configuration|Dépendant de la session et du fournisseur ; non stocké avec le projet, donc un agent froid ne le voit jamais|
|Statique`AGENTS.md`Fichier / instruction|Règles et conventions durables|Ne représente pas par lui-même l'état de la tâche en cours,`next_action`, ou l'historique de récupération|
|Suivi des problèmes / TODO|Gestion des tâches et du backlog|Ne définit pas par lui-même les sémantiques de continuation de l'agent — ce qu'un agent froid doit lire et exécuter lors de la reprise|
| **SAIPEN** |L'état d'exécution en temps réel, la file d'attente de travail, l'historique des événements, la connaissance durable et les règles de continuation vérifiables par machine — dans des fichiers simples à côté du code|Rien ; cette combinaison est le contrat|

La différence n'est pas un seul fichier. C'est que SAIPEN effectue l'étape de reprise
vérifiable par machine : l'action première d'un agent froid après`/saipen continue`est
dictée par le contenu persisté`next_action`et vérifiée par un validateur, pas
reconstituée à partir de la mémoire.

## Preuves d'ingénierie

SAIPEN associe un protocole de fichier simple normatif avec une implémentation exécutable, orientée vers l'échec
vérifications. Le dépôt illustre la conception de protocole/machine à états, Python
outils, état dirigé par schéma, raisonnement de récupération, tests de régression,
limites des workflows multi-agents, et discipline de spécification.

- **Contrat conçu.** [SPEC.md](SPEC.md)définit le modèle de continuation basé sur des fichiers
et le contrat stable sur disque ;[CORE.md](saipen/CORE.md)
et[MAINTENANCE.md](saipen/MAINTENANCE.md)définissent le comportement normatif actuel.
- **État vérifié par machine.**Le validateur uniquement stdlib canonique
  [validateur](tools/validate.py)lit le live
  [schéma d'état](extensions/schemas/state.schema.json)et vérifie la phase
des transitions, dépendances des billets, liens du graphe d'événements, invariants interdocuments
capacités et état de récupération.
- **Couverture des échecs.** [CONFORMANCE.md](saipen/CONFORMANCE.md)carte
les exigences à[fixtures de scénario](tests/scenarios/); le
  [exécuter les cas de passage/échec structurels](tools/run_scenarios.py)y compris l'état de récupération corrompu, les transitions invalides, les cycles de dépendance et
les restrictions en lecture seule.
Contrôles de régression.
- **** [audit_checks.py](tools/audit_checks.py)modifie
des copies connues pour être correctes et prouve que les vérifications du validateur peuvent tout de même devenir rouges, plutôt
que de considérer une vérification permanemment verte comme une preuve.
- **Couche exécutable.** [saipen.py](tools/saipen.py)fournit un état journalisé
opérations ;[bootstrap/](bootstrap/)contient l'installation, la désinstallation et l'export
assistants, avec une optionnelle[installation de l'hébergeur de pré-validation](tools/install_hook.py).
- **Choix explicites.**L'état du protocole principal est des fichiers normaux sans dépendance d'exécution
dépendance. La validation canonique et les outils CLI nécessitent Python, mais utilisent uniquement
sa bibliothèque standard et n'ont besoin d'aucun`pip`installation.

## Architecture

Trois couches, dépendances strictement unidirectionnelles :

```text
CORE            continuation / state / checkpoint / validation       required
  └─ MAINTENANCE   autonomous HUNT / ADD / CLEAN evolution           optional, on top of Core
       └─ GOAL MODE / SUBAGENTS   opt-in throughput/execution        optional
```

Le noyau ne dépend pas de la maintenance : avec l'évolution autonome désactivée, SAIPEN
reste toujours un protocole de continuation complet — un agent froid peut toujours reprendre.

- **Machine d'état du noyau** — `INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`.
- **Maintenance autonome**— plateau arrêté(rien de fonctionnel dans`## TODO`,
rien dans`## DOING`)et non`BLOCKED`? Transitions automatiques`HUNT` (détecter les bogues)
  → `ADD` (évoluer les fonctionnalités) → `HUNT`, aucune question posée. Une session assise à
  `BLOCKED`ne chasse jamais automatiquement
  ([Maintenance § 2.1](saipen/MAINTENANCE.md#21-autonomous-transitions)).
- **Mode Objectif** — `/saipen goal <objective>`pivote le plateau et exécute le
objectif vers l'avant via VERIFY/REVIEW, tombant dans l'entretien autonome
jusqu'à ce que la règle de finition s'active ou que l'exécution atteigne sa limite(3 vagues / 20 tickets,
puis les points de contrôle et les rapports) ([Maintenance § 2.4](saipen/MAINTENANCE.md#24-goal-mode-autonomous-execution)).
- **Renforcement**— l'entrée par lots est analysée en tickets individuels précis
  (CORE § 1.8); la continuation de l'arbre sale préserve les travaux non validés(CORE § 1.5);
les valeurs similaires à des secrets sont masquées dans les journaux(`sk-***`) (CORE § 1.2).

## Commandes courantes

Points d'entrée quotidiens ; la surface complète actuelle se trouve dans
[Core § 1.10](saipen/CORE.md#110-command-surface).

|Commande|Fait|
|---|---|
| `/saipen set` |Adopter un projet : créer`.saipen/`état|
| `/saipen continue` |Reprendre à partir de l'état du projet sauvegardé — aucun rébriefing|
| `/saipen plan` |Transformer une demande ou un backlog brut en tickets|
| `/saipen goal <text>` |Exécution autonome d'une vague contre un nouvel objectif|
| `/saipen validate` |Exécuter les vérifications de conformité|
| `/saipen status` |Rapport en lecture seule : phase, tickets, blocages, staleness|
| `/saipen stop` |Checkpoint et arrêt|

<details>
<summary><b>More commands</b></summary>

|Commande|Fait|
|---|---|
| `/saipen hunt` |Forcer le balayage des défauts/améliorations maintenant|
| `/saipen markhunt` |Audit sec, non limité — enregistre les constatations, ne corrige rien|
| `/saipen ship` |Portes de sortie ; commiter, taguer et pousser lorsqu'autorisé|
| `/saipen clean` |Nettoyage du tableau et de l'état|
| `/saipen translate` |Usine de traduction isolée|
| `/saipen prepare` / `/saipen collect` |Travail de package pour transfert / intégrer un package prêt|
| `/saipen test` |Exécuter l'ensemble de tests déclaré, uniquement le rapport|
| `/saipen crew` |Circuit d'équipe en ordre fixe(chasser → reproduire → intégrer → construire → traduire → documenter → envoyer) |
| `/saipen improve` |Audit de contrôle métasur les améliorations du protocole|
| `/saipen sub ...` |Créer/adopter des sous-agents en lecture seule|

**Clés de package.** `ee`/`qq`préparer des packages de traduction/wiki complets sans
intégration ;`eee`/`qqq`accepter uniquement les packages prêts, puis intégrer, vérifier,
réviser et pousser.

**saicrew.** `sc` / `saipen crew` (`extensions/subs/crew.md`)parcourt l'intégralité
du crew intégré dans un ordre fixe — capteurs(saihunt, saitest, saipython, saiui),
producteurs(saitranslate, saiwiki)et Core en tant qu'unique écrivain de l'arbre principal —
jusqu'à ce qu'une autre passe fraîche n'ait plus rien de concret à modifier. Il ajoute exactement un
mécanisme propre : la cible d'orchestration durable(`execution_intent:
converger` with `converge_target: crew`)qui rend le circuit reprendre et
dérivable à partir des preuves.`saipen crew --dry-run --json`dérive le
circuit en lecture seule ;`bootstrap/saipen_crew.*`est un assistant manuel OPTIONNEL
multi-fenêtres, jamais ce que`saipen crew`signifie. Voir
[extensions/subs/crew.md](extensions/subs/crew.md).
</details>

## Ce que SAIPEN n'est pas

- **Un LLM ou un modèle**— c'est un protocole suivi par les agents, pas une intelligence.
- **Un IDE ou une base de mémoire hébergée**— l'état est des fichiers simples dans votre projet ;
rien n'est hébergé.
- **Un remplacement de Git**— Git détient toujours l'historique des versions ; commit votre
  `.saipen/`comme tout autre code.
- **Consensus distribué**— voir la frontière de concurrence ci-dessous.
- **Une garantie qu'un LLM prendra des décisions d'ingénierie correctes**— il
réduit la perte de contexte et le dérive comportemental ; il ne rend pas les agents stochastiques
infaillibles.

Le travail de SAIPEN est un contrat de continuation/état plus la validation et les outils —
transmettre à l'agent suivant un point de départ vérifié par machine, pas de magie.

**Frontière de concurrence.**Mutations d'état journalisées(SAIOPS)utiliser un
verrou du système d'exploitation à portée de projet et un journal de récupération([OPS § 5](saipen/OPS.md#5-locks)).
Les modifications de projet ordinaires et les auteurs déconnectés sont en dehors de ce verrou. SAIPEN
n'est pas un consensus distribué, donc les auteurs déconnectés nécessitent une
coordination([SPEC](SPEC.md#concurrency--distribution-boundaries)).

## Écosystème

|Projet|Relation avec SAIPEN|
|---|---|
| [SAIPENVIEW](https://github.com/vacterro/saipenview) |Centre de contrôle local Windows pour les projets SAIPEN — auto-découvre`.saipen/`les espaces de travail, visualise l'état en temps réel et les verdicts de conformité, gère les tickets et lance les CLI d'IA. Un complément, pas l'autorité.|
| [SAIWORK](https://github.com/vacterro/saiwork) |Fork CodeNomad en aval qui intègre SAIPEN : injecte`BOOT.md`/`STYLE.md`dans les lancements OpenCode, expose les raccourcis SAIPEN et les vues d'état de projet, et ajoute une file de prompts persistante.|
| [FastPrompter](https://github.com/vacterro/fastprompter) |Bloc-notes et gestionnaire de fragments Windows portables qui auto-détecte`.saipen/`les dossiers et ajoute un visionneur en lecture seule STATE/BOARD/LOG.|

## Documentation

|Document|Qu'est-ce que c'est|
|---|---|
| [SPEC.md](SPEC.md) |Architecture formelle, objectifs de conception, test de litmus|
| [CORE.md](saipen/CORE.md) |Continuation normative, machine à états et contrat de commande|
| [MAINTENANCE.md](saipen/MAINTENANCE.md) |Maintenance autonome et Mode Objectif|
| [CONFORMANCE.md](saipen/CONFORMANCE.md) |Exigences exécutables/comportementales et règles du validateur|
| [GUIDE.md](GUIDE.md) |Tutoriel humain|
| [RFC.md](saipen/RFC.md) |Redirection vers les documents normatifs séparés pour la compatibilité|
| [STYLE.md](saipen/STYLE.md) |Style et voix de la communication de l'agent|
| [UI.md](saipen/UI.md) |Lignes directrices du design de l'interface utilisateur Vintage Golden|
|Brochure|Brochure de présentation —[EN](BROCHURE_EN.md) / [RU](BROCHURE_RU.md) / [ET](BROCHURE_ET.md) / [DED](BROCHURE_DED.md) / [JA](BROCHURE_JA.md) |

<details>
<summary><b>All 33 translated guides</b></summary>

🇷🇺 [Русский](guides/GUIDE_RU.md) · 🇺🇸 [Anglais](guides/GUIDE_EN.md) · 🇪🇪 [Estonien](guides/GUIDE_EE.md) · 🇯🇵 [日本語](guides/GUIDE_JA.md) · 👴 [Версия Деда](guides/GUIDE_DED.md)

🇺🇦 [Українська](guides/GUIDE_UK.md) · 🇩🇪 [Allemand](guides/GUIDE_DE.md) · 🇫🇷 [Français](guides/GUIDE_FR.md) · 🇪🇸 [Espagnol](guides/GUIDE_ES.md) · 🇮🇹 [Italien](guides/GUIDE_IT.md)

🇵🇹 [Portugais](guides/GUIDE_PT.md) · 🇳🇱 [Néerlandais](guides/GUIDE_NL.md) · 🇵🇱 [Polonais](guides/GUIDE_PL.md) · 🇸🇪 [Suédois](guides/GUIDE_SV.md) · 🇩🇰 [Danois](guides/GUIDE_DA.md)

🇫🇮 [Suomi](guides/GUIDE_FI.md) · 🇳🇴 [Norsk](guides/GUIDE_NO.md) · 🇨🇳 [中文](guides/GUIDE_ZH.md) · 🇰🇷 [한국어](guides/GUIDE_KO.md) · 🇹🇭 [ไทย](guides/GUIDE_TH.md)

🇻🇳 [Tiếng Việt](guides/GUIDE_VI.md) · 🇸🇦 [العربية](guides/GUIDE_AR.md) · 🇮🇱 [עברית](guides/GUIDE_HE.md) · 🇹🇷 [Türkçe](guides/GUIDE_TR.md) · 🇮🇳 [हिन्दी](guides/GUIDE_HI.md)

🇮🇩 [Bahasa Indonesia](guides/GUIDE_ID.md) · 🇬🇷 [Ελληνικά](guides/GUIDE_EL.md) · 🇨🇿 [Čeština](guides/GUIDE_CS.md) · 🇷🇴 [Română](guides/GUIDE_RO.md) · 🇭🇺 [Magyar](guides/GUIDE_HU.md)

🇧🇬 [Български](guides/GUIDE_BG.md) · 🇸🇰 [Slovenčina](guides/GUIDE_SK.md) · 🇭🇷 [Hrvatski](guides/GUIDE_HR.md)

</details>

## Notes de configuration

**Langue de réponse.**L'agent répond en**estonien**par défaut — c'est une
configuration, pas une exigence du protocole, et rien d'autre concernant SAIPEN n'est en estonien.
Le protocole, le code, les commits et chaque document restent en anglais à chaque
valeur. Changez-le en un seul endroit : la`reply_language:`ligne en haut de
[`saipen/STYLE.md`](saipen/STYLE.md). `et`l'estonien,`en`l'anglais,`ru`le russe,
`auto`sélectionne à partir du message que vous avez envoyé.

**Adaptateurs.**Plateforme non couverte par l'injecteur(DeepSeek, Qwen, autonome
OpenAI, etc.)? Les notes spécifiques à chaque plateforme se trouvent dans`extensions/adapters/`.

## Captures d'écran

<details>
<summary><b>Click to expand</b></summary>

<img src="assets/screenshot-freebuff.png" alt="FreeBuff agent instructions" width="600"/>

<img src="assets/screenshot-nomadcode1.png" alt="saipen set in nomadcode" width="600"/>

<img src="assets/screenshot-20260801-003853.png" alt="saipen screenshot 2026-08-01" width="600"/>

</details>

<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
</p>

<!-- translation-model: qwen3:14b contract:structured-markdown-v2 -->
<!-- source-digest: README.md sha256:bb47f7158db4a7a4fd99298427c1e4bc6859433c36435640e129cc6dad2a63b7 -->
