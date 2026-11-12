# pr-squad : 8 agents Claude Code qui relisent ta PR avant la review

Tu tapes `/pr-squad:ship` sur ta branche. Huit agents passent le diff au crible et te rendent un verdict : `GO`, `FIX FIRST` ou `STOP`.

| Agent | Ce qu'il fait | Comment il le prouve |
|---|---|---|
| secret-scan | Clés, tokens, `.env`, en-têtes écrits dans les logs | gitleaks, detect-secrets ou trufflehog, puis relecture ligne par ligne |
| dep-audit | Dépendances ajoutées : CVE, paquet jamais importé, version non épinglée | pip-audit, npm audit, govulncheck, cargo audit |
| migration-guard | Migrations qui cassent sur une base qui a déjà des lignes | Répétition de la migration sur une base remplie |
| scope-check | Changements sans rapport avec l'objectif de la branche | Diff relu hunk par hunk contre l'objectif cité |
| test-gaps | Fonctions modifiées sans test | Écrit les tests manquants et lance la suite |
| bug-hunt | Bornes, None, arrondis, argent en float, fuseaux | Chaque bug vient avec l'entrée qui le casse |
| query-check | Requêtes N+1 et lectures sans limite | Compte les requêtes pour 20 puis 40 lignes |
| pr-writer | Titre, description et message de commit | Écrit depuis le diff et les verdicts, `DO NOT MERGE` si un BLOCK reste ouvert |

Les agents ne modifient jamais ton code. Seuls les tests écrits par test-gaps restent dans ton dépôt.

## Installer

```bash
claude plugin marketplace add Darius-Tokam/ai-packs
claude plugin install pr-squad@ai-packs
```

Puis, sur ta branche :

```
/pr-squad:ship ajouter une remise en pourcentage aux factures
```

L'objectif après la commande est optionnel. Sans lui, scope-check le déduit du titre de la PR ou des commits.

Tu peux aussi appeler un seul agent : « lance secret-scan sur ma branche ».

## Sans taper la commande

Dis simplement à Claude Code ce que tu veux : « fais une PR pour ajouter la remise aux factures ». Le skill `review-before-pr` lance la revue complète avant de créer la PR :

- verdict `GO` : la PR est créée avec la description écrite par pr-writer ;
- verdict `FIX FIRST` ou `STOP` : Claude te montre les problèmes et te demande s'il faut corriger d'abord ou ouvrir quand même la PR en brouillon.

Un hook sert de garde-fou : tant que le commit en cours n'a pas été relu, il bloque `gh pr create`, `glab mr create` et les outils MCP qui créent une PR, et demande la revue d'abord. Un nouveau commit après la revue demande une nouvelle revue. Le hook n'utilise que bash et git. Pour le couper : `PR_SQUAD_SKIP=1`.

## Testé sur un dépôt piège

Une app Django avec 8 défauts plantés : 8 trouvés, verdict `STOP`. Le détail, les mesures et la limite du test sont dans [test/RESULTS.md](test/RESULTS.md). Tu peux rejouer le test avec `test/build_trap.py` et `test/run_checks.py`.

## Langages

Les contrôles outillés couvrent Python, Node, Go et Rust. Les exemples visent Django, SQLAlchemy, Prisma, Rails et Laravel. Les instructions des agents sont en anglais (Claude les exécute mieux ainsi), ce guide est en français.

---

Fait par [Darius Tokam](https://tokamdarius.ca) · Arivex · Licence MIT
