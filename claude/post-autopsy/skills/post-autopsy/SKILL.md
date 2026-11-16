---
name: post-autopsy
description: Measure which hook angles, formats, weekdays and hours go with more impressions in the user's own LinkedIn posts, from an export of their posts, with the number of posts and the median of each group, and never conclude on a group of fewer than 5 posts. Use when the user asks, in any language, what works in their posts, which posts performed or to review their post performance ("analyse mes posts LinkedIn", "qu'est-ce qui marche dans mes posts ?", "which of my LinkedIn posts worked", "audit my post performance").
---

# post-autopsy

The user wants to know what drives impressions in their own posts. Measure it on their history with the script, show the numbers, and recommend only what the numbers support.

## 1. Get the export

- If the user gave a file (CSV, JSON or spreadsheet), use it.
- Otherwise ask for it once, and give the two ways to build it:
  1. **LinkedIn's analytics export.** LinkedIn lets a creator export the analytics of their posts as an .xlsx file. Depending on the version, it may hold the publish date and the impressions of each post but not the text or the hour: the user adds those columns, then saves the sheet as CSV.
  2. **A CSV by hand**, one row per post, with the impressions shown under each post.
- The columns are `date,time,text,impressions,reactions,comments`. `date` and `impressions` are required. Without `text` there is no hook or format analysis; without `time` there is no hour analysis. One row looks like:

  ```csv
  date,time,text,impressions,reactions,comments
  2026-11-12,08:00,"J'ai testé une nouvelle accroche.
  Voici ce que ça a donné.",310,9,4
  ```

- If a connected tool can list the user's posts with their impressions, you may build the CSV from it, read only, once the user says yes.
- For an .xlsx file, ask the user to save it as CSV (UTF-8) from their spreadsheet app, or convert it with a tool that is already installed.
- Never retype, estimate or fill in a number. A post whose impressions are unknown keeps an empty cell: the script excludes it and counts it.

## 2. Run the script once

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/autopsy.py" posts.csv
```

- Exit 0: report with at least one conclusion. Exit 1: report, but nothing can be concluded. Exit 2: input error, the reason is on stderr; fix the file or ask the user, then run again.
- Slash dates are read day first (12/11/2026 is 12 November). For a US export (month first), add `--date-order mdy`.

## 3. Show the report

Print the report as the script wrote it. Do not recompute, round or rephrase its numbers. The report is in French: if the user writes in another language, translate the headings and labels, never the numbers.

## 4. Recommend, at most 3

- Take them only from the section "Ce que les chiffres permettent de dire". Prefer the groups with the most posts: a group of 5 to 9 posts is a lead to test, not a pattern.
- Each recommendation names the group, its n, its median and the overall median exactly as the report prints them, and is phrased as an observation on the user's own history, a correlation and not a cause. Shape: "In your history, your <n> posts that open in first person have a median of <median> impressions, against <overall median> for all your posts. Open your next 5 posts that way and run the analysis again."
- Never conclude on a group marked "échantillon trop petit", however high its median. If the user asks about one, say how many posts it has and that it needs at least 5.
- The tables of the most and least seen posts are examples, not evidence.
- Never promise a number of impressions. Never invent a number: every number you write is in the report.
- On exit 1, say plainly that nothing can be concluded yet, and suggest publishing at least 5 posts in each variant the user wants to compare, then running the analysis again.

Do not edit, publish or schedule any post.
