---
name: quote-auditor
description: Check a freelance quote against the client's brief before it is sent: every calculation (lines, subtotal, taxes, total), every request of the brief that no line prices, and the hidden work a line does not cover. Use when the user wants to check, review or send a quote, estimate, proposal or devis, or asks whether a quote is complete or correct.
---

# quote-auditor

You check the quote. You never send it and never change the user's prices without a yes.

## 1. Inputs

- The quote: a markdown table (item, hours, rate, amount) and its total lines. If the user's quote is a PDF, a spreadsheet or plain text, rebuild that table in `quote.md` first, one row per priced line, and show it to the user before going on.
- The brief: the client's text. If `scope.md` from brief-reader exists, use it too.
- The tax rates the user charges, if any (for example TPS 5 % and TVQ 9,975 % in Quebec, TVA 20 % in France). Ask once if the quote has tax lines and the user gave no rate. Never decide whether the user must charge a tax: that is their call.

## 2. Run the script once

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/quote_check.py" quote.md brief.md --tax TPS=5 --tax TVQ=9.975
```

Drop the `--tax` options when the user charges no tax. The script prints three groups (Calculs, Demandé pas chiffré, Travail caché), an hours range for the lines with hidden work, and one verdict line: `QUOTE VERDICT: SEND` or `QUOTE VERDICT: FIX FIRST (n)`.

## 3. Review what the script found, then what it cannot see

- Calculation findings are facts: report them as they are, with the corrected number.
- A "missing" finding comes from a word list. Confirm it against the brief: if a quote line covers the request under another name, say so and drop it. If scope.md lists a request the script did not flag and no line covers it, add it.
- A "hidden work" finding means the brief hints at work the line does not mention. Keep it, and give the question from scope.md that would settle it.
- The hours range applies a x1.2 to x2.0 margin to the lines with hidden work. Present it as a margin, not as a forecast, and say that unpriced requests are outside it.

## 4. Report

1. One table: | Finding | Where | Why it matters | Fix |
2. The corrected lines you propose (new line, new hours, new amount), clearly marked as proposals.
3. A short message to the client with the open questions, in the client's language, ready to copy. Do not send it.
4. One final line: `QUOTE: SEND` when nothing is left, otherwise `QUOTE: FIX FIRST (<n>)`.

Never edit the user's quote file without an explicit yes. Never send anything to the client.
