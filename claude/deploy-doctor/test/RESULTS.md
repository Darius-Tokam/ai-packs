# Résultats du test : deploy-doctor sur 11 déploiements

Test du 13 novembre 2026. Rejouable avec Python 3.10 ou plus, sans dépendance :

```bash
python build_cases.py /tmp/deploy-cases
python run_checks.py /tmp/deploy-cases
```

La sortie complète du dernier passage est dans [run_output.txt](run_output.txt).

## D'où viennent les cas

Le sujet vient d'une tâche qui revient chez l'auteur : lire les logs d'un déploiement Railway qui a planté et trouver la cause. Quatre cas reconstituent ses incidents, d'après ses notes, avec des noms de projets et de domaines inventés :

| Cas | Incident d'origine | Ce que la note dit |
|---|---|---|
| a1-npm-sigterm | serveur MCP, 8 juillet 2026 | un mail « Deployment crashed » à chaque redéploiement ; le serveur démarrait par `npm run dev:http`, npm en PID 1 traduisait le SIGTERM en échec. Corrigé en lançant `node` directement |
| a2-python-cron | cron d'un outil SEO, 2 juin 2026 | le cron Railway plantait avec `python: command not found` ; le correctif noté est de passer à `python3` |
| a3-missing-allowed-hosts | app Django, 14 juin 2026 | `production.py` lit `ALLOWED_HOSTS` sans défaut : sans la variable, le passage en production plante au démarrage (cas reconstitué à partir de cette règle notée, pas d'un log conservé) |
| a4-debug-page-in-prod | même app Django, 14 juin 2026 | la prod tournait avec les réglages de développement (page « DEBUG = True », SQLite) : `DJANGO_SETTINGS_MODULE` absent de l'hébergeur et `setdefault` vers `development` dans le code |

Les quatre autres pannes sont des messages d'erreur standards : serveur lié à `127.0.0.1` (Railway, [Fixing common errors](https://docs.railway.com/troubleshoot/fixing-common-errors), consulté le 13 novembre 2026 : l'app doit écouter sur `0.0.0.0` et le port de `PORT`), mémoire épuisée de Node, table absente faute de migration, module Python manquant. Les 3 cas sains : un démarrage gunicorn, un arrêt propre de Node sur SIGTERM, un arrêt propre de gunicorn.

## Résultats mesurés

| Cas | Cause attendue | Cause nommée | Preuve dans le log | Preuve dans le code | Résultat |
|---|---|---|---|---|---|
| a1-npm-sigterm | npm-pid1-sigterm | npm-pid1-sigterm | ligne 8 | `Dockerfile:5` `CMD ["npm", "run", "dev:http"]` | PASS |
| a2-python-cron | python-not-found | python-not-found | ligne 2 | `railway.toml:3` `startCommand = "python manage.py ..."` | PASS |
| a3-missing-allowed-hosts | missing-env-var | missing-env-var (ALLOWED_HOSTS) | ligne 7 | `config/settings/production.py:5` | PASS |
| a4-debug-page-in-prod | dev-settings-in-prod | dev-settings-in-prod | ligne 4 | `manage.py:5` `setdefault(... "config.settings.development")` | PASS |
| b1-localhost-binding | port-binding | port-binding | ligne 4 | `main.py:5` `host="127.0.0.1"` | PASS |
| b2-node-heap | out-of-memory | out-of-memory | ligne 3 | (pas de fichiers fournis) | PASS |
| b3-relation-missing | migrations-not-applied | migrations-not-applied | ligne 3 | (pas de fichiers fournis) | PASS |
| b4-missing-module | missing-dependency | missing-dependency (whitenoise) | ligne 3 | (pas de fichiers fournis) | PASS |
| c1-healthy-gunicorn | CLEAN | CLEAN | | | PASS |
| c2-graceful-node | CLEAN | CLEAN (arrêt propre sur SIGTERM) | | | PASS |
| c3-graceful-gunicorn | CLEAN | CLEAN (arrêt propre sur SIGTERM) | | | PASS |

**8 pannes sur 8 nommées, aucune autre cause ajoutée. 0 fausse alerte sur les 3 déploiements sains. La cause est appuyée par une ligne de code dans les 5 cas sur 5 qui fournissent leurs fichiers de démarrage.** Chaque diagnostic donne aussi un correctif et une façon de vérifier.

Le cas c2 est celui qui a trompé l'auteur : en juillet, un agent comptait des redéploiements normaux comme des crashs. Un arrêt propre sur SIGTERM sort `CLEAN`.

## Limite du test

Le même agent a écrit les signatures, construit les 11 cas et lancé les contrôles : les cas ne sont pas à l'aveugle, et 8 sur 8 dit seulement que le script reconnaît les pannes pour lesquelles il a été écrit. Une panne hors de ces 8 signatures sort `CLEAN` : le skill demande alors le bon log et lit lui-même les dernières lignes, une partie qui n'est pas mesurée ici. Les logs sont courts et propres ; un vrai log mélange build, démarrage et requêtes, et peut contenir plusieurs erreurs, dont la première n'est pas toujours la cause. Le cas a3 reconstitue une panne décrite dans une note, sans log conservé. Le déclenchement du skill par le modèle, à partir d'une phrase comme « mon déploiement a planté », n'a pas été testé : seul le script l'a été. Les correctifs sont proposés, jamais appliqués sans ton accord.
