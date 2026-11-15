---
name: x-writer
description: Turn one long post into a single X post (280 characters) and an X thread (3 to 8 posts) that keep its facts and numbers. Use when recycling a LinkedIn post, article or newsletter for X.
---

# x-writer

## Inputs

The source post (file or pasted text) and, if given, the link to promote. Read the source twice: first for the one result a reader would repeat, second for the proof behind it.

## x-post.md

- Line 1: the result, with the source's strongest number. No question, no "thread" teaser.
- Line 2: the proof or the method in one sentence.
- Line 3: the link if there is one, else what the reader gets.
- 280 characters at most; X counts each URL as 23.
- Same language as the source unless the user asks for English.

## x-thread.md

- 3 to 8 posts separated by a line `---`, each 280 characters at most, numbered `1/n`.
- Post 1 stands alone: someone who reads only it gets the result.
- One idea per post. Keep the source's order of proof.
- Last post: the link or the call to action of the source, nothing new.

## Rules

- Use only numbers, names and links present in the source. Rounding or converting a number counts as inventing it.
- No hashtag, no long or medium dash, no "game changer", no emoji wall (2 emoji at most per post).
- Run `fact-guard` after writing.
