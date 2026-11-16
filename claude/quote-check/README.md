# quote-check : 2 agents Claude Code qui relisent ton devis avant que le client le lise

Tu as le courriel du client et ton devis. Tu tapes `/quote-check:check` (ou tu dis « vérifie mon devis avant que je l'envoie »). Deux agents comparent les deux : ce que le client a demandé et que le devis oublie, le travail caché derrière une ligne (fuseaux horaires, annulations, rôles), et chaque calcul, taxes comprises. Rien ne part sans toi.

| Agent | Ce qu'il fait |
|---|---|
| `brief-reader` | liste tout ce que le client a demandé, avec ses propres mots, le travail caché derrière chaque demande et la question à lui poser |
| `quote-auditor` | lance le script de contrôle, confronte le devis à cette liste, propose les lignes corrigées et le message de questions pour le client |

Le script `scripts/quote_check.py` fait la partie mesurable : les calculs (chaque ligne, le sous-total, chaque taxe, le total), les demandes du brief qu'aucune ligne ne chiffre, et le travail caché que le brief laisse entendre. Pour les lignes à travail caché, il donne une fourchette d'heures avec une marge de x1,2 à x2,0. Python 3, sans dépendance, utilisable seul.

## Installer

```bash
claude plugin marketplace add Darius-Tokam/ai-packs
claude plugin install quote-check@ai-packs
```

## Le lancer

```
/quote-check:check devis.md courriel-client.md TPS=5 TVQ=9.975
```

Les taxes sont facultatives : donne celles que tu factures (TPS et TVQ au Québec, TVA en France), ou rien si tu n'en factures pas. Le skill ne décide jamais à ta place si tu dois facturer une taxe.

Le devis se lit en tableau markdown (poste, heures, taux, montant), suivi du sous-total, des taxes et du total. S'il est en PDF ou dans un tableur, l'agent le recopie d'abord en tableau et te le montre.

## Sans taper la commande

Dis simplement à Claude Code « vérifie mon devis avant que je l'envoie », « est-ce que mon devis oublie quelque chose ? » ou, en anglais, « check my quote before I send it ». Le skill `check-my-quote` lance la même procédure que la commande.

## Testé sur un devis piégé

Le cas reprend la forme d'un vrai devis de l'auteur : une plateforme avec un module de réservation estimé à 12 h, un devis de 40 h à 75 $/h, et une cliente qui a des clientes dans deux pays. Noms, montants et brief sont inventés. 9 défauts plantés (4 demandes non chiffrées, 3 travaux cachés, 2 erreurs de calcul) : 9 trouvés, 0 en trop. Sur le devis corrigé et sur un devis propre en anglais : 0 fausse alerte. Le détail, les mesures et la limite du test sont dans [test/RESULTS.md](test/RESULTS.md).

```bash
python test/build_case.py /tmp/quote-cases
python test/run_checks.py /tmp/quote-cases
```

## Ce qu'il ne fait pas

- Il ne fixe pas ton prix. Il te montre ce que ton devis ne couvre pas.
- Il ne remplace pas ta lecture du brief : une demande que le client n'a pas écrite ne sort pas.
- Il n'envoie rien et ne modifie pas ton devis sans ton accord.

## Langues

Les agents répondent dans ta langue et écrivent le message au client dans la sienne. Leurs instructions sont en anglais (Claude les exécute mieux ainsi), ce guide est en français. Le script reconnaît les demandes écrites en français et en anglais.

---

Fait par [Darius Tokam](https://tokamdarius.ca) · Arivex · Licence MIT
