---
name: leak-scan
description: Find the API keys, tokens, presigned URLs, OAuth secrets, auth headers and client email addresses exposed in the user's logs, grouped by distinct secret with a masked excerpt, the cause and the fix, then propose a log filter that masks them from now on and remind to rotate. Use whenever the user wants to know if their logs, production logs or a log file expose a secret or personal data, in any language ("cherche les clés qui fuient dans mes logs", "est-ce que mes logs exposent un secret ?", "scan my logs for leaked API keys", "did my logs leak a token?").
---

# leak-scan

The user wants to know whether their logs expose a secret. Scan them locally with the script, report each leak without ever repeating a secret, propose the filter for their stack, and remind them to rotate.

## Rules that never bend

- Never print a full secret, token, signed URL or email address back to the user, not even to confirm it. Quote only the masked excerpt from the report (first 4 characters and the length). When you show a log line, show the masked line from the report, not the raw one.
- Never send the logs anywhere: no upload, no paste service, no web search with a log line, no other tool that leaves the machine. The scan runs locally.
- Do not rotate a key, change a variable, edit code or write the filter file without an explicit yes.
- Keep fetched logs out of the repository (a temp file), never commit them, and offer to delete them at the end.

## What the script finds

Five forms, on each line:

1. A secret in clear: a URL query parameter or a named field (`key`, `api_key`, `apikey`, `token`, `access_token`, `client_secret`, `password`, `secret`, and names ending with them such as `GEMINI_API_KEY` or `DB_PASSWORD`), or a known key shape anywhere in a line (Google `AIza` + 35, Google OAuth `ya29.`, Stripe `sk_live_`/`rk_live_`, `sk-`, GitHub `ghp_`/`github_pat_`, GitLab `glpat-`, AWS `AKIA`/`ASIA` + 16, Slack `xoxb-`/`xoxp-`, Hugging Face `hf_`, SendGrid `SG.`, JWT), or the password of a connection URL (`postgres://user:password@host`).
2. A presigned URL logged with its signature: `X-Amz-Signature=`, `X-Goog-Signature=`, Azure SAS `sig=` with `sv=`, `se=` or `sp=`, `Signature=` with `Expires=` or `Key-Pair-Id=`.
3. OAuth secrets in a URL whose path contains oauth, callback, redirect, authorize, auth, token, signin or login: `code`, `access_token`, `id_token`, `refresh_token`, `client_secret`.
4. An auth header copied into the log: `Authorization: Bearer|Basic|Token ...`, `x-api-key:`, `x-goog-api-key:`, `api-key:`, `x-auth-token:`, `private-token:`, and session cookies (`Cookie:` or `Set-Cookie:` with a name containing sess, sid, auth, token, jwt or remember).
5. A client email address (personal data).

A durable secret (an API key, a client secret, a password) is one leak however many lines repeat it, with the count, first and last line. Per-request values are grouped by where they leak: presigned URLs by the key or account that signed them, OAuth tokens and codes by endpoint, Bearer tokens and session cookies by header. A value that starts like a known key, is shorter than it and ends the line (or stops before `...`, `[truncated]`) is a key cut by a truncating handler: "fuite partielle". The report shows the first 4 characters and the length (a quarter of the value under 16 characters).

## What the script never flags

- Parameters that only look like secrets: `sort_key=created_at`, `?page=2&per_page=50`, `token_count=1532`, `max_tokens=2048`, `next_page_token=` and other pagination, counter or CSRF tokens, a `csrftoken` cookie.
- A bare `key=` without a random-looking part (8 or more characters mixing letters and digits): `key=build-cache-v3-linux`, `key=uploads/a.png`, `key=session:42`.
- `code=` outside an OAuth path (promo code, HTTP status), and codes under 10 characters or all digits.
- Git SHAs, UUID request ids, sha256 hashes, ETags: no rule targets bare hex.
- An empty value (`key=`), a value already masked (`[REDACTED]`, `***`, `****abcd`, `[Filtered]`), a template or placeholder (`{api_key}`, `${TOKEN}`, `<token>`, `YOUR_TOKEN`, `null`, `password`), a value too short to be a secret (under 8 characters; 4 for a password, 10 for an OAuth code, 16 for a signature, 20 for a bare `key`), a named value with no digit unless it has 16 characters or more in both cases (`token=expired_session_retry`).
- The word password in a sentence without a value ("password reset email sent").
- Emails on reserved or test domains (`example.com`, `example.org`, `example.net`, `.test`, `.invalid`, `.example`, `.localhost`, `.local`, `.internal`), no-reply senders (`no-reply@`, `noreply@`, `do-not-reply@`, `mailer-daemon@`, `postmaster@`, `bounce@`), Google service accounts, `git@`, and file names or systemd units that look like addresses (`logo@2x.png`, `getty@tty1.service`).

