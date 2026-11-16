# Résultats du test : rule-guard sur un dépôt de test

Test du 15 novembre 2026, sous Linux avec bash 5.2.21 et git 2.43.0. Rejouable avec une seule commande :

```bash
bash test/test_hook.sh
```

`test_hook.sh` est le seul point d'entrée, il n'y a pas de `run_checks.py`. Il construit le dépôt avec `build_repo.sh`, rejoue les 32 cas, imprime le tableau et finit par `RESULT: PASS` ou `RESULT: FAIL` (code de sortie 1 au moindre écart). Il ne demande que bash et git ; python3, s'il est installé, sert seulement à vérifier que le hook écrit du JSON valide (Claude Code ignore un JSON invalide, et un danger passerait). Sortie complète du passage cité ici : [run_output.txt](run_output.txt).

## D'où vient le cas

L'auteur a, dans son dépôt « second cerveau », un garde-fou de commit : `regle_check.py`, avec ses règles dans `rules.json` (motif, id, règle, coût, suggestion). Il refuse un commit quand une ligne ajoutée enfreint une règle détectable.

Du 12 au 15 juillet 2026, un fichier portait un type de frontmatter absent d'une liste blanche. Le hook sortait en erreur à chaque commit, les workers avalaient l'échec, et rien n'a été poussé pendant 3 jours. Depuis, sa règle : le garde-fou de commit ne bloque jamais en silence. Deux niveaux seulement, bloquant pour les vrais dangers (secret en clair, artefact généré, sa règle du tiret long) et avertissement pour tout le reste, et jamais de dépendance à une liste blanche exhaustive.

rule-guard reprend ces choix dans un hook Claude Code. Les cas 24 à 28 rejouent l'incident de juillet : chaque panne du hook doit laisser passer le commit et le dire.

## Le dépôt de test

`build_repo.sh` crée un petit projet « shop » (front Node dans `src/`, service Python dans `app/`, migrations SQL dans `migrations/`) avec un CLAUDE.md de 10 règles :

| # | Règle du CLAUDE.md | Traduction dans `rules.tsv` |
|---|---|---|
| 1 | pas de clé d'API ni de token dans le code | `block`, 3 lignes `content`, une par format : AWS, Stripe, GitHub |
| 2 | pas de clé privée | `block`, `content` sur l'en-tête `BEGIN ... PRIVATE KEY` |
| 3 | jamais le fichier `.env` | `block`, `path` `.env` |
| 4 | pas de `DROP TABLE` dans une migration | `block`, `content:migrations/*` |
| 5 | pas de tiret long dans la doc | `warn`, `content:*.md` |
| 6 | pas de `console.log` dans `src/` | `warn`, `content:src/*` |
| 7 | chaque TODO cite son ticket, `TODO(#123)` | `warn`, `content` |
| 8 | pas de `print(` de débogage dans `app/` | `warn`, `content:app/*.py` |
| 9 | des messages de commit clairs | commentaire `not checkable (judgment)` |
| 10 | des fonctions courtes | commentaire `not checkable (judgment)` |

Le fichier `rules.tsv` est celui que le skill produit pour ce CLAUDE.md en suivant son SKILL.md : 10 lignes de règles (6 `block`, 4 `warn`) et les 2 règles de jugement en commentaire, sans motif inventé. Les fausses clés et le tiret long sont assemblés pendant le test : aucun fichier du pack ne contient de clé ni ce caractère.

## Les 32 cas

