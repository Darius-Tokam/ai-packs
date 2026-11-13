---
name: reminder-writer
description: Draft one payment reminder email per client from the invoice-chaser plan, at the right firmness (courteous, firm, final notice), citing only invoice numbers and amounts from the plan, then verify every number with a script. Use after bank-match, tax-check and duplicate-guard. Drafts only, never sends.
---

# reminder-writer

## 1. Read the plan

`chase_out/plan.json`, key `emails`: one entry per client with its level, invoices and amount. Write nothing for invoices on `hold` or `wait`.

## 2. Write one file per client

`reminders/<client-slug>.md`, in the client's language (French by default for a French-speaking user). First line exactly `client: <client name as in the plan>`, then `to:`, `subject:`, a blank line, the body.

Levels:
- **L1 rappel courtois** (1 to 14 days late): assume an oversight. Invoice number, amount, due date, how to pay. 4 to 6 lines.
- **L2 relance ferme** (15 to 44 days): restate the facts, ask for a payment date by a given day (5 business days). No threat.
- **L3 dernier avis** (45 days and more): list every late invoice and the total, set a final date (10 days), say what happens next only if the user confirmed it (late fees written in the contract, pause of the work, collection). Never invent a penalty, an interest rate or a legal step.

Rules for every level:
- Cite each invoice number of the entry, with its balance. Partial payment: name the amount received and ask only for the balance.
- Amounts in the client's format (`1 380,50 $` in French, `$1,380.50` in English). Copy them from the plan, never recompute by hand.
- One clear way to pay: `[lien de paiement]` or the bank details placeholder the user fills in. Never write real bank details in the draft.
- No guilt, no sarcasm, no long or medium dash.
- Sign with the user's name placeholder `[Ton nom]`.

## 3. Verify

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/chase.py" verify --plan chase_out/plan.json --emails reminders/
```

It flags: an invoice not in the plan, an invoice of another client, an invoice on hold, a late invoice missing from the email, an amount that matches no balance, total or payment, a dash. Fix every PROBLEM and rerun until `0 problems`.

## 4. Report

```
REMINDERS | 4 drafts in reminders/ | VERIFY: 4 emails checked, 0 problems
```

The user reads and sends each email from their own mailbox. This skill never sends anything.
