# post-recycler : 8 agents Claude Code qui transforment un post en 10 formats

Tu colles un post qui a marché. Tu tapes `/post-recycler:recycle`. Huit agents le réécrivent pour X, Threads, Bluesky, un carrousel, Instagram, une vidéo de 30 secondes, ta newsletter, une citation et une story. Un script vérifie chaque limite et chaque chiffre avant que tu publies.

| Agent | Ce qu'il écrit | Ce que le script vérifie |
|---|---|---|
| x-writer | Un post X et un fil de 3 à 8 posts | 280 caractères par post, un lien compte 23 |
| short-posts | Un post Threads et un post Bluesky, chacun avec sa propre accroche | 500 octets sur Threads (les accents comptent double), 300 caractères sur Bluesky |
| carousel | Un carrousel de 5 à 10 slides | 30 mots par slide au plus |
| insta-caption | Une légende Instagram | 2 200 caractères, 5 hashtags au plus |
| video-script | Un script vertical de 30 secondes, avec texte à l'écran | 55 à 90 mots dits |
| newsletter | Une section de newsletter avec son objet | objet de 60 caractères, 80 à 250 mots |
| quote-card | Une citation à mettre en image et une story de 3 à 5 écrans | 20 mots ; 15 mots par écran |
| fact-guard | Le contrôle des 10 formats | Chaque chiffre et chaque lien viennent du post source, aucun tiret long, 10 accroches différentes |

Le pack n'ajoute aucun fait, aucun chiffre, aucun lien absent de ton post. Il ne publie rien : tu copies, tu publies.

## Installer

```bash
claude plugin marketplace add Darius-Tokam/ai-packs
claude plugin install post-recycler@ai-packs
```

Puis :

```
/post-recycler:recycle mon-post.md
```

ou colle le texte du post après la commande. Les 10 formats arrivent dans `recycled/`. Python 3 suffit pour le garde-fou, sans dépendance.

## Sans taper la commande

Dis simplement à Claude Code ce que tu veux : « décline mon post LinkedIn pour X et Instagram » ou « transforme ce post en carrousel ». Le skill `recycle-my-post` lance la même procédure que `/post-recycler:recycle` : il écrit les formats demandés, puis les autres si tu les veux, et le garde-fou vérifie chaque limite et chaque chiffre. Il marche aussi en anglais (« repurpose this post for X and Instagram »).

## Testé sur un vrai post

Le post du pack n°1 de ce dépôt, recyclé en 10 formats : 10 sur 10 dans les limites, 0 chiffre inventé. Sur une version piégée avec 8 défauts (dont un post Threads de 476 caractères qui dépasse 500 octets), 8 attrapés, 0 fausse alerte. Le détail, les mesures et la limite du test sont dans [test/RESULTS.md](test/RESULTS.md). Tu peux rejouer le test avec `test/build_trap.py` et `test/run_checks.py`.

## Langues

Les formats sortent dans la langue du post source, ou dans celle que tu demandes. Les instructions des agents sont en anglais (Claude les exécute mieux ainsi), ce guide est en français.

---

Fait par [Darius Tokam](https://tokamdarius.ca) · Arivex · Licence MIT
