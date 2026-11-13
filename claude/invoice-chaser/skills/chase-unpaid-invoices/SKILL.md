---
name: chase-unpaid-invoices
description: Run the full invoice-chaser procedure when the user asks, in any language, to chase or follow up unpaid invoices, to find who still owes them money, or to write payment reminders ("relance mes factures impayées", "qui me doit encore de l'argent ?", "prépare mes relances de paiement", "chase my unpaid invoices", "who still owes me money?", "draft payment reminders for my late clients"). Same procedure as /invoice-chaser:chase, started by the request instead of the command.
---

# chase-unpaid-invoices

The user asked to chase unpaid invoices. Run the same procedure as `/invoice-chaser:chase`, started by the request instead of the command.

## 1. Inputs

- Take the as-of date from the request ("au 31 octobre" means 2026-10-31). Default: today.
- Run `ledger-import` to get `invoices.csv` and `bank.csv` from the exports in the current folder. Ask once for the taxes charged and the payment terms (default 30 days). Do not ask again for what the request already says.

## 2. One script run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/chase.py" check --invoices invoices.csv --bank bank.csv --as-of <date> --terms <days> --taxes "<rates>" --out chase_out
```

## 3. The 7 reports, in this order

Each skill gives its own verdict line. Do not stop at the first problem.

1. `bank-match`
2. `tax-check`
3. `duplicate-guard`
4. `aging`
5. `priority`
6. `reminder-writer`: drafts in `reminders/`, then `chase.py verify` until 0 problems
7. `chase-plan`

Print one summary table:

| Agent | Verdict | Findings |
|---|---|---|

Then the final line, copied from the report: `CHASE VERDICT: <amount> to recover on <n> invoices, <m> emails, <amount> on hold`.

## 4. Stop there

Show the drafts and the verdict. Never send an email, never change the user's accounting files, never compute an amount yourself: every amount comes from `chase.py`. If the user then asks to send a reminder, send only a draft that `chase.py verify` passed, and only after an explicit yes for that client.
