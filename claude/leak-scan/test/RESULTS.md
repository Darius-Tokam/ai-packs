# Résultats du test : leak-scan sur un log de production reconstitué

Test du 17 novembre 2026, lancé avec Python 3.13 (et repassé avec Python 3.11 et 3.12), et Node 22 pour le filtre Node. Rejouable sans dépendance :

```bash
python build_cases.py /tmp/leak-cases
python run_checks.py /tmp/leak-cases
```

La sortie complète du dernier passage est dans [run_output.txt](run_output.txt). Les logs générés restent dans le dossier donné et ne sont jamais commités.

## D'où vient le cas

Le sujet vient de deux incidents de l'auteur.

- Le 27 août 2026, la clé d'API Gemini de son SaaS (Gridar) s'est retrouvée en clair dans ses logs Railway, au bout d'une chaîne de trois maillons anodins. La clé était interpolée dans l'URL (`...:generateContent?key=...`) ; `raise_for_status()` levait une `HTTPError` dont le message contient l'URL complète, paramètres compris ; un `except Exception: logger.exception(...)` l'écrivait. Le quota était épuisé : chaque appel renvoyait 429 et écrivait une ligne de plus avec la clé, en boucle. Vérifié le même jour sur PageSpeed : une exception de timeout (94 caractères) ne contenait pas la clé ; le message d'un `raise_for_status` et `response.url` la contenaient. La clé PageSpeed n'avait échappé que parce que `key` était le dernier paramètre et que les handlers tronquaient entre 80 et 120 caractères : une protection par accident.
- Les 13 et 15 septembre 2026, dans son app Publiar, la lecture des logs de production a trouvé des URL d'images présignées loggées avec leur signature (valables 24 à 48 heures) et des secrets passés en paramètres d'URL dans les callbacks OAuth de Facebook et d'Instagram.

La règle que l'auteur a écrite ensuite : un filtre de logs qui masque `key=`, `token=`, `api_key=`, `Bearer ...` avant l'écriture est la vraie ceinture ; et après une fuite, le correctif ne suffit pas : il faut renouveler la clé.

`build_cases.py` reconstitue, avec une graine fixe (20260827), un log de cette forme : 2 021 lignes horodatées comme Railway, mêlant un log d'accès gunicorn, des lignes Django et Celery, des lignes JSON pino d'un service Node et des traces Python. Ce ne sont pas les logs de l'auteur : chaque ligne, nom, domaine et secret est inventé. Les faux secrets sont assemblés au lancement à partir de morceaux et de caractères tirés au hasard, pour qu'aucun fichier du dépôt ne contienne une chaîne qui ressemble à une vraie clé. Les fuites de deux apps et de trois dates sont réunies dans un seul log d'une journée (15 septembre 2026).

Ce qui est planté dans `app.log` :

| Planté | Forme | Lignes | Ce que le script doit faire |
|---|---|---|---|
| clé Gemini dans l'URL, dans le message de l'`HTTPError` écrit par `logger.exception`, réécrite par une boucle de 429 | clé ou secret en clair | 150 | une seule fuite, avec ses 150 lignes, la première et la dernière |
| clé PageSpeed en dernier paramètre, coupée par un handler qui tronque à 120 caractères (17 ou 24 caractères visibles sur 39) | clé ou secret en clair | 3 | une seule fuite, marquée « fuite partielle » |
| URL présignée S3 valable 24 h, 5 objets signés par la même clé d'accès | URL présignée | 5 | une fuite, regroupée par la clé qui signe |
| URL signée GCS valable 48 h, loggée par un worker Node, 4 objets, un même compte de service | URL présignée | 4 | une fuite |
| callback OAuth qui reçoit `access_token` dans sa query string, 3 connexions | secret OAuth dans une URL | 3 | une fuite, regroupée par endpoint |
| échange OAuth loggé par urllib3 en DEBUG, `client_secret` et `code` dans l'URL, 2 connexions | secret OAuth dans une URL | 2 | une fuite (le client_secret), le code nommé avec |
| `Authorization: Bearer <JWT>` dans le log de requête pino, 2 utilisateurs | en-tête recopié | 4 | une fuite, regroupée par en-tête |
| `x-api-key` dans un `console.log(req.headers)` imprimé sur 7 lignes | en-tête recopié | 3 | une fuite, sur la seule ligne de la clé |
| adresse e-mail de client dans un log Django | e-mail de client | 2 | une fuite |
| adresse e-mail de client dans un log Node | e-mail de client | 2 | une fuite |