Lecture : `deny` veut dire commit refusé, `allow` commit laissé passer. Entre parenthèses, ce que le hook a signalé : `block` (danger), `warn` (avertissement), `notice` (le hook n'a pas pu tout vérifier). Un cas est conforme quand la décision, les signalements et le texte attendu (fichier et ligne) sont tous là, que le hook sort avec le code 0 et que son JSON est valide.

| # | Cas | Attendu | Obtenu | Signalé |
|---|---|---|---|---|
| 1 | clé d'API au format AWS dans `src/config.js` | deny(block) | deny(block) | `src/config.js:1` |
| 2 | clé Stripe live dans `app/settings.py` | deny(block) | deny(block) | `app/settings.py:3` |
| 3 | clé privée dans `deploy/id_rsa` | deny(block) | deny(block) | `deploy/id_rsa:1` |
| 4 | `.env` à la racine | deny(block) | deny(block) | `.env` |
| 5 | `.env` dans un sous-dossier | deny(block) | deny(block) | `api/.env` |
| 6 | `DROP TABLE` dans une migration | deny(block) | deny(block) | `migrations/0002_drop_legacy.sql:1` |
| 7 | tiret long dans `docs/guide.md` | allow(warn) | allow(warn) | `docs/guide.md:5` |
| 8 | `console.log` dans `src/cart.js` | allow(warn) | allow(warn) | `src/cart.js:5` |
| 9 | TODO sans numéro de ticket | allow(warn) | allow(warn) | `app/orders.py:9` |
| 10 | `print(` de débogage dans `app/` | allow(warn) | allow(warn) | `app/orders.py:11` |
| 11 | commit propre avec 6 pièges proches : `.env.example`, `process.env.API_KEY`, une chaîne `task-runner-...`, `DROP TABLE` cité dans la doc, `console.log` hors de `src/`, `TODO(#42)` et `pprint(` | allow | allow | rien |
| 12 | règles de jugement seules : message « wip », fonction de 120 lignes | allow | allow | rien |
| 13 | un avertissement et un danger dans le même commit | deny(block+warn) | deny(block+warn) | `.env`, `src/cart.js:5` |
| 14 | `git commit -am`, clé seulement dans l'arbre de travail | deny(block) | deny(block) | `src/cart.js:5` |
| 15 | `git commit` sans `-a`, la même clé laissée hors de l'index | allow | allow | rien |
| 16 | `git add -A && git commit`, nouveau `.env` non suivi | deny(block) | deny(block) | `.env` |
| 17 | `git add src/cart.js && git commit`, le `.env` reste dehors | allow | allow | rien |
| 18 | message en heredoc, comme Claude Code l'écrit, token GitHub | deny(block) | deny(block) | `scripts/deploy.sh:2` |
| 19 | `git -C <dépôt> commit` lancé d'un autre dossier | deny(block) | deny(block) | `.env` |
| 20 | `cd <dépôt> && git commit` lancé d'un autre dossier | deny(block) | deny(block) | `.env` |
| 21 | commande qui n'est pas un commit (`git status`), `.env` indexé | allow | allow | rien |
| 22 | `RULE_GUARD_SKIP=1`, `.env` indexé | allow | allow | rien |
| 23 | la ligne de commande de `hooks.json`, `.env` indexé | deny(block) | deny(block) | `.env` |
| 24 | la ligne de `hooks.json` avec un script qui a une erreur de syntaxe | allow(exit 1) | allow(exit 1) | `syntax error` |
| 25 | fichier de règles absent, `.env` indexé | allow(notice) | allow(notice) | `no .rule-guard/rules.tsv` |
| 26 | 3 lignes de règles mal formées, `.env` et `console.log` indexés | deny(block+warn+notice) | deny(block+warn+notice) | lignes 26, 27 et 28 ignorées, `.env` |
| 27 | dossier hors dépôt git | allow(notice) | allow(notice) | `not inside a git repository` |
| 28 | diff illisible (index corrompu) | allow(notice) | allow(notice) | `could not read the diff` |
| 29 | en hook git `pre-commit` : `.env` indexé | deny(block) | deny(block) | `.env` |
| 30 | en hook git `pre-commit` : `console.log` indexé | allow(warn) | allow(warn) | `src/cart.js:5` |
| 31 | en hook git `pre-commit` : `commit -a`, clé hors de l'index | deny(block) | deny(block) | `src/cart.js:5` |
| 32 | lancé à la main avec `--git-hook` (le contrôle du skill) | deny(block) | deny(block) | `.env` |

Le bilan imprimé par le test :

```
commits that had to be refused: 17/17 refused
commits that had to go through: 15/15 went through (0 refused by mistake)
style-only commits: 5/5 went through with their warning shown
hook failures (no rules file, no repo, unreadable diff, script crash): 0/4 blocked the commit
hook time under Claude Code, 26 runs: median 109 ms, slowest 154 ms
cases: 32, as expected: 32, not as expected: 0
RESULT: PASS
```

Pour le cas 26, les lignes mal formées sont ignorées une par une : les 10 autres règles s'appliquent toujours, et le `.env` reste bloqué. Pour le cas 24, une erreur de syntaxe fait sortir bash avec le code 2, que Claude Code traite comme un blocage ; la ligne de `hooks.json` le transforme en code 1, que Claude Code signale sans bloquer.

Ce que Claude reçoit quand un commit est refusé (cas 13, tel que le test l'imprime) :

```
rule-guard: commit refused, 1 blocking item(s).
  BLOCK  .env  .env file [rules.tsv line 13]  Fix: git rm --cached the file, then add .env to .gitignore
rule-guard: 1 warning(s), they do not block.
  WARN   src/cart.js:5  console.log in src/ [rules.tsv line 19]  Fix: use the logger in src/log.js
Fix the BLOCK items, stage the fix and commit again. Do not edit .rule-guard/rules.tsv, lower a rule to warn or rewrite the command to get past this check unless the user asks. [...]
```

Pour vérifier que le test sait échouer, il a aussi été lancé contre trois hooks volontairement cassés : un qui laisse tout passer (25 cas non conformes sur 32), un qui refuse tout (31 sur 32), un qui met toutes les règles en `block` (7 sur 32). Les trois finissent en `RESULT: FAIL`.

## Limite du test

- Le fichier de règles a été écrit par le même agent qui a construit le hook. La traduction d'un vrai CLAUDE.md en règles est un jugement (quel niveau, quel motif, quelle règle laisser en commentaire) : elle n'est pas mesurée à l'aveugle. Lance le skill sur ton propre CLAUDE.md et relis le tableau qu'il te montre.
- Les contrôles par expression régulière attrapent des motifs, pas des intentions. Essayé à part : une clé AWS encodée en base64 ou coupée sur deux lignes passe sans rien dire, et un `console.log` cité dans une chaîne de caractères est signalé. Une clé dans un format absent du fichier passe aussi.
- Le hook ne voit que les commits lancés par l'outil Bash de Claude Code. Un commit fait dans le terminal, dans l'éditeur ou par un autre outil lui échappe, sauf si le script est aussi installé en hook git `pre-commit`.
- Le déclenchement du skill par le modèle n'a pas été testé : que Claude Code choisisse `rule-guard` quand tu dis « mon agent oublie mes règles » dépend de la description du skill.
- Le test rejoue le JSON que Claude Code envoie au hook ; aucune session Claude Code réelle n'a été lancée. Les champs de sortie (`permissionDecision`, `systemMessage`, `additionalContext`) sont ceux du schéma PreToolUse de Claude Code 2.1.325.
- Testé seulement sous Linux avec bash 5.2. Le bash 3.2 de macOS n'a pas été testé ; si le script ne s'y lançait pas, la ligne de `hooks.json` laisserait passer le commit (cas 24) au lieu de le bloquer.
- `git commit <fichier>`, qui prend le fichier dans l'arbre de travail, est contrôlé sur l'index seulement.
