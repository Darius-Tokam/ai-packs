# Installer crash-triage, pas à pas

Ce guide part de zéro : tu n'as jamais importé un workflow n8n ni branché un webhook. À la fin, chaque déploiement qui plante t'arrive par courriel avec sa cause, et un redéploiement normal ne t'envoie rien.

Le workflow a deux entrées. **Hébergeur ou CI** marche partout : ta CI, ton script de déploiement, Docker ou un autre workflow n8n envoie le log. **Railway** sert si tu héberges sur Railway : il reçoit l'alerte et va chercher le log tout seul. Garde l'une, l'autre, ou les deux.

## Ce qu'il te faut

- **n8n**, en ligne (n8n Cloud) ou sur ton serveur, joignable depuis Internet. Le workflow a été testé sur n8n 2.47.4.
- **Une source de logs** : une CI, un script ou un serveur capable d'envoyer une requête HTTP (avec `curl`), ou un projet Railway.
- **Un compte Gmail** qui t'enverra les alertes. Ou un autre canal : voir l'étape 4.
- Le fichier [workflow.json](workflow.json) de ce dossier.

## 1. Importer le workflow

1. Télécharge [workflow.json](workflow.json) : bouton **Download raw file** sur GitHub.
2. Dans n8n, crée un workflow vide.
3. Ouvre le menu du workflow (les trois points en haut du canevas), puis **Import from File**, et choisis `workflow.json`.

Tu dois voir 12 nœuds. Quatre portent un triangle rouge : les deux webhooks, **Logs du déploiement (Railway)** et **M'envoyer la cause**. C'est normal, aucun identifiant n'est encore branché.

Pas sur Railway : supprime **Railway : statut du déploiement**, **Logs du déploiement (Railway)** et **Lignes Railway**. Le reste ne change pas, et tu peux sauter l'étape 2.

## 2. Le jeton Railway (seulement pour l'entrée Railway)

1. Ouvre https://railway.com/account/tokens et crée un jeton. Choisis l'équipe (workspace) du projet à surveiller, ou « No workspace » pour un jeton de compte.
2. Dans n8n, ouvre **Logs du déploiement (Railway)**, puis **Credential for Bearer Auth**, **Create new credential**.
3. Colle le jeton dans **Bearer Token** et enregistre.

Un jeton de projet Railway ne marche pas ici : il passe par un autre en-tête. Ne colle le jeton nulle part ailleurs, ni dans un chat, ni dans un log.

## 3. Le secret des webhooks

Les deux webhooks refusent tout appel qui n'a pas le bon en-tête.

1. Choisis une longue valeur aléatoire. Dans un terminal : `openssl rand -hex 32`.
2. Dans n8n, ouvre **Hébergeur ou CI : log du déploiement**, puis **Credential for Header Auth**, **Create new credential**.
3. **Name** : `X-Webhook-Secret`. **Value** : la valeur aléatoire. Enregistre.
4. Choisis le même identifiant sur **Railway : statut du déploiement** si tu l'as gardé.

Garde la valeur : ta CI, ton script ou Railway l'enverront.

## 4. Le canal d'alerte

Par défaut, **M'envoyer la cause** envoie un courriel avec Gmail.

