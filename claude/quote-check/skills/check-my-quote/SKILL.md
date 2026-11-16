---
name: check-my-quote
description: Run the full quote-check procedure (brief-reader, then quote-auditor) when the user asks, in any language, to check, proofread or validate a quote, estimate, proposal or devis before sending it, or asks whether it forgets something ("vérifie mon devis avant que je l'envoie", "relis mon devis", "est-ce que mon devis oublie quelque chose ?", "check my quote before I send it", "is my estimate complete?", "review this proposal against the client's email"). Same procedure as /quote-check:check, started by the request instead of the command.
---

# check-my-quote

The user wants their quote checked before it goes to the client. Run the same procedure as `/quote-check:check`.

1. Find the two inputs: the quote and the client's brief. Take them from the request or the files named. If one is missing, ask for it once, in one sentence.
2. Run `brief-reader` on the brief: it writes `scope.md`.
3. Run `quote-auditor` on the quote, the brief and `scope.md`, with the user's tax rates if the quote has tax lines.
4. Print the report of quote-auditor and its final line, `QUOTE: SEND` or `QUOTE: FIX FIRST (<n>)`.

Stop there. Do not send the quote or the message to the client, and do not edit the quote without an explicit yes.
