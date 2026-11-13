---
description: Reconcile invoices with the bank, check taxes and duplicates, rank late invoices and draft one reminder per client.
argument-hint: "[as-of date YYYY-MM-DD, optional]"
---

Chase the unpaid invoices of the user. As-of date given: $ARGUMENTS (today if empty).

1. `ledger-import`: get `invoices.csv` and `bank.csv`. Ask once for the taxes charged and the payment terms (default 30 days).
2. Run once:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/chase.py" check --invoices invoices.csv --bank bank.csv --as-of <date> --terms <days> --taxes "<rates>" --out chase_out
   ```
3. Report with these skills, in this order, each with its own verdict line:
   1. `bank-match`
   2. `tax-check`
   3. `duplicate-guard`
   4. `aging`
   5. `priority`
   6. `reminder-writer` (drafts in `reminders/`, then `chase.py verify` until 0 problems)
   7. `chase-plan`
4. Print one summary table:

| Agent | Verdict | Findings |
|---|---|---|

5. Final line, copied from the report: `CHASE VERDICT: <amount> to recover on <n> invoices, <m> emails, <amount> on hold`.

Never send an email, never change the user's accounting files. Every amount comes from the script, never from mental math.
