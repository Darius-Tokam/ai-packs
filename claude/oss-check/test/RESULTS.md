# Résultats du test : oss-check sur les 3 outils vérifiés à la main par l'auteur

Test du 19 novembre 2026, lancé avec Python 3.13.18. Rejouable sans dépendance et sans réseau :

```bash
python build_case.py /tmp/oss-check-cases
python run_checks.py /tmp/oss-check-cases
```

La sortie complète du dernier passage est dans [run_output.txt](run_output.txt). Les cas générés restent dans le dossier donné et ne sont jamais commités. `run_checks.py` ne lit pas le code du script : il le lance comme une commande, compare ses sorties aux chiffres publiés par l'auteur et à `expected.json` (écrit par `build_case.py`), puis se relance lui-même sur 10 copies du script où un bug a été introduit.

## D'où vient le cas

Le sujet vient de trois posts LinkedIn de Darius Tokam où il a fait ce travail à la main, et de sa leçon « Open source ne veut pas dire usage commercial libre » (notes du 11 et du 12 juillet 2026) : une bibliothèque publiée en open source peut porter une licence qui restreint l'usage commercial.

1. **29 août 2026**, « J'ai installé un convertisseur de documents. Il est venu avec un moteur de calcul symbolique. » Trois environnements Python neufs et un témoin vide pour soustraire pip. Pile à la carte (pypdf, python-docx, openpyxl, python-pptx, markdownify) : 13 paquets, 39,5 Mo. `pip install markitdown` : 25 paquets, 147,7 Mo. `pip install markitdown[all]` : 56 paquets, 319,7 Mo. Les plus lourds : pandas 52,6 Mo, sympy 48,6 Mo, numpy 48,6 Mo, speech_recognition 42,7 Mo, onnxruntime 33,7 Mo. 11 des 13 paquets de la pile à la carte sont déjà dans markitdown. Mesuré sous Windows avec Python 3.10, disque seulement.
2. **31 août 2026**, « J'ai installé Open WebUI pour rester hors ligne. Il a commencé par télécharger 933 Mo. » Open WebUI 0.11.1 promet « does not make any external connections ». Au premier démarrage : 49 requêtes vers huggingface.co et 933 Mo téléchargés ; au deuxième, une seule requête. Sur une machine déjà coupée du réseau, il ne démarre pas, et rien à l'écran ne prévient.
3. **1er septembre 2026**, « J'ai compté les outils de Stirling PDF. 55, comme annoncé. C'est sa licence qui m'a arrêté. » Stirling PDF 2.14.3 : le LICENSE annonce MIT puis découpe six répertoires qui gardent leur propre licence, dont deux « proprietary » ; GitHub affiche NOASSERTION ; dans ces répertoires, l'usage en production est réservé à une licence payante. Le code compilé de ces répertoires voyage dans l'image Docker, avec un vérificateur de licence qui appelle api.keygen.sh, dormant tant qu'on n'entre pas de clé. L'auteur précise qu'il n'est pas juriste et qu'il cite le fichier.

Ce qui est réel dans le cas :

- les chiffres publiés du cas 1 (paquets et Mo des trois piles, les 5 plus lourds et leur poids, 11 des 13 paquets communs) et la méthode (témoin vide soustrait) ;
- la forme du cas 2 : une promesse « pas de connexion externe » dans le README, un modèle d'embedding téléchargé depuis huggingface.co au démarrage, une variable qui coupe ;
- la forme du cas 3 : un LICENSE MIT qui découpe 6 répertoires, dont 2 sous une licence propriétaire qui réserve la production à une licence payante, et un vérificateur de licence qui appelle api.keygen.sh et enregistre des machines, derrière la clé.

