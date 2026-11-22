# oss-check : 2 agents Claude Code qui vérifient un outil open source avant que tu l'installes

Tu as repéré un outil open source dans un carrousel et tu t'apprêtes à l'installer. Tu tapes `/oss-check:check ./outil saas` (ou tu dis « est-ce que je peux utiliser cette lib au travail ? »). Deux agents lisent ses fichiers de licence et son code. Tu sais ce que la licence permet pour ton usage, avec la phrase exacte et son fichier, découpages compris ; combien de paquets et de mégaoctets l'installation tire avec elle ; et quels appels réseau partent au premier lancement ou dorment derrière une clé, avec le réglage qui les coupe. Tu finis sur une ligne : OK, ATTENTION ou STOP. Rien n'est installé ni lancé sans toi.

| Agent | Ce qu'il fait |
|---|---|
| `license-reader` | lit tous les fichiers de licence (LICENSE, COPYING, licences par répertoire, en-têtes SPDX, champ license de package.json, pyproject.toml, setup.cfg), repère les découpages et les doubles licences, classe chaque licence (permissive, copyleft, copyleft réseau, source disponible et non libre, commerciale) et dit, pour ton usage, ce que les fichiers permettent, avec la phrase exacte en 15 mots au plus et son chemin |
| `install-weigher` | compte les paquets et les mégaoctets d'une installation moins un témoin vide, sort les plus lourds et les lourds connus qui servent rarement au but, les lourds cachés derrière un extra, ce qu'une pile contient de l'autre, et cherche dans le code les appels qui vont chercher quelque chose dehors (modèles, clés de licence, télémétrie, mises à jour), au premier lancement ou dormants |

Le script `scripts/oss_check.py` fait la partie mesurable. Python 3, sans dépendance, hors ligne : il ne lance rien, n'installe rien et ne télécharge rien. Les agents ajoutent le jugement : un appel qui ne part qu'à l'usage d'une fonction, une licence écrite seulement dans le README, du code compilé que la lecture ne voit pas.

## Installer

```bash
claude plugin marketplace add Darius-Tokam/ai-packs
claude plugin install oss-check@ai-packs
```

## Le lancer

```
/oss-check:check ./stirling-pdf interne
/oss-check:check https://github.com/exemple/outil saas
```

Quatre usages : `perso` (chez toi), `interne` (dans ton entreprise, production comprise), `saas` (un service que tu vends), `redistribution` (dans un produit ou une image que tu livres). Sans usage, l'agent te le demande une fois. Une URL est clonée en lecture seule dans un dossier temporaire.

La dernière ligne a toujours la même forme :

```
OSS-CHECK: ATTENTION pour interne : licence MIT avec découpage (6 répertoires, 2 non libres), ? paquets, taille non mesurée, 0 appels réseau au démarrage
```

- **STOP** : la licence du projet interdit l'usage demandé (production réservée à une licence payante, pas de service, pas de revente, aucune licence).
- **ATTENTION** : une restriction partielle (un répertoire découpé sous une licence non libre, l'AGPL pour un SaaS, une double licence dont l'option libre a des obligations, le copyleft si tu redistribues), ou un appel réseau au premier lancement que le README n'annonce pas.
- **OK** : rien dans les fichiers ne restreint ton usage, et rien ne part au démarrage sans être annoncé.

