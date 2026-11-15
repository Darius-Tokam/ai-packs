# Résultats du test : post-recycler sur un vrai post

Test du 12 novembre 2026. Rejouable avec Python 3.10 ou plus, sans dépendance :

```bash
python build_trap.py /tmp/recycle-trap
python run_checks.py /tmp/recycle-trap
```

La sortie complète du dernier passage est dans [run_output.txt](run_output.txt).

## Le post source

[source.md](source.md) : le post LinkedIn du pack n°1 de ce dépôt ([pr-squad](../../pr-squad)), 1 600 caractères environ, en français, avec 12 chiffres différents (8 défauts, ligne 24, PyYAML 5.3.1, 150 %, -500, 41 requêtes, 20 factures...).

## Les 10 formats

Rédigés en suivant les skills du pack, dans [output/](output), puis passés au garde-fou `check_formats.py` :

| Format | Mesure | Limite | Origine de la limite | Résultat |
|---|---|---|---|---|
| Post X | 240 caractères | 280 | X, compte gratuit | PASS |
| Fil X | 6 posts, le plus long à 191 | 280 par post | X, compte gratuit | PASS |
| Threads | 286 octets | 500 octets UTF-8 | Threads | PASS |
| Bluesky | 219 caractères | 300 | Bluesky | PASS |
| Carrousel | 8 slides, 20 mots au plus | 5 à 10 slides, 30 mots | règle du pack | PASS |
| Instagram | 550 caractères, 5 hashtags | 2 200, 5 hashtags | Instagram ; règle du pack pour les hashtags | PASS |
| Script vidéo | 64 mots dits | 55 à 90 (environ 30 s) | règle du pack | PASS |
| Newsletter | objet de 45 caractères, 154 mots | objet 60, corps 80 à 250 mots | règle du pack | PASS |
| Citation | 17 mots | 20 | règle du pack | PASS |
| Story | 4 écrans, 9 mots au plus | 3 à 5 écrans, 15 mots | règle du pack | PASS |

**10 formats sur 10 passent au premier passage**, avec 0 chiffre absent du post source, 0 lien étranger, 0 tiret long et 10 premières lignes différentes.

Les limites des plateformes viennent de la page d'aide de Buffer, [Character limits for each social network](https://support.buffer.com/article/588-character-limits-for-each-social-network), consultée le 12 novembre 2026 : X 280 (compte gratuit), Threads 500 comptés en octets UTF-8, Bluesky 300, Instagram 2 200. Les autres limites sont des règles du pack, réglables dans `check_formats.py`.

## Le piège : 8 défauts plantés

`build_trap.py` copie les 10 formats et en casse 8, un défaut chacun. Le script vidéo et la story restent propres pour mesurer les fausses alertes.

| # | Défaut planté | Mesure du garde-fou | Résultat |
|---|---|---|---|
| 1 | Post X trop long | 359 caractères sur 280 | attrapé |
| 2 | Un post du fil X trop long | post 4 : 302 caractères | attrapé |
| 3 | Post Threads de 476 caractères, donc sous 500, mais plein d'accents | 516 octets sur 500 | attrapé |
| 4 | Chiffre inventé sur Bluesky : « 73 % plus vite » | 73 absent du post source | attrapé |
| 5 | Slide de carrousel trop chargée | 49 mots sur 30 | attrapé |
| 6 | 9 hashtags sur Instagram | 9 sur 5 | attrapé |
| 7 | Objet de newsletter trop long | 74 caractères sur 60 | attrapé |
| 8 | Tiret long dans la citation | tiret détecté | attrapé |

**8 défauts plantés, 8 attrapés, 0 fausse alerte** sur les 2 formats restés propres.

Le défaut 3 est celui qu'un compteur de caractères ne voit pas : en français, chaque lettre accentuée compte double sur Threads.

## Limite du test

Le même agent a écrit le pack, rédigé les 10 formats, planté les défauts et lancé le garde-fou. Il connaissait les règles en rédigeant : le 10 sur 10 au premier passage ne dit pas comment le pack s'en sort sur un post qu'il découvre. Les mesures du garde-fou sont déterministes et reproductibles avec `run_checks.py`. La qualité éditoriale des formats (ton, accroche) n'est pas mesurée, seulement leurs limites et leur fidélité aux chiffres. Le garde-fou vérifie les chiffres et les liens, pas les affirmations sans chiffre. Le décompte en octets de Threads vient de la documentation de Buffer ; le garde-fou l'applique par prudence. Lance `/post-recycler:recycle` sur un de tes posts et compare.

Le skill d'entrée `recycle-my-post` (ajouté le 13 novembre 2026) lance la même procédure sans la commande. Son déclenchement par le modèle, à partir d'une phrase comme « décline mon post pour X et Instagram », n'a pas été testé : seule la procédure qu'il appelle l'a été. Le test a été rejoué le 13 novembre 2026, après le passage du lien du dépôt au nouveau nom du compte GitHub (`Darius-Tokam`) : `RESULT: PASS`, mêmes mesures, sauf le post Bluesky qui passe de 220 à 219 caractères (un caractère de moins dans le lien).
