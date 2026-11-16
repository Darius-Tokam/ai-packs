# crash-triage : la cause de chaque panne de déploiement, ou rien si c'est un arrêt normal

Quand un déploiement plante, ce workflow n8n lit son log, nomme la cause et t'envoie un courriel avec la ligne du log qui le prouve, le correctif et la façon de vérifier. Si le log montre un arrêt normal sur SIGTERM (un redéploiement ordinaire), il n'envoie rien.

Il a deux entrées, pour servir quel que soit ton hébergeur :

- **Hébergeur ou CI** : n'importe quel hébergeur, une CI (GitHub Actions, GitLab), ton script de déploiement, Docker ou un autre workflow n8n envoie le nom du service et son log. Une ligne de `curl` suffit.
- **Railway** : le webhook du projet annonce la panne, et le workflow va chercher le log lui-même par l'API de Railway.

C'est le bonus n8n du pack [deploy-doctor](../../claude/deploy-doctor) : mêmes 8 signatures de panne. Le workflow trie l'alerte au moment où elle arrive ; le skill, dans Claude Code, montre en plus la ligne de code qui provoque la panne.

| Nœud | Ce qu'il fait |
|---|---|
| Hébergeur ou CI : log du déploiement | reçoit `{ "service": "...", "log": "..." }` de n'importe quelle source, protégé par un en-tête secret |
| Railway : statut du déploiement | reçoit l'événement que Railway envoie à chaque changement de statut d'un déploiement, protégé par le même en-tête |
| Réglages | ton adresse, le nombre de lignes de log à lire, les projets à suivre |
| Lire l'entrée | reconnaît l'entrée ; côté Railway, ne garde que les pannes annoncées (`CRASHED` ou `FAILED`) |
| À analyser | laisse passer ce qui doit être lu, ignore le reste |
| Logs à lire chez Railway ? | va chercher le log chez Railway, ou prend celui qui a été envoyé |
| Logs du déploiement (Railway) | demande les dernières lignes du log à l'API de Railway |
| Lignes Railway | met la réponse de Railway dans la même forme qu'un log envoyé |
| Nommer la cause | cherche les 8 pannes connues, puis un arrêt normal |
| Vraie panne ? | sépare ce qui mérite un courriel de l'arrêt normal |
| M'envoyer la cause | t'envoie la cause, la preuve, le correctif et la vérification |
| Arrêt normal, rien à envoyer | fin silencieuse |

Les 8 pannes reconnues : npm (ou yarn, pnpm) qui transforme un redéploiement en échec, `python` appelé là où l'image n'a que `python3`, variable d'environnement absente, production en réglages de développement, serveur qui écoute sur `127.0.0.1`, mémoire épuisée, migrations non appliquées, dépendance absente du build.

Le workflow t'écrit aussi, sans inventer de cause, quand la panne ne ressemble à aucune des 8 (avec les 15 dernières lignes du log), quand le log est vide, ou quand Railway refuse la lecture des logs. Il ne se tait que sur une preuve d'arrêt normal.

Pas sur Railway : supprime les 3 nœuds Railway, le reste marche seul. Pas sur Gmail : remplace **M'envoyer la cause** par Slack, Discord, Telegram ou Send Email, avec `{{ $json.sujet }}` et `{{ $json.texte }}`.

## Installer

Le guide pas à pas est dans [GUIDE.md](GUIDE.md) : importer le fichier, le secret du webhook, Gmail, les réglages, l'envoi depuis ta CI ou ton script, le branchement Railway et les erreurs fréquentes.

En bref :

1. Télécharge [workflow.json](workflow.json), puis dans n8n : menu du workflow (les trois points), **Import from File**.
2. Branche un en-tête secret (type **Header Auth**) sur les deux webhooks et ton Gmail sur **M'envoyer la cause**. Sur Railway, ajoute un jeton (type **Bearer Auth**) sur **Logs du déploiement (Railway)**. Le fichier ne contient aucun identifiant.
3. Remplis **Réglages**, active le workflow, puis envoie tes logs à son adresse de production (ou colle-la dans les webhooks de ton projet Railway).

```bash
tail -n 300 deploy.log | jq -Rs --arg s "web" '{service: $s, log: .}' \
  | curl -sS -X POST "https://ton-n8n/webhook/crash-triage-log" \
      -H "Content-Type: application/json" -H "X-Webhook-Secret: $CRASH_TRIAGE_SECRET" --data @-
```

## Testé sur 21 événements

Les 11 déploiements du test de deploy-doctor (dont 4 reconstituent de vrais incidents de l'auteur), envoyés par l'entrée Railway, plus 4 cas de bord ; puis 6 envois par l'entrée générique. 10 pannes sur 10 nommées avec la ligne de preuve, le correctif et la vérification ; 3 arrêts normaux sur SIGTERM sans aucun courriel ; un log sain sans explication, des logs vides et un jeton refusé signalés sans cause inventée ; un déploiement réussi et deux projets non suivis ignorés. Même cause que le script de deploy-doctor dans 15 cas sur 15. La commande `jq` ci-dessus, rejouée sur un des logs, donne la même cause. Dans n8n, les deux entrées ont tourné en test avec des données simulées et sont passées par la bonne branche. Le détail et la limite du test sont dans [test/RESULTS.md](test/RESULTS.md).

Pour rejouer le test (Python 3.10+ et Node.js ; jq pour le contrôle de la commande) :

```bash
python test/build_events.py /tmp/crash-cases
python test/run_checks.py /tmp/crash-cases
```

---

Fait par [Darius Tokam](https://tokamdarius.ca) · Arivex · Licence MIT
