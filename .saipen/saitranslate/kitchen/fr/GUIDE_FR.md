<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Guide SAIPEN (Français)

[TRANSLATED FR]:
It is 2026 and the AI woke up. The assistants stopped being chat toys — they open your project, write the code, run the tests, and finish a job while you go make coffee. There is one thing they cannot do. They cannot remember. Close the window and everything they learned about your work is gone: what you were building, what you already tried, which idea died on Tuesday. Every morning you brief a brilliant stranger from scratch.

This is the fix for that one thing.

**SAIPEN** est un cahier résistant dans le dossier `.saipen/` de votre projet.

## Démarrage Rapide

## Commandes

## Bon à savoir
- Des changements non commités en revenant sur le projet ? Normal -- SAIPEN committe seulement au `ship`, pas à chaque étape. L'agent vérifie d'abord à qui appartiennent ces changements avant d'y toucher.
- Tu veux qu'il retienne une vraie décision d'architecture ? Mets-la dans `.saipen/KNOWLEDGE/`, soit en un fichier `decisions.md`, soit en fichiers numérotés `ADR-001.md`.
- Pas de git ni de shell sur cette machine ? L'agent le dit clairement (`mode`, `WAIT: <category> -- <question>`) plutôt que de deviner (la catégorie est l'une des sept : `manual-verify, destructive-op, first-publish, user brake, blocked, safety valve, init` ; elle indique le type de réponse qui débloque la situation)
- Tu veux un filet de sécurité ? `python <clone-saipen>/tools/install_hook.py` installe une vérification avant chaque commit.