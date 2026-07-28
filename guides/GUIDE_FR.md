<p align="center">
  <img src="assets/SAIPEN_design1.png" alt="SAIPEN Guide Title" width="800"/>
</p>

# Guide SAIPEN (Français)

Écoute ici, recrue. Le problème est simple: vos agents IA ont la mémoire d'un poisson rouge.

**SAIPEN** est un cahier résistant dans le dossier `.saipen/` de votre projet.

## Démarrage Rapide

1. **Installer une fois par machine:**
```bash
git clone https://github.com/vacterro/saipen
cd saipen
powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
bash bootstrap/inject.sh                                            # macOS / Linux
```

2. **Démarrer le projet:**
> `saipen set`

3. **Travailler:**
> `saipen`

## Commandes

| Commande | Action |
|---|---|
| `saipen set` | Initialiser le dossier mémoire `.saipen/` |
| `saipen continue` | Reprendre le travail depuis les notes |
| `saipen stop` | Sauvegarder la progression et arrêter |
| `saipen status` | Lire le tableau et l'état |
| `saipen goal <text>` | Pivoter vers un nouvel objectif |
| `saipen clean` | Nettoyage approfondi du dépôt |
| `saipen translate` | Construction de traduction isolée en 32 langues |
| `saipen markhunt` | Audit profond et illimité -- enregistre les découvertes sans rien corriger |
| `saipen prepare` | Empaquette le travail pour la transmission au prochain agent |
| `saipen ship` | Déclencher le flux de publication |

## Bon à savoir
- Des changements non commités en revenant sur le projet ? Normal -- SAIPEN committe seulement au `ship`, pas à chaque étape. L'agent vérifie d'abord à qui appartiennent ces changements avant d'y toucher.
- Tu veux qu'il retienne une vraie décision d'architecture ? Mets-la dans `.saipen/KNOWLEDGE/`, soit en un fichier `decisions.md`, soit en fichiers numérotés `ADR-001.md`.
- Pas de git ni de shell sur cette machine ? L'agent le dit clairement (`mode`, `WAIT: <category> -- <question>`) plutôt que de deviner.
- Tu veux un filet de sécurité ? `python <clone-saipen>/tools/install_hook.py` installe une vérification avant chaque commit.

---

**Full command list / complete command reference:** [RFC § 1.10](../saipen/RFC.md#110-command-surface) — the authoritative list of every `saipen` command.
