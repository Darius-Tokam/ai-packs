---
name: fact-guard
description: Check recycled formats with a script - platform limits (X 280, Threads 500 bytes, Bluesky 300, Instagram 2 200), pack length rules, invented numbers, foreign links, dashes, hashtags and repeated opening lines - then rewrite what fails. Use after writing any recycled format, before the creator posts it.
---

# fact-guard

## 1. Run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_formats.py" --source source.md --dir recycled/ --allow <link to promote>
```

If `CLAUDE_PLUGIN_ROOT` is empty, the script is at `../../scripts/check_formats.py` from this skill's base directory. Save the source post as `source.md` first if it was pasted.

## 2. What it checks

| Format | Limit | Origin |
|---|---|---|
| x-post, x-thread | 280 characters per post, URL = 23 | X, free accounts |
| threads | 500 UTF-8 bytes | Threads (accents count double) |
| bluesky | 300 characters | Bluesky |
| instagram | 2 200 characters, 5 hashtags | Instagram limit, pack rule for hashtags |
| carousel | 5 to 10 slides, 30 words each | pack rule |
| video-script | 55 to 90 spoken words | pack rule, about 30 s |
| newsletter | subject 60 characters, body 80 to 250 words | pack rule |
| quote-card | 20 words | pack rule |
| story | 3 to 5 screens, 15 words each | pack rule |

On every format: each number must exist in the source, each URL must be in the source or allowed, no long or medium dash, no hashtag outside Instagram, no two formats opening with the same line.

## 3. Fix

For each FAIL, rewrite only the failing format, keeping what passed, and rerun until `GUARD VERDICT: 10/10 formats PASS`. Never fix an invented number by adding it to the source: remove it from the format.

## 4. Report

Paste the table the script prints, then the verdict line.
