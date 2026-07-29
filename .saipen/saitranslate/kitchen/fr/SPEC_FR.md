# Spécification SAIPEN

## Résumé
**Objectif de conception #1 : Un agent à froid sans historique de chat doit pouvoir exécuter `/saipen continue` et reprendre un travail productif en moins d'une minute, sans demander à l'utilisateur de répéter le contexte.**

SAIPEN garantit que tout agent IA compatible peut continuer en toute sécurité tout projet sans être re-briefé. C'est une ABI (Interface Binaire d'Application) pour les agents d'ingénierie IA — une couche de compatibilité qui résout le problème d'amnésie. Que vous utilisiez Claude aujourd'hui, Gemini demain, et GPT le jour suivant, ils opéreront tous par rapport au même état du projet sans nécessiter que vous reprécisiez le contexte.

### Philosophie Principale : État du Projet > Mémoire du Modèle
La mémoire doit vivre à côté du code, pas dans la tête d'un autre modèle. SAIPEN change le paradigme de `Projet -> Mémoire -> LLM` à `Projet -> État SAIPEN -> LLM`. La mémoire appartient au projet.

À la base, SAIPEN utilise un protocole de continuation portable soutenu par des fichiers pour les agents LLM. Les implémentations PEUVENT varier. Le contrat sur disque DOIT rester stable. Tout dans ce protocole existe pour servir le Test de Continuation.

SAIPEN est évolutif, pas créatif. Son but est d'achever le logiciel, pas de le réinventer. ADD étend les modèles de conception existants, les conventions de l'industrie et la symétrie évidente des fonctionnalités.

- **`STATE`** : Existe pour répondre à *"Que dois-je faire tout de suite ?"*
- **`BOARD`** : Existe pour répondre à *"Quelle tâche suis-je en train de prendre ?"*
- **`LOG`** : Existe pour répondre à *"Pourquoi en sommes-nous arrivés là ?"*
- **`KNOWLEDGE`** : Existe pour répondre à *"Quelle est la vérité durable de ce projet ?"*
- **`next_action`** : Le cœur de SAIPEN. Elle répond à *"Quelle commande exacte dois-je exécuter à cette seconde même pour reprendre le travail ?"*

## Le Test Décisif SAIPEN

Toute proposition de changement ou nouvelle idée pour le protocole DOIT passer les trois questions suivantes :
1. Est-ce que cela rend la transition entre les agents plus fiable ?
2. Est-ce que cela rend le comportement de différents modèles plus uniforme ?
3. Est-ce que cela réduit la probabilité de perte de contexte ?

Si la réponse est "non" à au moins deux de ces questions, l'idée est rejetée. SAIPEN privilégie la discipline, la reproductibilité et la fiabilité par rapport à la nouveauté.

## Architecture

Le protocole est strictement normatif. SAIPEN se divise conceptuellement en deux couches : **Noyau (Core)** et **Maintenance**.
- **La couche Noyau** garantit une continuation de tâche sûre et neutre vis-à-vis du fournisseur.
- **La couche Maintenance** est un modèle d'évolution logicielle autonome construit au-dessus du Noyau.

En dessous des deux couches, SAIPEN sépare trois préoccupations qui ne s'entremêlent jamais :
**exactitude et continuation** (Noyau -- `STATE`/`BOARD`/`LOG`/`KNOWLEDGE`, négociation
de capacités, points de contrôle), **évolution sans surveillance** (Maintenance -- `HUNT`/`ADD`/`CLEAN`,
pleinement fonctionnel sous le défaut simple `saipen`/`saipen continue`), et **débit**
(Mode Goal, Sous-agents -- tous deux opt-in explicites, §1.3/§2.4). Désactiver le Mode Goal : le
protocole reste inchangé, un ticket à la fois. Désactiver les Sous-agents : `HUNT` exécute les mêmes
six catégories séquentiellement, même résultat. Utiliser le Noyau seul, sans aucune couche de
Maintenance : cela tient toujours -- un agent à froid reprend toujours correctement. Chaque couche s'appuie sur
celle du dessous sans que l'inverse ne soit jamais vrai ; rien en amont ne dépend
de l'existence d'une fonctionnalité en aval.

