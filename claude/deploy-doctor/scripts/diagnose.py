#!/usr/bin/env python3
"""Name the cause of a failed deployment from its logs.

    python3 diagnose.py deploy.log [more.log ...] [--project DIR] [--json]

Reads build or runtime logs (Railway, Render, Fly, Docker, Heroku style),
matches them against known failure signatures, and prints for each one:
the evidence (file:line), the cause, the fix and how to verify it.
With --project, it also reads the start files of the repo (Dockerfile,
Procfile, railway.json, railway.toml, package.json, settings) to back the
cause with the line of code that produces it.

A clean shutdown on SIGTERM (a normal redeploy) is reported as CLEAN, never
as a crash. Standard library only. Exit code 1 when a failure is found.
"""
import argparse
import json
import re
import sys
from pathlib import Path

RULES = [
    {
        "id": "npm-pid1-sigterm",
        "title": "npm is PID 1 and turns a normal redeploy into a crash",
        "any": [r"npm (?:error|ERR!) signal SIGTERM", r"ELIFECYCLE.*SIGTERM", r"(?:yarn|pnpm).*(?:SIGTERM|exit code 143)"],
        "cause": "The container starts through npm (or yarn, pnpm). On each redeploy the host sends SIGTERM; npm reports it as a failure and exits non-zero, so the host announces a crash although the app stopped normally.",
        "fix": "Start the server with node directly (Dockerfile: CMD [\"node\", \"dist/server.js\"]) and handle SIGTERM: close the server, then exit with code 0.",
        "verify": "Redeploy twice: the old container's log ends without 'npm error', and no 'Deployment crashed' alert arrives.",
        "project": [(r"(?:CMD|ENTRYPOINT|startCommand|web:|\"start\").*(?:\bnpm[\"',\s]+(?:run|start)\b|\byarn[\"',\s]|\bpnpm[\"',\s])", "start goes through a package manager")],
    },
    {
        "id": "python-not-found",
        "title": "the start or cron command calls python, the image only has python3",
        "any": [r"\bpython: command not found", r"/bin/(?:ba)?sh: \d+: python: not found", r"exec: \"python\": executable file not found"],
        "cause": "The command calls 'python' but the image only ships 'python3'. The service or the cron dies before running any code.",
        "fix": "Call python3 in the start or cron command (or install the python-is-python3 package in the image).",
        "verify": "Run the cron once by hand on the host: it prints its own output, not 'command not found'.",
        "project": [(r"(?:^|[\s\"'=:])python\s+(?!3)\S", "command calls python, not python3")],
    },
    {
        "id": "missing-env-var",
        "title": "a required environment variable is missing on the host",
        "any": [r"KeyError: '([A-Z][A-Z0-9_]{2,})'", r"ImproperlyConfigured: Set the ([A-Z][A-Z0-9_]+) environment variable", r"[Mm]issing (?:required )?environment variable:? ['\"]?([A-Z][A-Z0-9_]+)"],
        "cause": "The code reads {var} without a default and the variable is not set on this service, so the app crashes at boot.",
        "fix": "Set {var} on every service that runs this code (web, worker, beat), then redeploy. Do not paste its value in a chat or a log.",
        "verify": "List the service variables and check that {var} is there (value hidden), then redeploy: the boot log reaches the line where the server listens.",
        "project": [(r"os\.environ\[['\"]{var}['\"]\]|process\.env\.{var}\b|env\(['\"]{var}['\"]\)", "code reads {var} without a default")],
    },
    {
        "id": "dev-settings-in-prod",
        "title": "production runs with development settings",
        "any": [r"you have DEBUG = True in your Django settings", r"Watching for file changes with StatReloader", r"Starting development server at"],
        "cause": "The deployed app runs development settings (DEBUG on, often a throwaway SQLite base) because the settings module is chosen by an environment variable that is not set on the host.",
        "fix": "Set DJANGO_SETTINGS_MODULE to the production module on every service, or put it in the start command. Set ALLOWED_HOSTS first: production settings that read it without a default crash at boot.",
        "verify": "Request a missing page: a plain 404, not the debug page; and the Strict-Transport-Security header is present if production sets it.",
        "project": [(r"setdefault\(\s*['\"]DJANGO_SETTINGS_MODULE['\"]\s*,\s*['\"][\w.]*(?:dev|development|local)['\"]", "settings default to a development module")],
    },
    {
        "id": "port-binding",
        "title": "the server listens on localhost, the proxy cannot reach it",
        "any": [r"(?:[Ll]istening|running|Running) (?:on|at):? (?:https?://)?(?:127\.0\.0\.1|localhost)(?::\d+)?", r"Listening at: https?://(?:127\.0\.0\.1|localhost)"],
        "cause": "The server binds to localhost inside the container. The platform proxy cannot reach it, so every request ends in a 502 'Application failed to respond'.",
        "fix": "Bind to host 0.0.0.0 and to the port given in the PORT environment variable (uvicorn --host 0.0.0.0 --port $PORT; Express app.listen(process.env.PORT, '0.0.0.0')).",
        "verify": "After redeploy, the boot log shows 0.0.0.0 and the PORT value, and the public URL answers.",
        "project": [(r"(?:listen|run|bind)\(?.*(?:127\.0\.0\.1|['\"]localhost['\"])", "server binds to localhost")],
    },
    {
        "id": "out-of-memory",
        "title": "the process ran out of memory",
        "any": [r"JavaScript heap out of memory", r"Reached heap limit", r"exit(?:ed with)? code:? 137\b", r"OOMKilled", r"\bMemoryError\b", r"^\s*Killed\s*$"],
        "cause": "The process went over its memory limit and was killed (exit code 137 is SIGKILL). The last lines before the kill show what was running.",
        "fix": "Find the peak in the memory metrics, then lower it (fewer workers, smaller batches, NODE_OPTIONS=--max-old-space-size for Node) or raise the service limit.",
        "verify": "Replay the same load after redeploy: the memory curve stays under the limit and no exit code 137 appears.",
        "project": [],
    },
    {
        "id": "migrations-not-applied",
        "title": "the database schema is behind the code",
        "any": [r"relation \"([^\"]+)\" does not exist", r"no such table: (\w+)", r"column \"[^\"]+\" (?:of relation \"[^\"]+\" )?does not exist", r"You have \d+ unapplied migration"],
        "cause": "The code expects a table or column that this database does not have: the migrations were not applied on this environment.",
        "fix": "Run the migrations as part of the deploy (a pre-deploy or release command such as python manage.py migrate), then redeploy.",
        "verify": "python manage.py showmigrations (or your tool's status command) lists no unapplied migration, and the failing request works.",
        "project": [],
    },
    {
        "id": "missing-dependency",
        "title": "a dependency is missing from the build",
        "any": [r"ModuleNotFoundError: No module named '([\w.]+)'", r"Error: Cannot find module '([^']+)'", r"ImportError: No module named ([\w.]+)"],
        "cause": "The code imports {var}, which the build did not install: it is missing from requirements.txt or package.json (or only in devDependencies).",
        "fix": "Add {var} to the dependency file used by the build, commit, redeploy.",
        "verify": "The build log installs {var}, and the boot log passes the import.",
        "project": [],
    },
]

