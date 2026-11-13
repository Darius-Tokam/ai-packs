---
name: tax-check
description: Recompute the sales taxes and totals of each invoice (TPS/TVQ, GST/HST, VAT or any rate the user gives) and hold any wrong invoice before it is chased. Use before sending reminders or closing a tax period.
---

# tax-check

Chasing a wrong invoice gives the client a reason not to pay it. Fix first, chase second.

## 1. Get the rates

Ask the user which taxes they charge. Examples:

- Quebec: `--taxes "TPS:5,TVQ:9.975"` (both on the price before taxes, per Revenu Quebec).
- Ontario: `--taxes "HST:13"`.
- France: `--taxes "TVA:20"`.

Never guess a rate from the client's location: rates depend on the supply and on the seller's registration. If the user is not registered, run without `--taxes`.

## 2. Run

`chase.py check ... --taxes "<rates>"`. Each tax is compared to `subtotal x rate` rounded to the cent, with a 1 cent tolerance, and the total to `subtotal + taxes`.

## 3. Report

```
BLOCK | F-2026-016 | TVQ is 152,00 $, expected 159,60 $ (9.975 % of 1 600,00 $) | issue a corrected invoice, then chase
```

A BLOCK puts the invoice on hold: the reminder-writer will skip it. End with `TAX VERDICT: CLEAN` or `TAX VERDICT: <n> BLOCK`.

This is an arithmetic check, not tax advice. For what is taxable, the user checks with their accountant or the tax authority.
