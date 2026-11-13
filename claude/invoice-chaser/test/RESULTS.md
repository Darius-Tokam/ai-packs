# Résultats du test : invoice-chaser sur des comptes piégés

Test du 12 novembre 2026. Rejouable avec Python 3.10 ou plus, sans dépendance :

```bash
python build_dataset.py /tmp/books
python run_checks.py /tmp/books
```

La sortie complète du dernier passage est dans [run_output.txt](run_output.txt).

## Les comptes piégés

Un graphiste freelance fictif au Québec : 21 factures (mai à novembre 2026) à 7 clients fictifs (« Demo Alpha » à « Demo Golf », adresses en `example.com`), un relevé bancaire de 11 lignes, TPS 5 % et TVQ 9,975 % calculées sur le prix avant taxes, comme l'indique Revenu Québec ([Calcul des taxes](https://www.revenuquebec.ca/fr/entreprises/taxes/tpstvh-et-tvq/perception-de-la-tps-et-de-la-tvq/calcul-des-taxes/)). Date du test : 12 novembre 2026. Aucune donnée réelle.

8 défauts plantés :

| # | Défaut planté | Agent qui l'a trouvé | Preuve mesurée |
|---|---|---|---|
| 1 | F-2026-007 payée le 4 août, encore « impayée » dans les livres | bank-match | virement de 1 609,65 $ qui cite le numéro de facture |
| 2 | F-2026-010 payée en partie | bank-match | 600,00 $ reçus sur 1 149,75 $ : seul le solde de 549,75 $ est relancé |
| 3 | F-2026-012 payée sans numéro dans le virement | bank-match | 1 437,19 $ le 3 octobre, même montant, nom du client dans le libellé : « probable, à confirmer » |
| 4 | F-2026-018, doublon de F-2026-017 | duplicate-guard | même client, même date, même total : mise en attente |
| 5 | F-2026-014 absente de la numérotation | duplicate-guard | trou entre 013 et 015 |
| 6 | F-2026-016 avec une TVQ à 9,5 % | tax-check | 152,00 $ facturés, 159,60 $ attendus : mise en attente |
| 7 | F-2026-013 sans date d'échéance | aging | échéance supposée à 30 jours, 10 octobre, signalée |
| 8 | F-2026-004, 133 jours de retard | priority | classée en tête : 2 069,55 $ |

**8 défauts plantés, 8 trouvés.** Trouvé en plus, sans l'avoir planté : un dépôt de 0,42 $ (intérêts) rattaché à aucune facture, classé en NOTE.

## Ce que le pack rend

| Mesure | Résultat |
|---|---|
| À relancer | 8 080,63 $ sur 7 factures |
| Courriels rédigés | 4, un par client : 3 derniers avis (dont un qui déduit l'acompte reçu) et 1 relance ferme |
| Factures déjà payées sorties des relances | 2 (3 046,84 $), dont F-2026-012 à confirmer |
| En attente de correction | 2 factures, 2 406,88 $ (TVQ fausse, doublon) |
| Retard par tranche | 1-30 j : 3 441,66 $ · 31-60 j : 3 596,59 $ · 61-90 j : 804,83 $ · 90 j et plus : 2 069,55 $ |
| Vérification des 4 courriels | 0 problème |
| Courriels piégés (4 erreurs plantées : montant faux, facture oubliée, doublon relancé, facture pas encore due) | 4 erreurs sur 4 attrapées |

Verdict de `/invoice-chaser:chase` : `CHASE VERDICT: 8 080,63 $ to recover on 7 invoices, 4 emails, 2 406,88 $ on hold (2 BLOCK, 5 FIX)`.

Les 4 courriels sont dans [emails/](emails), les versions piégées dans [trap_emails/](trap_emails).

## Limite du test

Le même agent a écrit le pack, planté les défauts, rédigé les courriels et lancé les contrôles. Les mesures du script (`chase.py check` et `chase.py verify`) sont déterministes et reproductibles avec `run_checks.py`. La rédaction des courriels, elle, n'est pas un test à l'aveugle, et le relevé bancaire est propre : un vrai relevé a des libellés tronqués, des virements groupés et des frais de plateforme (Stripe, PayPal) qui rendent le rapprochement moins net. Le pack marque alors « probable » et demande confirmation. Lance `/invoice-chaser:chase` sur tes propres exports et compare.

Le pack rédige, il n'envoie rien. Il ne remplace pas ton comptable : tax-check vérifie une multiplication, pas ce qui est taxable.

Le skill d'entrée `chase-unpaid-invoices` (ajouté le 13 novembre 2026) lance la même procédure sans la commande. Son déclenchement par le modèle, à partir d'une phrase comme « relance mes factures impayées », n'a pas été testé : seule la procédure qu'il appelle l'a été. Le test a été rejoué le 13 novembre 2026 avant la sortie du pack : mêmes chiffres, `RESULT: PASS`.
