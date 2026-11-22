# leak-scan : un skill Claude Code qui trouve les secrets dans tes logs

Une clé d'API, une URL signée ou un jeton finit parfois en clair dans tes logs de production, recopié par le message d'une exception, un log d'accès ou un dump d'en-têtes, et quiconque lit ces logs peut s'en servir. Tu dis à Claude Code « cherche les clés qui fuient dans mes logs » : le skill lit tes logs, regroupe chaque fuite par secret avec un extrait masqué, la cause et le correctif, puis te donne un filtre de logs qui les masque à partir de maintenant. Il ne recopie jamais un secret en entier et n'envoie tes logs nulle part.

Un seul skill et un script Python, parce qu'il n'y a qu'une étape : lire les logs, repérer les fuites, proposer le filtre.

| Forme de fuite | Ce que tu vois dans le log | Ce que le skill propose |
|---|---|---|
| clé ou secret en clair | `...:generateContent?key=AIza...` dans le message d'une `HTTPError`, `api_key=`, `DB_PASSWORD=`, une clé `sk_live_`, `sk-`, `ghp_`, `AKIA`, `xoxb-`, un JWT, `postgres://user:motdepasse@` | passer la clé dans un en-tête, ne plus logger l'URL ni l'exception brute, renouveler la clé |
| URL présignée avec sa signature | `X-Amz-Signature=`, `X-Goog-Signature=`, `sig=` d'une SAS Azure | logger le chemin de l'objet sans la query string |
| secret OAuth dans une URL | `/callback/?access_token=...`, `client_secret=...&code=...` dans le log d'accès ou les logs DEBUG d'urllib3 | logger le chemin sans la query string, échanger le code en POST, renouveler le client_secret |
| en-tête d'authentification recopié | `Authorization: Bearer ...`, `Basic ...`, `x-api-key:`, `x-goog-api-key:`, `Cookie: sessionid=...` | ne jamais logger les en-têtes bruts : liste blanche, ou masquage (option `redact` de pino) |
| adresse e-mail de client | `order 8841 confirmed for jeanne...@...` | logger l'identifiant du client, purger ou raccourcir la rétention |

Une clé répétée sur 150 lignes compte pour une seule fuite, avec le nombre de lignes, la première et la dernière. Les URL présignées sont regroupées par la clé qui les a signées, les jetons d'utilisateurs par l'endroit où ils fuient. Une clé coupée en fin de ligne par un handler qui tronque les lignes (souvent entre 80 et 120 caractères) est signalée « fuite partielle » : une partie suffit à la reconnaître. Chaque extrait garde les 4 premiers caractères et la longueur (un quart de la valeur sous 16 caractères) : tu peux coller le rapport. Dès qu'il trouve une fuite, il se termine par la même consigne : renouvelle la clé, le correctif arrête la fuite, il n'efface pas ce qui est déjà dans les logs.

## Ce qu'il ne signale jamais

- Les paramètres qui ressemblent à des secrets sans en être : `sort_key=created_at`, `?page=2&per_page=50`, `token_count=1532`, `max_tokens=2048`, les jetons de pagination (`next_page_token=`), les jetons et cookies CSRF.
- Un `key=` nu sans partie aléatoire (au moins 8 caractères qui mêlent lettres et chiffres) : `key=build-cache-v3-linux`, `key=uploads/a.png`, `key=session:42`.
- `code=` hors d'une URL OAuth (code promo, code HTTP), ou un code de moins de 10 caractères.
- Un SHA git, un UUID d'identifiant de requête, une empreinte sha256, un ETag.
- Un `key=` vide, une valeur déjà masquée (`[REDACTED]`, `***`, `****abcd`, `[Filtered]`), un modèle (`{api_key}`, `${TOKEN}`, `<token>`, `YOUR_TOKEN`), une valeur trop courte pour être un secret.
- Le mot « password » dans une phrase sans valeur (« password reset email sent »).
- Une adresse sur un domaine réservé ou de test (`example.com`, `example.org`, `example.net`, `.test`, `.invalid`, `.localhost`), un expéditeur no-reply (`no-reply@`, `noreply@`, `mailer-daemon@`...), un compte de service Google, `git@github.com`, et ce qui ressemble à une adresse sans en être (`logo@2x.png`, `getty@tty1.service`).