Any other email address is flagged, whether it belongs to a client, a supplier or a package maintainer: say which ones look like client data.

## 1. Get the logs

- If the user gave a file or pasted logs, use them (save pasted logs to a temp file as given).
- Otherwise read them with the platform CLI if it is installed and logged in: Railway `railway logs`, Fly `fly logs`, Heroku `heroku logs -n 1500`, Docker `docker logs <container>`, Kubernetes `kubectl logs <pod>`, Render or Vercel with their CLI. Check `--help` for the options of the installed version (deployment, build log, number of lines). A command that streams must be stopped: `timeout 30 railway logs > "$LOG"`. A connected MCP server of the host (a logs tool) works too.
- If nothing works, ask once: paste the logs or point to an exported file. More history is better, since a leak can be weeks old; take application and access logs.

```bash
LOG="$(mktemp -t leak-scan.XXXXXX).log"
```

## 2. Run the script once

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/leak_scan.py" "$LOG"
```

Several files can be given at once, or the log on stdin (`railway logs | python3 .../leak_scan.py`). Exit code 0: no leak, 1: leaks found, 2: bad input (missing or binary file, no input). Add `--json` if you need the line numbers of every occurrence.

## 3. Report

Start with the count of distinct leaks, then for each finding, in the report's order:

1. What leaks (form, kind, masked excerpt), how many lines, first and last line. Say "fuite partielle" / "partial leak" when the report does: a key cut by the log handler is still a leak, treat it as complete.
2. The cause, in the user's language. Then find it in the user's code if the repo is open: search for what produces the line (`?key=`, `raise_for_status`, `logger.exception`, `response.url`, `req.headers`, the logger name of the line) and cite `file:line` after opening the file.
3. The fix, as a diff or the exact change, adapted to their code. Do not apply it without a yes.
4. The rotation step from the report.

End with one line: `LEAK VERDICT: <n> leak(s), rotate <what>` or `LEAK VERDICT: CLEAN`.

## 4. Propose the filter for their stack

The filter masks the same forms as the scan, before each line is written. Pick by the files of the repo:

- Python (`requirements.txt`, `pyproject.toml`, `manage.py`): `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/leak_scan.py" --filter python > <package>/leak_filter.py`, then put `RedactSecretsFilter` on every handler. Django: `LOGGING["filters"] = {"redact": {"()": "<package>.leak_filter.RedactSecretsFilter"}}` and `"filters": ["redact"]` on each handler. A filter on a logger does not see its child loggers: put it on the handlers. The gunicorn or uvicorn access log has its own handlers.
- Node (`package.json`): `--filter node > redact.js`, then `require('./redact').install()` at the top of the entry file, or the pino destination shown at the top of the file.
- Other stacks: show the rules of the Python filter and translate them; say that this translation is untested.

After the user installs it, verify it on their real logging setup: log a fake key in a URL inside an exception (`logger.exception` for Python) and check that the output shows `key=[REDACTED]`. A formatter that formats the exception itself (some JSON formatters) can bypass the filter: this check catches it.

To share a log without its secrets: `--redact <copy>` writes a masked copy.

## 5. Rotate

Always end with it: every key, client secret or password found must be renewed (rotation) where it is issued (Google Cloud console for `AIza` keys, the provider console for an OAuth `client_secret`, the database for a password). The fix stops the leak, it does not undo what is already in the logs. For tokens of users, revoke them and close the sessions. For presigned URLs, renew the signing key if the objects are sensitive, otherwise they expire. For client emails, purge the lines or shorten the log retention if the platform allows it.

## When the script finds nothing

Say CLEAN, with the number of lines read, and what the scan does not see: key formats outside its list without a recognizable parameter name, encoded secrets (base64, double URL encoding), a secret split over several lines, webhook URLs whose secret is in the path. Never claim the logs are safe in absolute terms.
