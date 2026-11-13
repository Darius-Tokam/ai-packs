---
name: ledger-import
description: Convert an invoice export (QuickBooks, Wave, FreshBooks, Stripe, Excel, any CSV) and a bank export into the two standard files invoice-chaser reads. Use first, whenever the user hands over books or bank statements to chase unpaid invoices.
---

# ledger-import

Goal: two clean files, `invoices.csv` and `bank.csv`, without changing a single amount.

## 1. Find the inputs

Ask for, or look in the working folder for: the invoice list (CSV or XLSX export of the accounting tool) and the bank export covering at least the same period. A PDF statement is fine: extract the lines, then show them to the user before using them.

## 2. Map the columns

Target formats:

```
invoices.csv  number,client,client_email,issue_date,due_date,subtotal,tax1,tax2,total,status
bank.csv      date,amount,memo
```

- Dates in `YYYY-MM-DD`. Amounts with a dot, no currency sign, no thousands separator.
- `status` is what the books say: `paid`, `unpaid` or `partial`. Do not correct it here: bank-match does that with proof.
- `tax1` and `tax2`: the two sales taxes if the user charges them (in Quebec: TPS then TVQ). One tax: leave `tax2` at 0. No tax: both at 0.
- Leave `due_date` empty when the export has none. Never invent one.
- `bank.csv` keeps deposits and withdrawals; only deposits are used.

Write a short mapping table (source column to target column) and show it before writing the files.

## 3. Validate

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/chase.py" check --invoices invoices.csv --bank bank.csv --as-of $(date +%F) --out chase_out
```

If `CLAUDE_PLUGIN_ROOT` is empty, the script is at `../../scripts/chase.py` from this skill's base directory. A parse error means a column is wrong: fix the mapping, not the numbers.

## 4. Report

```
IMPORT | invoices.csv: 21 rows (export "Invoices 2026.xlsx", sheet 1) | bank.csv: 11 rows (statement 2026-05 to 2026-11)
IMPORT | unmapped columns: "Project", "Notes" (ignored)
```
