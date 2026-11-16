"""Rebuild the deploy-doctor test cases: 8 failed deployments and 3 healthy ones.

    python build_cases.py /tmp/deploy-cases

Each case is a folder with deploy.log and, for some, the start files of a
small project (Dockerfile, Procfile, railway.toml, settings). expected.json
lists the cause the skill must name. All names are invented; the four first
cases rebuild incidents from the author's notes (see RESULTS.md).
"""
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/deploy-cases")

CASES = {
    "a1-npm-sigterm": {
        "expected": "npm-pid1-sigterm",
        "log": """2026-07-08T10:15:02Z > notes-api@1.0.0 dev:http
2026-07-08T10:15:02Z > tsx packages/app/src/http/index.ts
2026-07-08T10:15:04Z HTTP server listening on 0.0.0.0:8080
2026-07-08T10:16:40Z GET /health 200 3ms
2026-07-08T10:16:49Z Stopping Container
2026-07-08T10:16:49Z npm error path /app
2026-07-08T10:16:49Z npm error command failed
2026-07-08T10:16:49Z npm error signal SIGTERM
2026-07-08T10:16:49Z npm error command sh -c tsx packages/app/src/http/index.ts
""",
        "project": {
            "Dockerfile": 'FROM node:22-slim\nWORKDIR /app\nCOPY . .\nRUN npm ci\nCMD ["npm", "run", "dev:http"]\n',
            "package.json": '{\n  "name": "notes-api",\n  "scripts": {\n    "dev:http": "tsx packages/app/src/http/index.ts"\n  }\n}\n',
        },
    },
    "a2-python-cron": {
        "expected": "python-not-found",
        "log": """2026-06-02T03:00:01Z Starting Container
2026-06-02T03:00:01Z /bin/bash: line 1: python: command not found
2026-06-02T03:00:01Z Stopping Container
""",
        "project": {
            "railway.toml": '[deploy]\ncronSchedule = "0 3 * * *"\nstartCommand = "python manage.py rank_snapshot"\n',
        },
    },
    "a3-missing-allowed-hosts": {
        "expected": "missing-env-var",
        "var": "ALLOWED_HOSTS",
        "log": """2026-06-14T18:02:11Z Starting Container
2026-06-14T18:02:13Z Traceback (most recent call last):
2026-06-14T18:02:13Z   File "/app/config/settings/production.py", line 12, in <module>
2026-06-14T18:02:13Z     ALLOWED_HOSTS = os.environ["ALLOWED_HOSTS"].split(",")
2026-06-14T18:02:13Z   File "/usr/local/lib/python3.12/os.py", line 714, in __getitem__
2026-06-14T18:02:13Z     raise KeyError(key) from None
2026-06-14T18:02:13Z KeyError: 'ALLOWED_HOSTS'
2026-06-14T18:02:14Z Stopping Container
""",
        "project": {
            "Procfile": "web: daphne config.asgi:application --bind 0.0.0.0 --port $PORT\n",
            "config/settings/production.py": 'import os\nfrom .base import *  # noqa\n\nDEBUG = False\nALLOWED_HOSTS = os.environ["ALLOWED_HOSTS"].split(",")\n',
        },
    },
    "a4-debug-page-in-prod": {
        "expected": "dev-settings-in-prod",
        "log": """GET https://shop-web.example.com/admin/missing/ -> 404
<title>Page not found at /admin/missing/</title>
Using the URLconf defined in config.urls, Django tried these URL patterns, in this order:
You're seeing this error because you have DEBUG = True in your Django settings file.
""",
        "project": {
            "Procfile": "web: daphne config.asgi:application --bind 0.0.0.0 --port $PORT\n",
            "manage.py": 'import os\nimport sys\n\nif __name__ == "__main__":\n    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")\n',
            "config/asgi.py": 'import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")\n',
        },
    },
    "b1-localhost-binding": {
        "expected": "port-binding",
        "log": """2026-11-02T14:20:05Z INFO:     Started server process [1]
2026-11-02T14:20:05Z INFO:     Waiting for application startup.
2026-11-02T14:20:05Z INFO:     Application startup complete.
2026-11-02T14:20:05Z INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
2026-11-02T14:21:30Z edge: 502 Application failed to respond
""",
        "project": {
            "main.py": 'import uvicorn\nfrom app import app\n\nif __name__ == "__main__":\n    uvicorn.run(app, host="127.0.0.1", port=8000)\n',
        },
    },
    "b2-node-heap": {
        "expected": "out-of-memory",
        "log": """2026-10-21T09:12:40Z > next build
2026-10-21T09:13:58Z <--- Last few GCs --->
2026-10-21T09:13:58Z FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory
2026-10-21T09:13:58Z Build failed with exit code 134
""",
    },
    "b3-relation-missing": {
        "expected": "migrations-not-applied",
        "log": """2026-10-30T16:44:02Z [INFO] Listening at: http://0.0.0.0:8080 (1)
2026-10-30T16:45:10Z Internal Server Error: /orders/
2026-10-30T16:45:10Z django.db.utils.ProgrammingError: relation "shop_order" does not exist
2026-10-30T16:45:10Z LINE 1: ...shop_order"."total" FROM "shop_order" ORDER BY ...
""",
    },
    "b4-missing-module": {
        "expected": "missing-dependency",
        "var": "whitenoise",
        "log": """2026-09-18T11:02:33Z [INFO] Booting worker with pid: 7
2026-09-18T11:02:34Z   File "/app/config/settings/production.py", line 3, in <module>
2026-09-18T11:02:34Z ModuleNotFoundError: No module named 'whitenoise'
2026-09-18T11:02:34Z [INFO] Worker exiting (pid: 7)
""",
    },
    "c1-healthy-gunicorn": {
        "expected": None,
        "log": """2026-11-10T08:00:01Z [INFO] Starting gunicorn 22.0.0
2026-11-10T08:00:01Z [INFO] Listening at: http://0.0.0.0:8080 (1)
2026-11-10T08:00:01Z [INFO] Booting worker with pid: 7
2026-11-10T08:05:12Z GET /health 200
""",
    },
    "c2-graceful-node": {
        "expected": None,
        "log": """2026-07-08T10:27:01Z Server listening on 0.0.0.0:8080
2026-07-08T10:27:15Z Stopping Container
2026-07-08T10:27:15Z Received SIGTERM, closing the HTTP server
2026-07-08T10:27:15Z Server closed, exit code 0
""",
        "project": {
            "Dockerfile": 'FROM node:22-slim\nWORKDIR /app\nCOPY . .\nRUN npm ci && npm run build:http\nCMD ["node", "packages/app/dist/http/index.js"]\n',
        },
    },
    "c3-graceful-gunicorn": {
        "expected": None,
        "log": """2026-11-11T22:10:00Z [INFO] Handling signal: term
2026-11-11T22:10:00Z [INFO] Worker exiting (pid: 7)
2026-11-11T22:10:01Z [INFO] Shutting down: Master
""",
    },
}

ROOT.mkdir(parents=True, exist_ok=True)
expected = []
for name, case in CASES.items():
    d = ROOT / name
    (d / "project").mkdir(parents=True, exist_ok=True)
    (d / "deploy.log").write_text(case["log"], encoding="utf-8")
    for rel, content in case.get("project", {}).items():
        f = d / "project" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
    expected.append({"case": name, "expected": case["expected"], "var": case.get("var", ""),
                     "has_project": bool(case.get("project"))})
(ROOT / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
print(f"{len(CASES)} cases written to {ROOT}")
