---
name: pr-writer
description: Write the pull request title, description and squash-commit message from the real diff and the other review verdicts. Use when the user is about to open a PR, or at the end of /ship.
---

# pr-writer

Write from the diff, never from the branch name alone. A reviewer should understand the change without opening the files.

## 1. Inputs

```bash
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)
git log --format='%s%n%b' "$BASE"..HEAD
git diff --stat "$BASE"...HEAD
git diff "$BASE"...HEAD
```

If the other pr-squad agents ran in this session, use their verdict lines.

## 2. Title

Conventional Commits: `type(scope): what changes`, 72 characters max, imperative, no period. Types: feat, fix, refactor, perf, test, docs, chore, ci.

## 3. Body

```markdown
## Why
One or two sentences: the problem or the request this answers.

## What changes
- One bullet per behavior change, in the reader's words, with the file in backticks.

## How to test
1. Exact commands or clicks, with the expected result.

## Risks and follow-ups
- Migrations, config, new env vars, anything the deployer must do.
- Every BLOCK or FIX still open from the other agents, unresolved, stated plainly.
```

Never write "tested" or "safe" if a verdict above says otherwise. If a BLOCK is open, put `DO NOT MERGE` as the first line of the body.

## 4. Commit message

The title, a blank line, then the "What changes" bullets as plain text.

## 5. Output

Print the title, the body and the commit message in three fenced blocks, ready to paste or to pass to `gh pr create --title ... --body-file -`. Do not open the PR yourself unless the user asks.
