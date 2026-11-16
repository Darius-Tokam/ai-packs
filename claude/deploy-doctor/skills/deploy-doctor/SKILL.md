---
name: deploy-doctor
description: Name the cause of a failed or crashed deployment from its logs, back it with the line of code that produces it, and give the fix and how to verify it. Use whenever the user says a deploy, build, cron or container failed, crashed, keeps restarting, returns 502, or sent a "Deployment crashed" alert, in any language ("mon déploiement Railway a planté", "pourquoi mon build échoue ?", "j'ai reçu un mail deployment crashed", "mon cron ne tourne plus", "my Railway deploy crashed", "why does my app return 502 after deploy?").
---

# deploy-doctor

The user has a deployment that failed, or an alert that says it did. Find the cause in the logs, prove it, and stop at a proposed fix.

## 1. Get the logs

- If the user pasted logs or an error page, save them to `deploy.log` as given.
- Otherwise read them with the platform CLI if it is installed and logged in (for Railway: `railway logs`; check `railway logs --help` for the build log). Take the failing deployment, not the current one. If no CLI works, ask the user to paste the end of the build or deploy log, once.
- Never print the value of an environment variable or a secret found in the logs: mask it.

## 2. Run the script once

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/diagnose.py" deploy.log --project .
```

`--project .` lets the script read the start files of the repo (Dockerfile, Procfile, railway.json, railway.toml, package.json, settings) and cite the line that causes the failure.

## 3. Report

For each finding of the script, in its order:

1. The cause in one sentence, in the user's language.
2. The evidence: the log line and, when there is one, the line of code (`file:line`). Open that file and confirm it before you report.
3. The fix as a diff or the exact setting to change. Do not apply it, do not change a variable, do not redeploy without an explicit yes.
4. How to verify, copied from the script.

Then one final line: `DEPLOY VERDICT: <cause ids>` or `DEPLOY VERDICT: CLEAN`.

## 4. When the script finds nothing

- `CLEAN` with a SIGTERM line: say it plainly. A clean stop on SIGTERM is a normal redeploy, not a crash. Do not invent another cause.
- `CLEAN` with no line at all: the log you have is not the failing one. Ask for the build log or the log of the failed deployment, then run the script again. If it is still CLEAN, read the last 50 lines yourself and say that the cause is outside the known signatures.