Pour le poids réel, l'agent te demande ton accord, installe l'outil dans un environnement jetable à côté d'un témoin vide, et compte. Sans ton accord, il s'en tient aux dépendances déclarées, et la ligne dit « taille non mesurée » (« ? paquets » quand aucun manifeste n'est lisible, pour un projet Java par exemple).

### Sans taper la commande

Dis simplement à Claude Code « est-ce que je peux utiliser cette lib au travail ? », « vérifie la licence de cet outil avant que je l'installe », « combien pèse cette install ? » ou, en anglais, « can I use this library commercially? » et « check this repo's license before I install it ». Le skill `check-before-install` lance la même procédure que la commande.

## Le script seul

```bash
python3 scripts/oss_check.py license ./outil
python3 scripts/oss_check.py weigh ./venv-outil --baseline ./venv-vide --compare ./venv-autre
python3 scripts/oss_check.py weigh ./outil/node_modules
python3 scripts/oss_check.py weigh ./outil
python3 scripts/oss_check.py network ./outil
python3 scripts/oss_check.py report ./outil --usage saas --env ./venv-outil --baseline ./venv-vide
```

- `license` : la licence du projet ou les options d'une double licence, l'identifiant global (`NOASSERTION` quand le LICENSE découpe des répertoires), chaque découpage avec sa licence, les en-têtes SPDX, les fichiers NOTICE, et un statut par usage avec la phrase citée et son chemin.
- `weigh` : sur un site-packages, un venv ou un node_modules installé, les paquets et les octets, moins le témoin, les 5 plus lourds, les lourds connus et leur part du total, et avec `--compare` ce qu'une pile contient de l'autre. Sur un dépôt source, les dépendances déclarées et les lourds cachés derrière un extra. La taille est la taille apparente des fichiers listés dans chaque RECORD, 1 Mo = 1 000 000 octets.
- `network` : les appels trouvés dans le code, classés au premier lancement ou dormants (derrière une clé ou une option désactivée par défaut), les variables d'environnement qui les coupent, et la promesse du README face au code. Les tests, la doc, les commentaires et les docstrings sont ignorés.
- `report` : les trois, puis la ligne `OSS-CHECK`.
- `--json` sur chaque commande pour une sortie lisible par une machine ; sinon le texte est en français.

Codes de sortie : `0` étape terminée (ou verdict OK), `1` verdict ATTENTION, `2` verdict STOP, `3` entrée invalide (dossier absent, usage inconnu).

## Testé sur les 3 outils vérifiés à la main par l'auteur

L'auteur a fait ce travail à la main sur trois outils en août et septembre 2026, et l'a raconté sur LinkedIn : markitdown, Open WebUI et Stirling PDF. Le test les reconstitue sur leur forme (noms de projets, code et textes inventés, chiffres publiés repris), avec 2 pièges, 3 dépôts propres et un dépôt sous BUSL pour le verdict STOP.

- **markitdown** : le script retrouve les chiffres publiés, 13 paquets et 39,5 Mo pour la pile à la carte, 25 paquets et 147,7 Mo pour `markitdown`, 56 paquets et 319,7 Mo pour `markitdown[all]`, les 5 plus lourds à leur poids publié, et 11 des 13 paquets de la pile à la carte déjà dans `markitdown[all]`. Les 5 lourds connus font 70,8 % du total. Les environnements simulés sont fabriqués pour redonner ces totaux : le test vérifie que le script les retrouve, pas ce que pèse markitdown aujourd'hui.
- **Open WebUI** : 2 appels vers huggingface.co au premier lancement, contraires à la promesse « does not make any external connections » du README, coupés par `OFFLINE_MODE` et `HF_HUB_OFFLINE` ; la télémétrie reste dormante derrière une option désactivée par défaut. ATTENTION pour les 4 usages.
- **Stirling PDF** : 6 répertoires découpés dont 2 non libres, identifiant global NOASSERTION, la clause « Production use ... » citée, 2 appels au service de clés api.keygen.sh dormants derrière la clé. OK en perso, ATTENTION en interne, en SaaS et en redistribution.

36 verdicts justes sur 36 (9 dépôts, 4 usages), 0 fausse alerte sur les 3 dépôts propres et les 2 pièges, 60 citations sur 60 copiées du fichier en 15 mots au plus, et les 10 copies du script où un bug a été introduit sont toutes rejetées par le test. Médiane de 5 lancements : 70 ms pour le rapport complet sur `markitdown[all]`. Le détail, les mesures et la limite du test sont dans [test/RESULTS.md](test/RESULTS.md).

```bash
python test/build_case.py /tmp/oss-check-cases
python test/run_checks.py /tmp/oss-check-cases
```

## Ce qu'il ne fait pas

- Il ne donne pas d'avis juridique : il cite les fichiers. Pour un contrat, c'est un juriste.
- Il ne lance pas l'outil : la lecture du code dit qui il peut appeler, pas ce qu'il envoie, et le code compilé (jar, binaires, JS minifié) n'est pas lu.
- Il ne suit pas le graphe d'appels : un appel sans garde est compté au premier lancement, et l'agent vérifie s'il part vraiment au démarrage.
- Il n'installe rien sans ton accord, et jamais dans ton projet ni dans ton environnement.

## Bonus n8n

Le workflow n8n [oss-watch](../../n8n/oss-watch/) reçoit la liste des dépendances d'un projet (webhook, CSV ou autre workflow) et te prévient quand une dépendance change de licence ou passe à une licence non libre.

## Langues

Les agents répondent dans ta langue. Leurs instructions sont en anglais (Claude les exécute mieux ainsi), ce guide et la sortie du script sont en français. Les citations restent dans la langue du fichier de licence. Le script reconnaît les promesses « hors ligne » écrites en anglais et en français.

---

Fait par [Darius Tokam](https://tokamdarius.ca) · Arivex · Licence MIT