- Sur n8n Cloud : ouvre le nœud, **Create new credential**, **Sign in with Google**.
- Sur ton serveur : il faut une petite application Google (Gmail API activée, écran de consentement, identifiant OAuth de type Web application). La marche à suivre est dans le guide de [relance-radar](../relance-radar/GUIDE.md#sur-ton-propre-serveur) et dans la [documentation de n8n](https://docs.n8n.io/integrations/builtin/credentials/google/oauth-single-service/).
- Un autre canal : supprime **M'envoyer la cause** et branche à sa place, sur la sortie **true** de **Vraie panne ?**, un nœud Slack, Discord, Telegram ou Send Email. Mets `{{ $json.sujet }}` en titre et `{{ $json.texte }}` en message.

## 5. Remplir les réglages

Ouvre le nœud **Réglages** :

| Champ | Ce que tu y mets | Par défaut |
|---|---|---|
| `mon_adresse` | l'adresse qui reçoit les alertes | `toi@exemple.com` (à changer) |
| `lignes_de_log` | combien de lignes de log lire au plus, de 20 à 1 000 | 300 |
| `projets_suivis` | les projets à suivre, séparés par des virgules ; vide = tous | vide |

Active ensuite le workflow (bouton **Active** ou **Publish**, selon ta version de n8n).

## 6. Envoyer un log depuis ta CI, ton script ou un autre workflow

Ouvre **Hébergeur ou CI : log du déploiement** et copie la **Production URL** (elle finit par `/webhook/crash-triage-log`). Pas la Test URL : elle ne marche que pendant un test dans l'éditeur.

L'entrée attend une requête `POST` en JSON, avec l'en-tête `X-Webhook-Secret` :

| Champ | Obligatoire | Ce que c'est |
|---|---|---|
| `service` | oui | le nom du service qui a planté |
| `log` | `log` ou `lines` | le log, en un seul texte |
| `lines` | `log` ou `lines` | le log, une ligne par élément |
| `projet`, `environnement`, `commit` | non | affichés dans le courriel ; `projet` sert au filtre `projets_suivis` |

Depuis un serveur ou un conteneur Docker, après un échec de démarrage :

```bash
docker logs --tail 300 mon-service 2>&1 | jq -Rs --arg s "mon-service" '{service: $s, log: .}' \
  | curl -sS -X POST "$CRASH_TRIAGE_URL" \
      -H "Content-Type: application/json" -H "X-Webhook-Secret: $CRASH_TRIAGE_SECRET" --data @-
```

Depuis GitHub Actions, en fin de job : fais écrire le log du déploiement dans un fichier (par exemple `./deploy.sh 2>&1 | tee deploy.log`, dans une étape `shell: bash` pour que l'échec remonte), puis :

```yaml
      - name: Envoyer le log à crash-triage
        if: failure()
        shell: bash
        run: |
          tail -n 300 deploy.log | jq -Rs --arg s "web" '{service: $s, log: .}' \
            | curl -sS -X POST "$CRASH_TRIAGE_URL" \
                -H "Content-Type: application/json" -H "X-Webhook-Secret: $CRASH_TRIAGE_SECRET" --data @-
        env:
          CRASH_TRIAGE_URL: ${{ secrets.CRASH_TRIAGE_URL }}
          CRASH_TRIAGE_SECRET: ${{ secrets.CRASH_TRIAGE_SECRET }}
```

Range l'adresse et le secret dans les secrets du dépôt, jamais dans le fichier.

Depuis un autre workflow n8n : un nœud **HTTP Request** en `POST` vers la même adresse, avec l'en-tête `X-Webhook-Secret` et un corps JSON qui contient `service` et `log`.

## 7. Brancher Railway (seulement pour l'entrée Railway)

1. Ouvre **Railway : statut du déploiement** et copie la **Production URL** (elle finit par `/webhook/crash-triage`).
2. Dans Railway, ouvre ton projet, puis **Settings** en haut à droite, onglet **Webhooks**.
3. **Webhook URL** : colle la Production URL.
4. Ajoute un en-tête personnalisé : nom `X-Webhook-Secret`, valeur celle de l'étape 3.
5. Dans les événements, garde les changements de statut des déploiements.
6. Clique sur **Test Webhook** : Railway envoie un exemple et doit afficher le code 200. Puis **Save Webhook**.

Le webhook vaut pour tous les environnements du projet. Pour suivre plusieurs projets, ajoute le même webhook dans chacun.

## 8. Le premier essai

- Entrée générique : lance la commande `curl` de l'étape 6 sur un vieux log d'échec. Le courriel arrive avec la cause. Lance-la sur un log d'arrêt normal : rien n'arrive, et l'exécution s'arrête à **Arrêt normal, rien à envoyer** dans l'onglet **Executions**.
- Entrée Railway : redéploie un service qui marche. L'exécution s'arrête à **À analyser**, car un déploiement réussi n'est pas une panne.

Garde les alertes de ton hébergeur tant que tu n'as pas vu passer quelques vraies pannes.

## Si ça ne marche pas

| Ce que tu vois | Cause probable | Ce que tu fais |
|---|---|---|
| `curl` ou **Test Webhook** répond 403 | l'en-tête envoyé ne correspond pas | recopie le nom `X-Webhook-Secret` et la valeur, sans espace, des deux côtés |
| `curl` répond 404 | workflow inactif, ou Test URL utilisée | active le workflow et utilise la Production URL |
| Courriel « aucune ligne de log » depuis ta CI | ni `log` ni `lines` dans la requête, ou un log vide | vérifie la commande `jq` : elle doit produire `{"service": ..., "log": ...}` |
| Courriel « Railway a refusé la lecture des logs : Not Authorized » | jeton invalide, jeton de projet, ou jeton d'une autre équipe | crée un jeton de compte ou de l'équipe du projet, en **Bearer Auth** |
| Courriel « aucune ligne de log » depuis Railway | la panne a eu lieu pendant le build : le workflow ne lit que le log du déploiement | ouvre le log de build dans Railway |
| Courriel « cause non reconnue » | la panne ne ressemble à aucune des 8 | lis les 15 lignes du courriel, ou lance deploy-doctor dans Claude Code |
| Le workflow ne s'active pas | un nœud sans identifiant | branche l'identifiant, ou supprime les nœuds Railway si tu ne t'en sers pas |

## Ce que le workflow ne fait pas

- Il ne touche ni à ton code, ni à ton service : pas de redémarrage, pas de redéploiement.
- Il lit le log qu'on lui donne. Côté Railway, c'est le log du déploiement, pas celui du build.
- Il reconnaît 8 pannes. Hors de celles-là, il te montre les dernières lignes au lieu d'inventer une cause.
- Il ne se tait que sur une preuve d'arrêt normal (`Received SIGTERM`, `Handling signal: term`, `Shutting down`…). Un log sain sans cette preuve t'arrive en « cause non reconnue ».
- Les courriels sont en français. Pour une autre langue, modifie les textes du nœud **Nommer la cause**.

## Sources

- Railway, [Webhooks](https://docs.railway.com/guides/webhooks) : réglage du webhook, forme de l'événement, en-têtes personnalisés, absence de signature. Consulté le 14 novembre 2026.
- Railway, [Deployments](https://docs.railway.com/reference/deployments) : les statuts d'un déploiement, dont `Failed` et `Crashed`. Consulté le 14 novembre 2026.
- Railway, [Public API](https://docs.railway.com/guides/public-api) et [API](https://docs.railway.com/integrations/api) : adresse de l'API, jetons de compte et d'équipe, en-tête `Authorization: Bearer`. Consultés le 14 novembre 2026.
- Railway Station, [GQL unable to get deployment logs](https://station.railway.com/questions/gql-unable-to-get-deployment-logs-7edbf824) : la requête `deploymentLogs` et ses variables. Consulté le 14 novembre 2026.
- n8n, [Google OAuth2 single service](https://docs.n8n.io/integrations/builtin/credentials/google/oauth-single-service/). Consulté le 13 novembre 2026.

---

Fait par [Darius Tokam](https://tokamdarius.ca) · Arivex · Licence MIT