Toute autre adresse e-mail est signalée, qu'elle soit celle d'un client, d'un fournisseur ou d'un mainteneur de paquet : le script ne peut pas faire la différence, le skill te dit lesquelles ressemblent à des données de clients. Les règles complètes sont dans [skills/leak-scan/SKILL.md](skills/leak-scan/SKILL.md).

## Installer

```bash
claude plugin marketplace add Darius-Tokam/ai-packs
claude plugin install leak-scan@ai-packs
```

## Le lancer

Pas de commande à retenir. Dans le dossier du projet, dis à Claude Code : « cherche les clés qui fuient dans mes logs », « est-ce que mes logs exposent un secret ? » ou « scan my logs for leaked API keys ». Le skill lit les logs avec la CLI de ta plateforme si elle est connectée (par exemple `railway logs`), sinon il te demande de les coller ou d'indiquer un fichier. Il cherche dans ton code la ligne qui produit chaque fuite, te propose le correctif et le filtre pour ta stack, et ne modifie rien sans ton accord.

Tu peux aussi lancer le script seul, sans Claude : `python3 scripts/leak_scan.py app.log` (Python 3, sans dépendance). Il lit aussi plusieurs fichiers, ou l'entrée standard : `railway logs | python3 scripts/leak_scan.py`.

- `--json` : le rapport en JSON, avec chaque ligne de chaque fuite.
- `--redact copie.log` : écrit une copie du log où chaque fuite est remplacée par `[REDACTED]`, pour la partager.
- `--filter python` : affiche une classe `logging.Filter` prête à coller, qui masque le message, ses arguments et la trace d'un `logger.exception`. À poser sur chaque handler.
- `--filter node` : affiche un module de masquage pour Node, avec `install()` pour masquer tout ce qui sort sur stdout et stderr.

Codes de sortie : `0` aucune fuite, `1` au moins une fuite, `2` entrée invalide (fichier absent, illisible ou binaire, rien sur l'entrée standard, option inconnue).

## Testé sur un log de production reconstitué de 2 021 lignes

10 fuites plantées, 2 par forme, reconstituées à partir d'incidents réels de l'auteur : 10 trouvées sur 10, chacune une seule fois et sur exactement ses lignes. La clé Gemini que la boucle de 429 réécrit sur 150 lignes sort comme une seule fuite, la clé PageSpeed coupée par la troncature est signalée « fuite partielle ». 0 fausse alerte sur 102 lignes pièges de 19 sortes et sur un log propre de 500 lignes ; sur 52 lignes d'autres formats (nginx, curl, Stripe, Sentry, Kubernetes, CI, systemd), les 17 qui fuient sont signalées et aucune des 35 autres. Aucun des 25 secrets plantés n'apparaît en entier dans le rapport. Après `--redact`, un nouveau scan trouve 0 fuite et seules les 178 lignes qui fuyaient ont changé ; le filtre Python posé sur un handler `logging` et le module Node masquent les 2 021 lignes exactement comme `--redact`. Temps médian : 141 ms pour 2 021 lignes, démarrage de Python compris. Le détail, les mesures et la limite du test sont dans [test/RESULTS.md](test/RESULTS.md). Tu peux rejouer le test avec `test/build_cases.py` et `test/run_checks.py`.

## Bonus n8n

Le workflow n8n [leak-watch](../../n8n/leak-watch/) reçoit les lignes de log de n'importe quel hébergeur par webhook et t'alerte avec le secret masqué, avec son guide d'installation pas à pas.

## Langues

Le skill répond dans ta langue. Ses instructions sont en anglais (Claude les exécute mieux ainsi), ce guide et le rapport du script sont en français.

---

Fait par [Darius Tokam](https://tokamdarius.ca) · Arivex · Licence MIT
