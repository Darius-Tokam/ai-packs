# deploy-doctor : un skill Claude Code qui dit pourquoi ton déploiement a planté

Ton build échoue, ton app répond 502, ou tu reçois un mail « Deployment crashed ». Tu dis à Claude Code « mon déploiement a planté ». Le skill lit les logs, nomme la cause, montre la ligne de code qui la provoque, et te donne le correctif et la façon de vérifier. Il ne touche à rien sans ton accord.

Un seul skill et un script Python, parce qu'il n'y a qu'une étape : lire le log et le confronter aux pannes connues.

| Panne reconnue | Ce que tu vois dans le log | Ce que le skill propose |
|---|---|---|
| npm en PID 1 | `npm error signal SIGTERM` à chaque redéploiement | lancer `node` directement et gérer SIGTERM |
| python introuvable | `python: command not found` dans un cron | appeler `python3` |
| variable d'environnement absente | `KeyError: 'ALLOWED_HOSTS'` au démarrage | poser la variable sur chaque service |
| réglages de dev en prod | la page « DEBUG = True » de Django | fixer `DJANGO_SETTINGS_MODULE` sur l'hébergeur |
| serveur sur localhost | `running on http://127.0.0.1:8000`, puis 502 | écouter sur `0.0.0.0` et `$PORT` |
| mémoire épuisée | `JavaScript heap out of memory`, code 137 | trouver le pic, baisser la charge ou la limite |
| migrations non appliquées | `relation "..." does not exist` | migrer au déploiement |
| dépendance absente | `ModuleNotFoundError`, `Cannot find module` | l'ajouter au fichier de dépendances |

Un arrêt propre sur SIGTERM (un redéploiement normal) sort `CLEAN`, jamais « crash ».

## Installer

```bash
claude plugin marketplace add Darius-Tokam/ai-packs
claude plugin install deploy-doctor@ai-packs
```

## Le lancer

Pas de commande à retenir. Dans le dossier du projet, dis à Claude Code : « mon déploiement Railway a planté », « pourquoi mon build échoue ? » ou « my deploy crashed ». Le skill lit les logs avec la CLI de ta plateforme si elle est connectée, sinon il te demande de coller la fin du log.

Tu peux aussi lancer le script seul, sans Claude : `python3 scripts/diagnose.py deploy.log --project .` (Python 3, sans dépendance).

## Testé sur 11 déploiements

8 déploiements en panne, dont 4 reconstitués à partir d'incidents réels de l'auteur, et 3 déploiements sains : 8 causes sur 8 nommées, 0 fausse alerte sur les 3 sains, et la cause appuyée par une ligne de code dans les 5 cas qui fournissent leurs fichiers de démarrage. Le détail, les mesures et la limite du test sont dans [test/RESULTS.md](test/RESULTS.md). Tu peux rejouer le test avec `test/build_cases.py` et `test/run_checks.py`.

## Langues

Le skill répond dans ta langue. Ses instructions sont en anglais (Claude les exécute mieux ainsi), ce guide est en français.

---

Fait par [Darius Tokam](https://tokamdarius.ca) · Arivex · Licence MIT