Ce qui est inventé : les noms des projets (convertisseur, Chat Local, Papyrus PDF, TableKit, docsift, mini-slug, geo-tiles, csvtool, Queueforge), tout le code, les textes des licences propriétaire et commerciale, les versions, le poids du témoin (pip et setuptools), la liste exacte des paquets de chaque environnement et le poids de ceux que le post ne donne pas, choisis pour retomber sur les totaux publiés. Les 2 paquets de la pile à la carte absents de `markitdown[all]` sont pypdf et typing-extensions (le post dit seulement que ce sont « ceux du PDF »). sympy et numpy, publiés tous deux à 48,6 Mo, sont séparés de 80 000 octets pour garder l'ordre du post. Les fichiers lourds sont creux (`os.truncate`) : la taille mesurée est la taille apparente, et les environnements simulés ne prennent presque rien sur le disque.

Ce qui n'est pas reproduit : les 49 requêtes et les 933 Mo du cas 2 se mesurent en lançant l'outil, ce que le script ne fait pas : il compte les sites d'appel dans le code (2). Le contenu du jar compilé du cas 3 n'est pas simulé : le vérificateur y est en Java source.

### Ce qui est planté

| Cas | Type | Planté | Ce que le script doit rendre |
|---|---|---|---|
| darius-1-markitdown | réel | témoin, pile à la carte, markitdown, markitdown[all] en site-packages avec RECORD ; dépôt source MIT | les chiffres publiés, les 5 plus lourds, 11 des 13 communs, OK pour les 4 usages |
| darius-2-open-webui | réel | README qui promet « no external connections » ; `snapshot_download(` et `SentenceTransformer(` sans garde ; `OFFLINE_MODE` qui pose `HF_HUB_OFFLINE` ; PostHog derrière `ENABLE_POSTHOG`, faux par défaut | 2 appels au premier lancement, 1 dormant, les 2 réglages qui coupent, promesse contredite, ATTENTION pour les 4 usages |
| darius-3-stirling-pdf | réel | LICENSE MIT qui découpe 6 répertoires ; 2 sous une licence « Production use of the Papyrus Software is only permitted with a valid User License. » ; 4 sous Apache-2.0, MIT, OFL-1.1 et BSD-3-Clause ; vérificateur Java vers api.keygen.sh avec sortie anticipée sans clé | 6 découpages dont 2 non libres, NOASSERTION, 2 appels dormants, OK en perso, ATTENTION ailleurs |
| piege-double-licence | piège | LICENSE AGPL-3.0, LICENSE-COMMERCIAL.md, `"license": "AGPL-3.0-only OR LicenseRef-Commercial"`, node_modules avec un paquet à portée @ et un paquet imbriqué | double licence, pas un cumul : OK en perso et en interne, ATTENTION en SaaS et en redistribution ; 4 paquets, 4,5 Mo |
| piege-extra-lourd | piège | 2 dépendances de base, torch et transformers derrière `[ocr]`, pandas en plus derrière `[all]` ; `from_pretrained(` derrière `if self.use_ocr:` | lourds cachés derrière les extras, aucun dans la base ; 1 appel dormant ; OK |
| propre-mit | propre | « proprietary » dans un commentaire, une chaîne et le README | MIT, rien d'autre |
| propre-apache | propre | Apache-2.0, NOTICE, 3 en-têtes SPDX ; huggingface.co dans docs/ et `from_pretrained(` dans tests/ | 0 appel, 3 lignes ignorées |
| propre-bsd | propre | GPL-3.0 et « proprietary » cités dans le CHANGELOG ; `check_for_updates()` dans une docstring | BSD-3-Clause seule, 0 appel |
| controle-busl | contrôle | BUSL-1.1, « Additional Use Grant: None » | OK en perso, STOP en interne, en SaaS et en redistribution |

## Résultats mesurés

Copiés de la sortie de `run_checks.py`.

### Verdict par cas et par usage

| Cas | Type | perso | interne | saas | redistribution |
|---|---|---|---|---|---|
| darius-1-markitdown/repo | réel | OK | OK | OK | OK |
| darius-2-open-webui | réel | ATTENTION | ATTENTION | ATTENTION | ATTENTION |
| darius-3-stirling-pdf | réel | OK | ATTENTION | ATTENTION | ATTENTION |
| piege-double-licence | piège | OK | OK | ATTENTION | ATTENTION |
| piege-extra-lourd | piège | OK | OK | OK | OK |
| propre-mit | propre | OK | OK | OK | OK |
| propre-apache | propre | OK | OK | OK | OK |
| propre-bsd | propre | OK | OK | OK | OK |
| controle-busl | contrôle | OK | STOP | STOP | STOP |

