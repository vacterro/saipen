# Politique de Sécurité

## Portée

SAIPEN est une spécification plus un petit ensemble de scripts d'installation/exportation
locaux (`bootstrap/inject.ps1`/`.sh`, `uninstall.ps1`/`.sh`,
`export.ps1`/`.sh`). Il n'exécute pas de serveur, ne collecte pas
de télémétrie, et ne transmet aucune donnée nulle part. Tout ce que
font les scripts, ce sont des écritures locales dans le système de fichiers vers des fichiers que vous contrôlez déjà
(votre propre `~/.claude`, `~/.gemini`, `.saipen/` du projet, etc.).

Deux niveaux de soin différents s'appliquent ici, et il vaut la peine d'être précis
plutôt que de prétendre à une sécurité générale :

- **Vos propres fichiers de configuration** (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
  `.aider.conf.yml`) ne sont jamais modifiés qu'en ajoutant ou supprimant un
  bloc délimité `SAIPEN:BEGIN`/`END`, et l'original est copié vers
  `<fichier>.bak` avant la première modification. La désinstallation écrit en
  plus `<fichier>.uninstalled.bak` avant le retrait.
- **Les répertoires de compétences (skills)** que l'injecteur crée (`~/.claude/skills/saipen`
  et autres) sont des copies appartenant à SAIPEN et ne sont **pas** sauvegardés :
  l'installation les écrase entièrement et la désinstallation les supprime
  récursivement. C'est intentionnel -- ils ne contiennent que des copies des
  fichiers de ce dépôt -- mais si vous modifiez manuellement une copie de skill
  locale, ces modifications sont perdues lors de la prochaine exécution
  d'`inject`/`uninstall`. Gardez les personnalisations dans votre propre bloc de
  configuration ou un fork, pas dans le dossier de skill copié.

Les deux choses qui méritent vraiment un rapport de sécurité :
1. Un script d'amorçage faisant quelque chose à votre système de fichiers ou historique git
   au-delà de ce que ses propres commentaires/README décrivent.
2. La propre règle d'hygiène des secrets du protocole (RFC.md § 1.1 -- ne jamais écrire
   de clés d'API, jetons, mots de passe dans `STATE.md`/`BOARD.md`/`LOG.md`/
   `KNOWLEDGE/`/`kitchen/`/`extensions/`/`saitranslate/kitchen/`/
   `recovery/`/`logs/`) ayant une véritable faille qui amènerait un
   agent suivant SAIPEN à divulguer un secret dans un fichier commité. Les deux
   derniers sont les plus subtils : Recovery copie une `STATE.md` corrompue
   textuellement dans `.saipen/recovery/`, et le scellement LOG déplace des lignes
   textuellement dans `.saipen/logs/`, donc tout ce qui a atteint l'original est
   archivé par une machinerie dont le travail entier est de ne pas altérer le contenu.

## Versions Supportées

Seule la dernière release taguée sur `main` est supportée. Ceci est une
spécification de protocole, pas un service à longue durée de vie -- il n'y a pas de branche
LTS.

## Signaler une Vulnérabilité

Ouvrez une issue GitHub. Si le rapport implique un vrai problème
actuellement exploitable (pas une hypothèse), marquez-le comme un avis privé/de sécurité via
l'onglet **Sécurité** ("Report a vulnerability") de ce dépôt au lieu
d'une issue publique, afin qu'il ne soit visible publiquement avant le déploiement d'un correctif.

Incluez : quel script ou règle RFC, le scénario concret, et ce
qui se passe réellement vs ce qui devrait se passer. Même norme de preuve que pour tout
autre rapport de bug (voir `CONTRIBUTING.md`).
