---
name: bank-match
description: Reconcile unpaid invoices with bank deposits before any reminder is sent - finds invoices already paid but still marked unpaid, partial payments, and deposits with no invoice number. Use before chasing a client, so nobody gets a reminder for an invoice they paid.
---

# bank-match

The most expensive reminder is the one sent to a client who already paid. This skill prevents it.

## 1. Run the match

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/chase.py" check --invoices invoices.csv --bank bank.csv --as-of <date> --taxes "<taxes>" --out chase_out
```

The script matches in two passes:
1. the deposit memo cites the invoice number: sure match, partial or full;
2. no number, but the exact total and a word of the client name are in the memo: probable match.

## 2. Review what it found

Read the `bank-match` lines of `chase_out/report.md`:

- **paid in full, marked unpaid**: tell the user to mark it paid in their accounting tool. Never chase it.
- **partial payment**: only the balance is chased. The reminder must name what was received.
- **probable match**: show the deposit line and ask the user to confirm. Until confirmed, keep it out of the reminders.
- **marked paid, no deposit found**: the payment may sit in another account or a payment processor (Stripe, PayPal). Ask, do not chase.
- **deposit that matches no invoice**: list it. It can be an invoice missing from the export.

## 3. Report

```
FIX  | F-2026-007 | paid 1 609,65 $ on 2026-08-04, still unpaid in the books | mark paid, do not chase
FIX  | F-2026-010 | 600,00 $ received of 1 149,75 $ | chase 549,75 $ only
FIX  | F-2026-012 | 1 437,19 $ on 2026-10-03, no reference, same amount and client | confirm, then mark paid
NOTE | -          | 0,42 $ on 2026-10-31 (Interets compte) | no invoice
```

End with `MATCH VERDICT: <n> reminders avoided (<amount>)`.
