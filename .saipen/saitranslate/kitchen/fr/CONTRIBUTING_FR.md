# Contribuer à SAIPEN

SAIPEN est d'abord une spécification, ensuite une implémentation. La plupart des contributions
sont des changements à `saipen/RFC.md`, un fichier `phases/*.md`, ou l'outillage de conformité
dans `tests/` -- pas du code d'application.

## Avant de proposer un changement

Exécutez le [Test Décisif SAIPEN](SPEC.md#le-test-décisif-saipen) sur votre
idée :
1. Est-ce que cela rend la transition entre les agents plus fiable ?
2. Est-ce que cela rend le comportement de différents modèles plus uniforme ?
3. Est-ce que cela réduit la probabilité de perte de contexte ?

Si la réponse est "non" à au moins deux de ces questions, c'est hors du champ d'application de ce
protocole, aussi utile que cela puisse être ailleurs.

## Signaler une lacune

Ouvrez une issue décrivant :
- dans quel fichier/section se trouve la lacune (RFC.md, un doc de phase, un schéma, un test)
- la preuve concrète (une citation, une commande et sa sortie, un scénario où
  le comportement actuel échoue)
- ce que vous attendriez à la place

Les rapports vagues ("ça semble bizarre") sont plus difficiles à traiter qu'un `grep`/reproduction
spécifique. Voir le modèle d'issue de rapport de bug pour la forme que cela
devrait prendre.

## Faire un changement

1. Lisez `saipen/RFC.md` et le(s) fichier(s) `phases/*.md` pertinent(s) entièrement avant
   de modifier -- la plupart des lacunes apparentes s'avèrent déjà abordées ailleurs,
   ou délibérément délimitées d'une certaine manière pour une raison documentée.
2. Vérifiez `CHANGELOG.md` et `.saipen/KNOWLEDGE/decisions.md` pour l'état de l'art.
   Ne rouvrez pas silencieusement une décision qui a déjà été prise et rejetée --
   si vous avez de nouvelles preuves qu'un rejet passé était faux, dites-le explicitement
   dans la description de la PR.
3. Chaque changement normatif (un DOIT/NE DOIT PAS/DEVRAIT) nécessite une entrée
   dans `CHANGELOG.md` et, lorsque c'est pratique, une couverture dans `tests/validate.sh` +
   `tests/validate.ps1` (les deux plateformes) ou une fixture sous
   `tests/scenarios/`.
4. Exécutez le validateur canonique avant d'ouvrir une PR :
   ```bash
   python tools/validate.py
   ```
   C'est celui qui compte -- il vérifie `STATE.md` par rapport à
   `extensions/schemas/state.schema.json`, parcourt le graphe d'événements `LOG.md`
   à travers les segments scellés, et vérifie le manifeste d'exécution et le câblage
   de l'injecteur. `tests/validate.sh` / `validate.ps1` sont le **plancher portable
   gelé** pour les hôtes sans Python (ils le disent en haut de chaque fichier) :
   moins de vérifications, conservés uniquement pour qu'un hôte sans Python ne soit
   pas laissé sans rien. Exécutez-les aussi si votre modification touche à l'un d'eux,
   mais jamais *à la place* -- réussir le plancher seul prouve beaucoup moins qu'il n'y paraît.
   CI exécute le validateur canonique sur chaque push et PR indépendamment
   (`.github/workflows/validate.yml`).
5. Augmentez `VERSION` selon le schéma dans `phases/ship.md` (patch pour des clarifications
   uniquement dans la doc, mineur pour un nouveau comportement normatif, majeur pour des changements
   de contrat cassants) et gardez le badge de version du `README.md` synchronisé --
   `tests/validate.sh`/`.ps1` vérifient cela automatiquement lorsqu'ils sont exécutés depuis un
   clone de ce dépôt.

## Style

- Docs de protocole et de phase : concis, mots-clés RFC-2119 là où ils importent, pas
  de remplissage. Voir `saipen/STYLE.md`.
- Tout dans ce fichier, les messages de commit, les commentaires de code, et le
  CHANGELOG : simple et professionnel. Les voix de chat/LOG du projet lui-même
  (`saipen/STYLE.md`) ne s'appliquent pas aux artefacts.

## Ce qui est hors de portée

- Transformer SAIPEN en un système de consensus distribué. Voir
  la section Concurrence & Frontières de Distribution de `SPEC.md`.
- Grammaire de marqueurs de LOG analysable par machine au-delà du squelette existant.
  `LOG.md` reste de la prose autour d'une forme fixe.
- Une commande `saipen doctor` ou similaire redondante avec `saipen validate` +
  `saipen status`.

Chacun de ces éléments a déjà été proposé et évalué ; les rouvrir nécessite
de nouvelles preuves, pas seulement de redemander.
