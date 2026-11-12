---
name: secret-scan
description: Find secrets and sensitive data a branch is about to push - API keys, tokens, private keys, passwords, .env files, request headers or personal data written to logs. Use before every push or pull request.
---

# secret-scan

A secret in a diff is a BLOCK, even on a private repo: git history keeps it after you delete the line.

## 1. Diff and added files

```bash
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)
git diff --name-status "$BASE"...HEAD
git diff -U0 "$BASE"...HEAD | grep '^+' | grep -v '^+++'
```

Any added `.env`, `*.pem`, `*.key`, `id_rsa*`, `*.p12`, `credentials*.json` or `service-account*.json` is a BLOCK by itself.

## 2. Run a real scanner when one is installed

Try in this order and keep the first that runs:

```bash
gitleaks detect --log-opts="$BASE..HEAD" --no-banner --redact
detect-secrets scan $(git diff --name-only "$BASE"...HEAD)
trufflehog git file://. --since-commit "$BASE" --only-verified
```

If none is installed, offer `pip install detect-secrets` and continue with step 3 anyway.

## 3. Read the added lines yourself

Scanners miss things. On every added line, look for:

- Provider key shapes: `sk_live_`, `rk_live_`, `sk-` (OpenAI, Anthropic `sk-ant-`), `AKIA`/`ASIA` (AWS), `ghp_`/`github_pat_`, `xox[bap]-` (Slack), `AIza` (Google), `-----BEGIN ... PRIVATE KEY-----`.
- Assignments to names containing `secret`, `token`, `password`, `passwd`, `api_key`, `apikey`, `private` with a literal string value.
- Connection strings with credentials: `postgres://user:pass@`, `mongodb+srv://user:pass@`.
- Sensitive data sent to logs or stdout: `print`/`logger` of `request.headers`, `request.META`, cookies, `Authorization`, full request bodies, emails or card numbers.

## 4. Report

Never print a full secret. Show the first 8 characters, then `…`.

```
BLOCK | billing/settings.py:24 | Stripe live key hardcoded (sk_live_5…) | detect-secrets: Secret Keyword + high-entropy string | move to env var, then ROTATE the key: it is in git history
FIX   | invoices/views.py:15   | request headers printed (Authorization, cookies end up in logs) | read | delete or log an allow-list of headers
```

When a real key reached any commit, say so: removing the line does not remove it from history, the key must be rotated. End with `SECRETS VERDICT: CLEAN` or `SECRETS VERDICT: BLOCK (<n>)`.