**36 verdicts justes sur 36.** Trois des lignes finales :

```
OSS-CHECK: OK pour saas : licence MIT, 56 paquets, 319,7 Mo, 0 appels réseau au démarrage
OSS-CHECK: ATTENTION pour perso : licence BSD-3-Clause, 5 paquets, taille non mesurée, 2 appels réseau au démarrage
OSS-CHECK: ATTENTION pour interne : licence MIT avec découpage (6 répertoires, 2 non libres), ? paquets, taille non mesurée, 0 appels réseau au démarrage
```

### Chiffres publiés par l'auteur face au script (cas 1)

| Environnement | Publié | Mesuré par le script | Écart | Résultat |
|---|---|---|---|---|
| a-la-carte | 13 paquets, 39,5 Mo | 13 paquets, 39,5 Mo | +0 paquet, 0,00 Mo | PASS |
| markitdown | 25 paquets, 147,7 Mo | 25 paquets, 147,7 Mo | +0 paquet, 0,00 Mo | PASS |
| markitdown-all | 56 paquets, 319,7 Mo | 56 paquets, 319,7 Mo | +0 paquet, 0,00 Mo | PASS |

| Rang | Publié | Mesuré | Écart |
|---|---|---|---|
| 1 | pandas 52,6 Mo | pandas 52,6 Mo | 0,00 Mo |
| 2 | sympy 48,6 Mo | sympy 48,6 Mo | 0,04 Mo |
| 3 | numpy 48,6 Mo | numpy 48,6 Mo | -0,04 Mo |
| 4 | speech_recognition 42,7 Mo | SpeechRecognition 42,7 Mo | 0,00 Mo |
| 5 | onnxruntime 33,7 Mo | onnxruntime 33,7 Mo | 0,00 Mo |

Les écarts de 0,04 Mo viennent du cas (les 80 000 octets qui séparent sympy et numpy), pas du script. Le post écrit « speech_recognition », le nom du module ; le script donne le nom du paquet, SpeechRecognition.

Ce que le script ajoute au post : les 5 lourds connus font 226,2 Mo, soit 70,8 % de `markitdown[all]` ; dans `markitdown` seul, sympy, numpy et onnxruntime font déjà 130,9 Mo sur 147,7 (88,6 %). Le post écrit aussi que markitdown contient la pile à la carte « plus 43 autres » (56 moins 13) ; le script compte 45 paquets de `markitdown[all]` absents de la pile à la carte (56 moins les 11 communs).

### Appels réseau trouvés

| Cas | Premier lancement (attendu / trouvé) | Dormants (attendu / trouvé) | Détail | Résultat |
|---|---|---|---|---|
| darius-1-markitdown/repo | 0 / 0 | 0 / 0 | aucun | PASS |
| darius-2-open-webui | 2 / 2 | 1 / 1 | huggingface.co utils.py:15, sans garde; huggingface.co utils.py:20, sans garde; posthog telemetry.py:12, derrière l'option ENABLE_POSTHOG (défaut : false) | PASS |
| darius-3-stirling-pdf | 0 / 0 | 2 / 2 | api.keygen.sh KeygenLicenseVerifier.java:28, derrière une clé (licence ou API); api.keygen.sh KeygenLicenseVerifier.java:38, derrière une clé (licence ou API) | PASS |
| piege-double-licence | 0 / 0 | 0 / 0 | aucun | PASS |
| piege-extra-lourd | 0 / 0 | 1 / 1 | huggingface.co extract.py:12, derrière l'option use_ocr (défaut : false) | PASS |
| propre-mit | 0 / 0 | 0 / 0 | aucun | PASS |
| propre-apache | 0 / 0 | 0 / 0 | aucun | PASS |
| propre-bsd | 0 / 0 | 0 / 0 | aucun | PASS |
| controle-busl | 0 / 0 | 0 / 0 | aucun | PASS |