```text
saipen/
  RFC.md                    spécification normative (divisée en Noyau et Maintenance)
  CONFORMANCE.md             vecteurs d'auto-contrôle + tableau de couverture de scénarios
  SKILL.md                  point d'entrée mince pour les plateformes lisant les skills
  STYLE.md                  voix : chat, LOG.md, artefacts
  UI.md                     spécification UI Vintage Golden (obligatoire pour le travail UI)
  BOOT.md                   ~noyau de démarrage à froid : le chemin rapide dont un `continue`
                             nu a besoin, avant que l'une des ci-dessus soit chargée
  phases/                   logique stricte de machine à état -- 16 docs, un par
                             valeur d'énumération RFC § 1.6 (vérifié machine dans les
                             deux sens par tools/validate.py)
    [Phases du Noyau]
    init.md / plan.md / scout.md / build.md / verify.md / review.md / ship.md / done.md / blocked.md
    [Phases de Maintenance]
    hunt.md / markhunt.md / add.md / clean.md / translate.md

    [Infrastructure]
    prepare.md              prépare le travail pour la passation au prochain agent
    validate.md             test de conformité

extensions/                 <- LA COUCHE ADAPTATIVE
  adapters/                 ponts d'instructions par modèle, pour les plateformes que
                             l'injecteur ne détecte pas automatiquement (README.md pointe ici)
  schemas/                  state.schema.json est lu par machine par tools/validate.py
                             (source unique de vérité pour la forme de STATE) ; les schémas
                             board/log restent uniquement pour référence (voir schemas/README.md)
  templates/                modèles .saipen/ frais
  security/                 EXEMPLE de hook à copier dans un projet (RFC § 1.9, s'attache à VERIFY)
  performance/              EXEMPLE de hook à copier dans un projet (RFC § 1.9, s'attache à REVIEW)
  subs/                     EXEMPLE de sous-agents de recherche en lecture seule (RFC § 1.9) -- propre
                             STATE/BOARD/LOG par sous-agent, résultats uniquement via OUTBOX,
                             jamais un second chemin d'écriture dans le projet

bootstrap/                  <- INSTALLER/EXPORTER/DÉSINSTALLER, une machine à la fois
  inject.ps1 / .sh          installe le bloc SAIPEN + copies de skills (Démarrage Rapide du README)
  uninstall.ps1 / .sh       inverse inject -- supprime les blocs + copies de skills
  export.ps1 / .sh          archive le .saipen/ d'un projet pour sauvegarde
  saipen_crew.bat / .sh     ouvre la disposition d'équipe à 3 fenêtres (bonus, extensions/subs/crew.md)

tools/                      <- VALIDATEUR CANONIQUE & UTILITAIRES DE DÉPÔT
  validate.py               validateur de conformité canonique (Python stdlib, zéro
                             installations ; valide STATE contre state.schema.json
                             directement, plus vérifications de graphe que la paire shell ne peut pas faire)
  install_hook.py           installe un hook pre-commit exécutant validate.py
  uninstall_hook.py         supprime exactement ce hook (restaure tout hook antérieur)

tests/                      <- COUCHE DE CONFORMITÉ
  validate.ps1 / .sh        plancher portable gelé pour les hôtes sans Python --
                             les nouvelles vérifications atterrissent uniquement dans tools/validate.py
  scenarios/                états simulés (récupération de plantage, conflits de réclamation, etc.)
```

## Négociation de Capacités Bidirectionnelle
Les agents ne déclarent pas simplement ce qu'ils peuvent faire ; le protocole exige ce qui est requis.
Le projet définit `requires: [filesystem, git, shell, python]` dans son état. L'agent recoupe ses capacités d'hôte et se verrouille dans un `mode` (par ex., `full`, `read-only`).

## Journalisation d'Événements Basée sur Graphe
Les journaux dans SAIPEN ne sont pas des chaînes linéaires. Ils forment un graphe acyclique de décisions utilisant des IDs d'Événement (`E-001`). Cela permet des bifurcations complexes, des fusions d'agents, et des pistes d'audit précises.

## Registres de Décisions d'Architecture (ADR)
Les journaux d'événements transitoires n'hébergent pas de connaissances permanentes. SAIPEN exige que les décisions architecturales structurelles soient persistées en tant qu'ADRs (par ex., `KNOWLEDGE/ADR-001-use-sqlite.md`).

## Concurrence & Frontières de Distribution
SAIPEN garantit l'intégrité de l'état via des réclamations basées sur des fichiers (`owner`, `claim_time`) et des graphes séquentiels (`LOG.md`). Cependant, **SAIPEN est un protocole d'état, pas un algorithme de consensus distribué.**
- **Système de Fichiers Local/Partagé** : La résolution des conflits repose sur les écritures atomiques du système de fichiers ("le premier commit gagne").
- **Environnements en Réseau/Distribués** : Si les agents opèrent sur des machines déconnectées sans synchronisation de fichiers en temps réel, des conditions de course sur les réclamations de `BOARD.md` se produiront. Dans des configurations hautement distribuées, le contrat du protocole sur disque de SAIPEN DOIT rester stable -- l'état du projet lui-même mute constamment, à travers les propres règles de SAIPEN (point de contrôle § 1.5), jamais la forme du protocole que ces règles suivent.


<p align="center">
  <img src="assets/SAIPEN_design2_alpha.png" alt="Timbre SAIPEN" width="120"/>
</p>
