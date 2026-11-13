# invoice-chaser : 8 agents Claude Code qui retrouvent l'argent qu'on te doit

Tu donnes tes factures et ton relevé bancaire. Tu tapes `/invoice-chaser:chase`. Huit agents rapprochent, vérifient, classent et rédigent un courriel de relance par client. Rien ne part sans toi.

| Agent | Ce qu'il fait | Comment il le prouve |
|---|---|---|
| ledger-import | Convertit ton export (QuickBooks, Wave, FreshBooks, Stripe, Excel) et ton relevé en deux fichiers standards | Tableau de correspondance des colonnes, montré avant d'écrire |
| bank-match | Retrouve les factures déjà payées, les paiements partiels, les virements sans numéro | Chaque rapprochement cite la ligne du relevé |
| aging | Classe les soldes par retard : pas encore dû, 1-30, 31-60, 61-90, 90 jours et plus | Calculé sur le solde après rapprochement, pas sur le total |
| tax-check | Recalcule TPS et TVQ (ou TVH, TVA) et le total de chaque facture | Écart au cent près, la facture fausse est mise en attente |
| duplicate-guard | Doublons (même client, même date, même total) et trous dans la numérotation | Les deux numéros côte à côte |
| priority | Qui relancer en premier : solde x jours de retard | Classement chiffré, et 3 questions sur ce que les chiffres ne voient pas |
| reminder-writer | Un courriel par client : rappel courtois, relance ferme ou dernier avis | `chase.py verify` contrôle chaque numéro de facture et chaque montant |
| chase-plan | Le calendrier des prochaines relances | Une ligne par facture, avec sa date |

Le pack n'envoie aucun courriel et ne modifie pas tes fichiers comptables. Il ne remplace pas ton comptable : tax-check vérifie une multiplication, pas ce qui est taxable.

## Installer

```bash
claude plugin marketplace add Darius-Tokam/ai-packs
claude plugin install invoice-chaser@ai-packs
```

Puis, dans le dossier où sont tes exports :

```
/invoice-chaser:chase
```

Le pack te demande les taxes que tu factures et tes conditions de paiement (30 jours par défaut). Python 3 suffit, sans dépendance.

## Sans taper la commande

Dis simplement à Claude Code ce que tu veux : « relance mes factures impayées » ou « qui me doit encore de l'argent ? ». Le skill `chase-unpaid-invoices` lance la même procédure que `/invoice-chaser:chase` : rapprochement, taxes, doublons, retard, priorité, un courriel par client vérifié par script, puis le calendrier des relances. Il marche aussi en anglais (« chase my unpaid invoices »).

Rien ne part sans toi : le skill montre les brouillons et le verdict, puis s'arrête.

## Testé sur des comptes piégés

21 factures fictives, un relevé bancaire, 8 défauts plantés : 8 trouvés. 8 080,63 $ à relancer sur 7 factures, 2 factures déjà payées sorties des relances, 4 courriels vérifiés. Le détail, les mesures et la limite du test sont dans [test/RESULTS.md](test/RESULTS.md). Tu peux rejouer le test avec `test/build_dataset.py` et `test/run_checks.py`.

## Langues

Les courriels sont rédigés dans la langue du client (français par défaut). Les instructions des agents sont en anglais (Claude les exécute mieux ainsi), ce guide est en français.

---

Fait par [Darius Tokam](https://tokamdarius.ca) · Arivex · Licence MIT