Les pièges ne doivent jamais être signalés. 19 sortes, plantées 3 fois dans `app.log` (102 lignes) et 2 fois dans `clean.log`, un log de 500 lignes sans aucune fuite (68 lignes) : `sort_key=created_at` ; `?page=2&per_page=50` ; `token_count=1532` et `max_tokens=2048` ; un SHA git de 40 et de 7 caractères ; des UUID d'identifiant de requête ; une empreinte sha256 et un ETag ; un `key=` vide ; des valeurs déjà masquées (`key=[REDACTED]`, `Bearer ***`, `api_key=****a1b2`, `"password":"********"`) ; « password reset email sent » et « invalid password for user » ; des adresses sur `example.com`, `example.org`, `.test` et `.invalid`, et des expéditeurs no-reply ; un callback OAuth refusé, sans code ; `code=` hors OAuth (un code promo court, un code promo de 18 caractères, un code HTTP) ; une URL S3 publique sans signature ; `logo@2x.png` et `git@github.com` ; la ligne PageSpeed coupée juste avant la clé (la protection par accident) et le timeout sans clé ; « Authorization header missing » ; un cookie `csrftoken` ; un `next_page_token` ; la ligne `url = f"{GEMINI_URL}:generateContent?key={api_key}"` affichée dans une trace.