CLEAN_SHUTDOWN = [r"Received SIGTERM", r"SIGTERM received", r"Handling signal: term", r"[Gg]raceful(?:ly)? (?:shutdown|stopping)", r"[Ss]hutting down"]
START_FILES = ["Dockerfile", "Procfile", "railway.json", "railway.toml", "package.json", "nixpacks.toml"]


def read_logs(paths):
    lines = []
    for p in paths:
        text = sys.stdin.read() if p == "-" else Path(p).read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            lines.append((p, n, line))
    return lines


def project_files(root):
    root = Path(root)
    files = [root / f for f in START_FILES if (root / f).is_file()]
    files += [p for p in root.rglob("*.py") if ".venv" not in p.parts and "node_modules" not in p.parts]
    files += [p for p in root.rglob("*.js") if "node_modules" not in p.parts]
    out = []
    for f in files:
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            out.append((str(f.relative_to(root)), n, line))
    return out


def diagnose(log_paths, project=None):
    lines = read_logs(log_paths)
    code = project_files(project) if project else []
    findings = []
    for rule in RULES:
        for path, n, line in lines:
            m = next((re.search(rx, line) for rx in rule["any"] if re.search(rx, line)), None)
            if not m:
                continue
            var = m.group(1) if m.groups() else ""
            fill = lambda s: s.replace("{var}", var)
            f = {
                "id": rule["id"], "title": rule["title"], "var": var,
                "evidence": f"{path}:{n}: {line.strip()[:160]}",
                "cause": fill(rule["cause"]), "fix": fill(rule["fix"]), "verify": fill(rule["verify"]),
                "code": [],
            }
            for rx, label in rule["project"]:
                rx = rx.replace("{var}", re.escape(var)) if var else rx
                for cpath, cn, cline in code:
                    if re.search(rx, cline) and not cline.lstrip().startswith("#"):
                        f["code"].append(f"{cpath}:{cn}: {cline.strip()[:120]} ({fill(label)})")
            findings.append(f)
            break
    shutdown = [] if findings else [f"{p}:{n}: {l.strip()[:160]}" for p, n, l in lines
                                     if any(re.search(rx, l) for rx in CLEAN_SHUTDOWN)]
    return findings, shutdown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--project")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    findings, shutdown = diagnose(a.logs, a.project)
    if a.json:
        print(json.dumps({"findings": findings, "clean_shutdown": shutdown}, indent=2, ensure_ascii=False))
        return 1 if findings else 0
    for i, f in enumerate(findings, 1):
        print(f"## {i}. {f['id']}: {f['title']}\n")
        print(f"- Evidence: `{f['evidence']}`")
        for c in f["code"]:
            print(f"- In the code: `{c}`")
        print(f"- Cause: {f['cause']}\n- Fix: {f['fix']}\n- Verify: {f['verify']}\n")
    if findings:
        print("DEPLOY VERDICT: " + " + ".join(f["id"] for f in findings))
        return 1
    if shutdown:
        print("Clean shutdown on SIGTERM, not a crash:")
        for s in shutdown[:3]:
            print(f"- `{s}`")
    print("DEPLOY VERDICT: CLEAN (no failure signature)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
