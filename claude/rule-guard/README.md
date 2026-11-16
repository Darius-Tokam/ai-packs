# rule-guard : la règle de ton CLAUDE.md vérifiée à chaque commit

Tu as écrit « ne jamais commiter le `.env` » dans ton CLAUDE.md. L'agent l'a lu, puis l'a oublié trente messages plus tard. Sans contrôle, tu répètes les mêmes consignes, et l'agent finit toujours par en oublier une.

rule-guard transforme les règles de ton CLAUDE.md en contrôles. Un hook les applique avant chaque `git commit` lancé par Claude Code : les vrais dangers bloquent le commit, les règles de style préviennent sans jamais bloquer ton travail.

Un skill et un hook (bash et git), parce qu'il n'y a qu'une action risquée à protéger : le commit.

## Deux niveaux, pas plus

| Niveau | Pour quoi | Ce qui se passe |
|---|---|---|
| `block` | les vrais dangers : clé d'API ou token en clair, clé privée, fichier `.env`, artefact généré, `DROP TABLE` dans une migration | le commit est refusé. Claude reçoit la règle, le fichier, la ligne et le correctif, avec la consigne de corriger avant de recommiter |
| `warn` | tout le reste : `console.log`, TODO sans ticket, `print(` de débogage, tiret long dans la doc | le commit passe. L'avertissement s'affiche pour toi et pour Claude |

Les règles qui demandent du jugement (« écris des messages de commit clairs », « garde des fonctions courtes ») restent dans ton CLAUDE.md. Le skill les marque « non vérifiable » au lieu d'inventer un motif qui bloquerait du bon code.

Le hook ne bloque jamais à cause de lui-même. Fichier de règles absent, ligne mal formée, dossier hors dépôt git, diff illisible, script qui plante : le commit passe, et un avertissement le dit. Cette règle vient d'un incident de l'auteur : en juillet 2026, son garde-fou de commit a refusé tous les commits pendant 3 jours à cause d'une valeur absente d'une liste blanche, l'échec était avalé en silence, et rien n'a été poussé.

## Ce que le hook vérifie

Avant un `git commit` passé par l'outil Bash de Claude Code, le hook lit `.rule-guard/rules.tsv` à la racine du dépôt et contrôle ce que le commit ajoute :

- les lignes ajoutées et les chemins des fichiers indexés ;
- avec `git commit -a` : les fichiers suivis modifiés, comparés à HEAD ;
- avec `git add ... && git commit` dans la même commande : aussi les fichiers que ce `git add` va ajouter, nouveaux fichiers compris.

Il ne relit pas le code déjà commité, ni le dossier `.rule-guard/`. Il n'affiche jamais la ligne fautive, seulement le fichier et son numéro de ligne, pour ne pas recopier un secret dans la conversation.

## Le fichier de règles

Une règle par ligne, cinq champs séparés par des tabulations : niveau, type, motif, message, correctif. Les lignes qui commencent par `#` sont des commentaires.

```
# CLAUDE.md:8 never commit the .env file
block	path	.env	.env file	git rm --cached the file, then add .env to .gitignore
# CLAUDE.md:13 no console.log in src/
warn	content:src/*	console\.log\(	console.log in src/	use the logger in src/log.js
# not checkable (judgment): "Keep functions small." (CLAUDE.md:19)
```

- `path` : un glob sur le chemin des fichiers du commit. Sans `/`, il vaut aussi pour le nom seul : `.env` attrape `api/.env`, mais pas `.env.example`.
- `content` : une expression régulière étendue (celle de `grep -E`), testée sur chaque ligne ajoutée. `content:<glob>` la limite à certains fichiers, par exemple `content:migrations/*`.
- Un caractère non ASCII s'écrit `\uXXXX`. Le tiret long, par exemple, s'écrit `\u2014` : le fichier reste en ASCII.

Pour passer une règle de `warn` à `block`, ou l'inverse, change le premier champ de sa ligne. Commite le fichier : toute l'équipe aura les mêmes contrôles.

## Installer

```bash
claude plugin marketplace add Darius-Tokam/ai-packs
claude plugin install rule-guard@ai-packs
```

## Sans taper de commande

Dis à Claude Code : « transforme mes règles CLAUDE.md en contrôles », ou simplement « mon agent oublie mes règles ». Le skill `rule-guard` lit ton CLAUDE.md, écrit `.rule-guard/rules.tsv`, teste chaque motif sur un exemple, puis te montre le tableau des règles avec leur niveau :

| # | Règle (CLAUDE.md) | Niveau | Contrôle |
|---|---|---|---|
| 3 | Never commit the `.env` file | block | chemin `.env` |
| 6 | No `console.log` in `src/` | warn | `console\.log\(` dans `src/*` |
| 10 | Keep functions small | non vérifiable | demande du jugement, reste dans le CLAUDE.md |

Il ne commite pas le fichier de règles sans ton accord.

## Le couper

Lance Claude Code avec la variable `RULE_GUARD_SKIP=1` (par exemple `RULE_GUARD_SKIP=1 claude`) : le hook laisse alors tout passer. Pour un seul faux positif, passe plutôt la règle en `warn`.

## Sans Claude Code, en hook git

Le même script sert de hook `pre-commit` pour les commits que tu fais toi-même dans le terminal :

```bash
git clone https://github.com/Darius-Tokam/ai-packs
cp ai-packs/claude/rule-guard/hooks/rule-guard.sh ton-projet/.git/hooks/pre-commit
chmod +x ton-projet/.git/hooks/pre-commit
```

Un `block` refuse le commit, un `warn` s'affiche et laisse passer, `git commit -a` compris. Pour passer une fois : `RULE_GUARD_SKIP=1 git commit ...`. Testé en copiant le script dans `.git/hooks/pre-commit` du dépôt de test : 3 cas sur 3 conformes.

## Testé sur 32 cas

Un dépôt de test dont le CLAUDE.md a 10 règles : 4 dangers (clé d'API, clé privée, `.env`, `DROP TABLE` dans une migration), 4 règles de style vérifiables (tiret long dans la doc, `console.log` dans `src/`, TODO sans numéro de ticket, `print(` dans `app/`) et 2 règles de jugement. Sur 32 cas, 32 conformes :

- 17 commits sur 17 qui devaient être refusés l'ont été, y compris `git commit -am`, `git add -A && git commit` et un message de commit en heredoc comme Claude Code les écrit ;
- 15 commits sur 15 qui devaient passer sont passés, dont un commit propre avec 6 pièges proches (`.env.example`, `process.env.API_KEY`, `DROP TABLE` cité dans la doc...) : 0 refus à tort ;
- 5 commits de style sur 5 sont passés avec leur avertissement affiché ;
- 4 pannes du hook lui-même (pas de fichier de règles, pas de dépôt git, index corrompu, script qui ne se lance pas) : 0 commit bloqué ;
- 109 ms par commit en médiane, 154 ms au plus.

Le détail et la limite du test sont dans [test/RESULTS.md](test/RESULTS.md). Pour rejouer : `bash test/test_hook.sh`.

## Langues

Le skill te répond dans ta langue. Ses instructions et les messages du hook sont en anglais (Claude les suit mieux ainsi), ce guide est en français.

---

Fait par [Darius Tokam](https://tokamdarius.ca) · Arivex · Licence MIT