`formats.log` ajoute 52 lignes isolées dans des formats que le log principal n'utilise pas (nginx, curl, Stripe, Sentry, Kubernetes, CI, systemd) : 17 fuites (une clé Google dans une URL Maps, `Authorization: Basic`, une clé `sk-proj-` dans un curl, un mot de passe dans une URL Redis, `GITHUB_TOKEN=`, `"apiKey"` en JSON, un jeton OAuth Google `ya29.`, un jeton Slack, `aws_secret_access_key=`, un `apikey=` hexadécimal, `key=key-...`, un cookie de session, une SAS Azure, une URL CloudFront signée, l'adresse e-mail d'un utilisateur, un code OAuth Google, `"password"` en JSON) et 35 lignes qui n'en sont pas (identifiants Stripe et clé publique `pk_live_`, clés de cache, `x-amz-request-id` et `traceparent`, cookies vidés, `password_hash`, `[Filtered]` de Sentry, `${PARTNER_API_KEY}`, `Bearer YOUR_TOKEN`, une unité systemd `getty@...`, une clé d'objet S3, une clé Redis, une clé Stripe déjà masquée par Stripe, un champ `"auth_token"` dont la valeur est une phrase, entre autres).

`run_checks.py` ne lit pas le code du script : il le lance comme une commande et compare ses sorties (rapport JSON, rapport Markdown, copie masquée, filtres Python et Node) à `truth.json`, écrit par `build_cases.py`.

## Résultats mesurés

Copiés de la sortie de `run_checks.py` :

| Contrôle | Attendu | Mesuré | Résultat |
|---|---|---|---|
| fuites distinctes trouvées | 10/10, chacune une seule fois | 10/10 | PASS |
| lignes signalées pour chaque fuite | 10/10 identiques à la vérité | 10/10 | PASS |
| forme de chaque fuite | 10/10 | 10/10 | PASS |
| boucle de 429 : clé Gemini | 1 fuite, 150 lignes, l. 228 à 2016 | 1 fuite, 150 lignes, l. 228 à 2016 | PASS |
| clé coupée par la troncature | 1 fuite partielle (« fuite partielle »), 3 lignes, aucune autre partielle | partielle : oui, 3 lignes, 17 à 24 car. visibles sur 39, autres partielles : 0 | PASS |
| URL présignées regroupées par signataire | S3 : 1 fuite, 5 signatures ; GCS : 1 fuite, 4 signatures | S3 : 5 signatures ; GCS : 4 signatures | PASS |
| fuites en trop (faux positifs) | 0 | 0 | PASS |
| pièges signalés | 0 sur 102 lignes pièges (19 sortes) | 0 ligne(s) | PASS |
| cause, correctif et rotation pour chaque fuite | 10/10 | 10/10 | PASS |
| code de sortie, log qui fuit | 1 | 1 | PASS |
| log propre | 0 fuite, code 0 (500 lignes, 68 lignes pièges) | 0 fuite, code 0 | PASS |
| autres formats (nginx, curl, Stripe, Sentry, Kubernetes, CI, systemd) | 17/17 lignes qui fuient signalées, 0/35 autres | 17/17 signalées, 0/35 autres | PASS |
| aucun secret complet dans le rapport Markdown | 0 sur 25 valeurs plantées | 0 | PASS |
| aucun secret complet dans le rapport JSON | 0 sur 25 valeurs plantées | 0 | PASS |
| --redact puis nouveau scan | 0 fuite, code 0 | 0 fuite, code 0 | PASS |
| --redact : lignes modifiées | exactement les 178 lignes qui fuient, même nombre de lignes | 178 modifiées, 0 hors fuite, 2021 lignes | PASS |
| --redact : secrets dans la copie | 0 | 0 | PASS |
| --filter python, chaque ligne passée par logging | 2 021 lignes identiques à --redact | 2 021/2 021 identiques | PASS |
| --filter python sur logger.exception (la chaîne Gemini) | clé absente de la trace, [REDACTED] présent | clé absente : oui, [REDACTED] : oui | PASS |
| --filter node (v22.23.4), même log | 2 021 lignes identiques à --redact | 2 021/2 021 identiques | PASS |
| log lu sur l'entrée standard | même résultat que le fichier | identique | PASS |
| codes de sortie | fuite 1, propre 0, fichier absent 2, option inconnue 2 | fuite 1, propre 0, fichier absent 2, option inconnue 2 | PASS |
| temps médian sur 2 021 lignes (7 passages, démarrage de Python compris) | moins de 1 000 ms | 141 ms | PASS |
| tiret long ou moyen dans le pack | aucun | aucun | PASS |

**10 fuites sur 10 trouvées, chacune une seule fois et sur exactement ses lignes : 178 lignes signalées, aucune en trop. La clé Gemini réécrite 150 fois par la boucle de 429 sort comme une seule fuite ; la clé coupée par la troncature est la seule « fuite partielle ». 0 fausse alerte sur les 102 lignes pièges, sur le log propre de 500 lignes et sur les 35 lignes saines d'autres formats. Aucun des 25 secrets plantés n'apparaît en entier dans les rapports. Le filtre Python, posé sur un handler `logging`, masque les 2 021 lignes exactement comme `--redact`, et masque la clé dans la trace d'un `logger.exception` : le maillon de l'incident Gemini.**

Les 10 fuites du rapport, dans son ordre :

| # | Forme | Ce qui fuit | Lignes | Statut |
|---|---|---|---|---|
| 1 | clé ou secret en clair | clé d'API Google, paramètre key | 150 | fuite complète |
| 2 | clé ou secret en clair | clé d'API Google, paramètre key | 3 | fuite partielle (17 à 24 caractères visibles sur 39) |
| 3 | URL présignée avec sa signature | URL présignée S3 | 5 | fuite complète, 5 signatures, valable 24 h |
| 4 | URL présignée avec sa signature | URL signée Google Cloud Storage | 4 | fuite complète, 4 signatures, valable 48 h |
| 5 | secret OAuth dans une URL | access_token dans une URL OAuth | 3 | fuite complète, 3 jetons |
| 6 | secret OAuth dans une URL | client_secret dans une URL OAuth, avec code | 2 | fuite complète |
| 7 | en-tête d'authentification recopié | en-tête x-api-key | 3 | fuite complète |
| 8 | en-tête d'authentification recopié | en-tête Authorization Bearer | 4 | fuite complète, 2 jetons |
| 9 | adresse e-mail de client | adresse e-mail | 2 | fuite complète |
| 10 | adresse e-mail de client | adresse e-mail | 2 | fuite complète |

Hors du test, le même log copié 50 fois (101 050 lignes, 14,9 Mo) a été lu en 5 secondes environ (4,7 à 5,1 sur 3 passages) avec 69 Mo de mémoire, et donne toujours 10 fuites, sur 8 900 lignes.

Pendant la construction, des copies volontairement cassées du script ont été passées au test : limite gauche des noms de paramètres retirée (`sort_key` et `token_count` deviennent des fuites), extrait qui montre la valeur entière, une fuite par ligne au lieu d'une par secret, détection de troncature retirée, domaines réservés acceptés, valeurs déjà masquées acceptées, code de sortie toujours 0, `code=` accepté sur n'importe quel chemin, URL présignées regroupées par signature au lieu de la clé qui signe, filtre Python qui ne masque pas la trace, phrase acceptée comme valeur d'un champ `token`. Chacune des 11 a fait sortir `RESULT: FAIL`. La première version du test laissait passer la copie qui accepte `code=` partout : le seul piège, `code=WELCOME10`, était trop court pour être retenu de toute façon et ne testait donc pas la règle du chemin OAuth. Un code promo de 18 caractères a été ajouté aux pièges ; cette copie échoue depuis.

Aucune attente n'a été changée pour faire passer le script. Quatre règles ont été resserrées après une recherche de fausses alertes hors du test. Lancé sur les 12 582 lignes des autres fichiers texte du dépôt et sur les logs système de la machine de test, le script signalait `getty@tty1.service` (une unité systemd lue comme une adresse e-mail) et `postgres://user:pass@` (un exemple de documentation) ; en écrivant des lignes d'autres formats, il acceptait aussi tout `key=` de 20 caractères avec une lettre et un chiffre, donc une clé de cache comme `key=build-cache-v3-linux` ; lancé sur ses propres fichiers, il prenait pour un secret un champ dont le nom finit par `-token` et dont la valeur est une phrase (`"google-oauth-token": "jeton OAuth Google"`). Les noms d'unités systemd, la valeur `pass`, les `key=` sans partie aléatoire et les valeurs qui contiennent une espace (sauf pour un mot de passe) sont depuis exclus. Ces cas sont entrés dans `formats.log` avec les autres lignes écrites à ce moment : ces 52 lignes ont été écrites en connaissant les règles, elles ne sont pas à l'aveugle. Sur ces mêmes fichiers, le script signale encore `DB_PASSWORD=changeme` dans le script de test d'un autre pack (une vraie forme de fuite), deux adresses d'exemple sur `exemple.com`, un domaine qui n'est pas réservé, l'adresse de contact d'une licence de police et, dans un log d'installation de paquets, l'adresse de la clé qui signe une archive Ubuntu : de vraies adresses, qui ne sont pas des données de clients.

## Limite du test

Le même agent a écrit le script, construit les logs et lancé les contrôles : les cas ne sont pas à l'aveugle, et 10 sur 10 dit seulement que le script reconnaît les formes pour lesquelles il a été écrit, sur des lignes écrites pour elles. Les logs sont reconstitués, pas de vrais logs de production : aucun log réel de l'auteur n'a été lu, les formats Railway, Django, gunicorn, Celery et pino sont imités, et les fuites de deux apps et de trois dates sont réunies dans un seul log d'une journée.

Le déclenchement du skill par Claude dans une vraie session, à partir d'une phrase comme « cherche les clés qui fuient dans mes logs », n'a pas été testé, ni ce que Claude fait du rapport (retrouver la ligne de code, proposer le correctif, choisir le filtre), ni la récupération des logs par `railway logs` : seul le script l'a été.

Formats non couverts : une clé d'un autre fournisseur sans nom de paramètre reconnaissable (une clé Twilio, Mailgun ou Azure isolée dans une phrase) ; un secret encodé (base64 hors d'un en-tête `Basic`, URL encodée deux fois : `%3Ftoken%3D...` n'est pas vu) ; un secret coupé sur plusieurs lignes et une clé privée PEM ; `name: valeur` sans guillemets (YAML : `password: hunter2`) et `key = valeur` avec des espaces ; les URL de webhook dont le secret est dans le chemin (Slack, Discord). Chaque ligne est lue seule : un log JSON imprimé sur plusieurs lignes n'est pas recollé, ce qui marche tant que le nom et la valeur sont sur la même ligne, comme `'x-api-key': '...'` dans le dump Node du test. Une clé coupée n'est reconnue comme partielle que si son préfixe est connu (`AIza`, `sk_live_`, `ghp_`, `AKIA`...) : une clé inconnue coupée en fin de ligne est signalée comme complète, si elle est signalée.

Toute adresse e-mail hors des domaines réservés et des expéditeurs no-reply est signalée : le script ne distingue pas un client d'un fournisseur, comme le montrent les adresses trouvées ci-dessus. Le filtre Python masque le message, ses arguments et `exc_text` ; un formateur qui formate lui-même `record.exc_info` (certains formateurs JSON) contourne le masquage de la trace, d'où la vérification avec une fausse clé que le skill demande après l'installation, et ni `print()` ni le log d'accès de gunicorn ou uvicorn ne passent par lui sans configuration. Le module Node a été testé sur le même log que `--redact`, par sa fonction `redactSecrets`, pas branché sur pino ni par `install()` dans une vraie app. Le temps est mesuré sur une seule machine, et le script lit chaque fichier en entier en mémoire.