### Fausses alertes

Une alerte est un découpage, un appel réseau, un écart entre manifeste et LICENSE, ou un usage qui n'est pas OK.

| Cas | Type | Alertes attendues | Alertes trouvées | Fausses | Manquées |
|---|---|---|---|---|---|
| darius-1-markitdown/repo | réel | 0 | 0 | 0 | 0 |
| darius-2-open-webui | réel | 7 | 7 | 0 | 0 |
| darius-3-stirling-pdf | réel | 11 | 11 | 0 | 0 |
| piege-double-licence | piège | 2 | 2 | 0 | 0 |
| piege-extra-lourd | piège | 1 | 1 | 0 | 0 |
| propre-mit | propre | 0 | 0 | 0 | 0 |
| propre-apache | propre | 0 | 0 | 0 | 0 |
| propre-bsd | propre | 0 | 0 | 0 | 0 |
| controle-busl | contrôle | 3 | 3 | 0 | 0 |

**0 fausse alerte sur les 3 dépôts propres et les 2 pièges.**

### Contrôles

| Section | Contrôle | Attendu | Mesuré | Résultat |
|---|---|---|---|---|
| verdict | verdicts justes (cas x usage) | 36/36 | 36/36 | PASS |
| sortie | ligne finale du texte identique au JSON | 36/36 | 36/36 | PASS |
| sortie | code de sortie = verdict (0 OK, 1 ATTENTION, 2 STOP) | 36/36 | 36/36 | PASS |
| sortie | ligne finale au format OSS-CHECK exact | 36/36 | 36/36 | PASS |
| poids | a-la-carte : paquets et Mo (tolérance 0,1 Mo), texte = JSON | 13, 39,5 Mo | 13, 39,5 Mo | PASS |
| poids | markitdown : paquets et Mo (tolérance 0,1 Mo), texte = JSON | 25, 147,7 Mo | 25, 147,7 Mo | PASS |
| poids | markitdown-all : paquets et Mo (tolérance 0,1 Mo), texte = JSON | 56, 319,7 Mo | 56, 319,7 Mo | PASS |
| poids | les 5 plus lourds de markitdown[all], noms et Mo | 5/5 | 5/5 | PASS |
| poids | lourds connus signalés dans markitdown[all] | les 5 publiés | les 5 publiés | PASS |
| poids | part des lourds connus dans markitdown[all] | mesurée | 226,2 Mo (70,8 %) | PASS |
| poids | lourds connus dans markitdown seul | mesurés | sympy, numpy, onnxruntime = 130,9 Mo (88,6 %) | PASS |
| poids | pile à la carte contenue dans markitdown[all] | 11 des 13 | 11 des 13 | PASS |
| poids | les 2 absents de markitdown[all] | pypdf, typing-extensions | pypdf, typing-extensions | PASS |
| poids | paquets de markitdown[all] absents de la pile à la carte | 56 - 11 = 45 | 56 - 11 = 45 | PASS |
| poids | témoin soustrait | pip, setuptools | pip, setuptools | PASS |
| poids | Node : node_modules (dont 1 paquet à portée @ et 1 imbriqué) | 4 paquets, 4,5 Mo | 4 paquets, 4,5 Mo | PASS |
| licence | darius-1-markitdown/repo : étiquette | MIT | MIT | PASS |
| licence | darius-2-open-webui : étiquette | BSD-3-Clause | BSD-3-Clause | PASS |
| licence | darius-3-stirling-pdf : étiquette | MIT avec découpage (6 répertoires, 2 non libres) | MIT avec découpage (6 répertoires, 2 non libres) | PASS |
| licence | piege-double-licence : étiquette | AGPL-3.0 ou commerciale | AGPL-3.0 ou commerciale | PASS |
| licence | piege-extra-lourd : étiquette | MIT | MIT | PASS |
| licence | propre-mit : étiquette | MIT | MIT | PASS |
| licence | propre-apache : étiquette | Apache-2.0 | Apache-2.0 | PASS |
| licence | propre-bsd : étiquette | BSD-3-Clause | BSD-3-Clause | PASS |
| licence | controle-busl : étiquette | BUSL-1.1 | BUSL-1.1 | PASS |
| licence | cas 3 : répertoires découpés trouvés | 6 | 6 | PASS |
| licence | cas 3 : dont non libres (proprietary) | 2 | 2 | PASS |
| licence | cas 3 : identifiant global (GitHub affiche NOASSERTION) | NOASSERTION | NOASSERTION | PASS |
| licence | cas 3 : clause citée | 2 x « Production use ... » | 2 x « Production use ... » | PASS |
| licence | double licence : options trouvées | AGPL-3.0, commerciale | AGPL-3.0, commerciale | PASS |
| licence | Apache-2.0 : NOTICE et en-têtes SPDX | NOTICE ; Apache-2.0 x 3 | NOTICE ; Apache-2.0 x 3 | PASS |
| poids | extra : dépendances de base | pypdf, requests | pypdf, requests | PASS |
| poids | extra : lourds cachés derrière [ocr] et [all] | ocr : torch, transformers ; all : pandas, torch, transformers | ocr : torch, transformers ; all : pandas, torch, transformers | PASS |
| poids | extra : lourds dans la base | aucun | aucun | PASS |
| réseau | cas 2 : réglages qui coupent trouvés dans le code | HF_HUB_OFFLINE, OFFLINE_MODE | HF_HUB_OFFLINE, OFFLINE_MODE | PASS |
| réseau | cas 2 : promesse du README contredite | oui | oui | PASS |
| réseau | cas 2 : télémétrie derrière une option désactivée par défaut | ENABLE_POSTHOG | ENABLE_POSTHOG | PASS |
| réseau | cas 3 : service de clés, dormant derrière la clé | api.keygen.sh x 2 | api.keygen.sh x 2 | PASS |
| réseau | cas 3 : promesse du README non contredite | non contredite | non contredite | PASS |
| fausses alertes | sur les 3 propres et les 2 pièges | 0 | 0 | PASS |
| fausses alertes | alertes manquées sur les pièges | 0 | 0 | PASS |
| piège | « proprietary » dans un commentaire et une chaîne (propre-mit) | aucune licence proprietary | aucune licence proprietary | PASS |
| piège | huggingface.co dans docs/ et tests/ (propre-apache) | 0 appel, 3 lignes ignorées | 0 appel, 3 lignes ignorées | PASS |
| piège | GPL-3.0 cité dans le CHANGELOG (propre-bsd) | BSD-3-Clause seule | BSD-3-Clause seule | PASS |
| piège | check_for_updates() dans une docstring (propre-bsd) | 0 appel, 1 ignoré | 0 appel, 1 ignoré | PASS |
| piège | URL huggingface.co en commentaire, docs/ et tests/ (cas 2) | 1 commentaire, 2 doc ou test ignorés | 1 commentaire, 2 doc ou test ignorés | PASS |
| citation | citations de 15 mots au plus, copiées du fichier | 60/60 | 60/60 | PASS |
| sortie | network et license : chiffres du texte = JSON | 18/18 | 18/18 | PASS |
| sortie | deux lancements identiques | identiques | identiques | PASS |
| sortie | dossier absent : code 3 | 3 | 3 | PASS |
| sortie | usage inconnu : code 3 | 3 | 3 | PASS |
| copies cassées | copies du script avec un bug, rejetées par le test | 10/10 | 10/10 | PASS |
| temps | médiane de 5 lancements : report cas 1 avec markitdown[all] (56 paquets) | mesuré | 70 ms | PASS |
| temps | médiane de 5 lancements : report cas 3 (Stirling PDF reconstitué) | mesuré | 70 ms | PASS |
| hygiène | fichiers avec un tiret long ou moyen | aucun | aucun | PASS |
| hygiène | fichiers avec l'ancien nom du compte | aucun | aucun | PASS |

**Contrôles : 56/56 PASS.**

### Les copies cassées

Chaque copie du script porte un seul bug. Le test doit échouer sur chacune, sinon il ne protège pas ce que le bug casse.

| Bug introduit | Rejetée |
|---|---|
| témoin non soustrait | oui |
| Mo comptés en Mio (1 048 576 octets) | oui |
| découpage du LICENSE ignoré | oui |
| découpage non libre jugé comme la licence de tout le projet (STOP au lieu d'ATTENTION) | oui |
| double licence lue comme un cumul | oui |
| commentaires lus comme du code | oui |
| tests et doc lus comme du code | oui |
| garde par clé ignorée | oui |
| promesse du README ignorée | oui |
| extras comptés dans la base | oui |

## Limite du test

- Le même agent a écrit le script, construit les cas et lancé le test : rien n'est à l'aveugle, et 36 sur 36 dit seulement que le script trouve ce pour quoi ses règles ont été écrites. Les 10 copies cassées montrent que le test attrape ces 10 bugs-là, pas tous les bugs.
- Les chiffres du cas 1 sont reproduits par construction : les environnements simulés sont fabriqués pour redonner les totaux publiés. Le test vérifie la lecture des RECORD, la soustraction du témoin, le tri, la comparaison des piles et l'arrondi, pas ce que pèse markitdown aujourd'hui. Aucune vraie installation n'a été faite (pas de réseau), et les fichiers creux mesurent la taille apparente, pas la place réelle sur le disque.
- Les cas 2 et 3 sont reconstitués sur leur forme : le script n'a pas été lancé sur le vrai code d'Open WebUI ni de Stirling PDF. Sur un vrai dépôt, il y aura plus de code, des appels écrits autrement et des gardes plus lointaines.
- Le déclenchement du skill d'entrée `check-before-install` par le modèle, à partir d'une phrase comme « est-ce que je peux utiliser cette lib au travail ? », n'a pas été testé.
- Ce que les agents Claude feraient avec le jugement n'a pas été testé à l'aveugle : suivre un appel depuis le point d'entrée, lire une licence écrite seulement dans le README, dire si les répertoires non libres voyagent dans l'image Docker. Seul le script est mesuré.
- La lecture du réseau est une heuristique : un appel est dormant si le `if` qui l'entoure (ou une sortie anticipée juste avant) teste une clé, ou une option dont la valeur par défaut trouvée dans le code est fausse ; sinon il est compté au premier lancement. Le script ne suit pas le graphe d'appels : un appel sans garde qui ne part qu'à l'usage d'une fonction est compté au démarrage. Il compte des sites d'appel, pas des requêtes ni des mégaoctets téléchargés, et il ne lit ni le code compilé ni les Dockerfile.
- Les licences sont reconnues par des phrases de leurs textes officiels et par les champs des manifestes ; une licence maison sort en « non reconnue » (ATTENTION). Les statuts par usage sont des choix écrits dans le script (par exemple : AGPL OK en interne et ATTENTION en SaaS ; un répertoire non libre donne ATTENTION, pas STOP, parce que le reste du projet reste libre). Ce sont des repères pour lire les fichiers, pas un avis juridique. Dans le vrai cas Stirling PDF, l'auteur a vu que le code de ces répertoires voyage dans l'image Docker : c'est à l'agent de le dire, le script ne le voit pas.
- Les « lourds connus » sont une liste fixe de 27 paquets au-dessus de 5 Mo : un paquet lourd qui n'y est pas sort dans les 5 plus lourds, pas dans les lourds connus.
- Sans manifeste lisible (Java, Go), la ligne dit « ? paquets » : le poids d'une image Docker ou d'un jar n'est pas mesuré.
- Le script fait environ 1 040 lignes, au-dessus de la taille visée (400 à 900).
- Les temps ont été mesurés dans un bac à sable Linux, démarrage de Python compris.
