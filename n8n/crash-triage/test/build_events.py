"""Rebuild the crash-triage test: 21 events, from Railway or from any host.

    python build_events.py /tmp/crash-cases

Each case holds the body posted to one of the two webhooks and what the
workflow must do. Railway cases also hold the answer of the Railway GraphQL
API to the deploymentLogs query. The 11 logs are the deploy-doctor cases
(claude/deploy-doctor): four rebuild incidents from the author's notes, with
invented names. 15 cases go through the Railway entry (11 logs and 4 edge
cases), 6 through the generic entry used by any host, CI or script.
Standard library only.
"""
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/crash-cases")

LOGS = {'a1-npm-sigterm': {'expected': 'npm-pid1-sigterm',
                    'var': '',
                    'log': '2026-07-08T10:15:02Z > notes-api@1.0.0 dev:http\n'
                           '2026-07-08T10:15:02Z > tsx packages/app/src/http/index.ts\n'
                           '2026-07-08T10:15:04Z HTTP server listening on 0.0.0.0:8080\n'
                           '2026-07-08T10:16:40Z GET /health 200 3ms\n'
                           '2026-07-08T10:16:49Z Stopping Container\n'
                           '2026-07-08T10:16:49Z npm error path /app\n'
                           '2026-07-08T10:16:49Z npm error command failed\n'
                           '2026-07-08T10:16:49Z npm error signal SIGTERM\n'
                           '2026-07-08T10:16:49Z npm error command sh -c tsx '
                           'packages/app/src/http/index.ts\n'},
 'a2-python-cron': {'expected': 'python-not-found',
                    'var': '',
                    'log': '2026-06-02T03:00:01Z Starting Container\n'
                           '2026-06-02T03:00:01Z /bin/bash: line 1: python: command not found\n'
                           '2026-06-02T03:00:01Z Stopping Container\n'},
 'a3-missing-allowed-hosts': {'expected': 'missing-env-var',
                              'var': 'ALLOWED_HOSTS',
                              'log': '2026-06-14T18:02:11Z Starting Container\n'
                                     '2026-06-14T18:02:13Z Traceback (most recent call last):\n'
                                     '2026-06-14T18:02:13Z   File "/app/config/settings/production.py", line '
                                     '12, in <module>\n'
                                     '2026-06-14T18:02:13Z     ALLOWED_HOSTS = '
                                     'os.environ["ALLOWED_HOSTS"].split(",")\n'
                                     '2026-06-14T18:02:13Z   File "/usr/local/lib/python3.12/os.py", line '
                                     '714, in __getitem__\n'
                                     '2026-06-14T18:02:13Z     raise KeyError(key) from None\n'
                                     "2026-06-14T18:02:13Z KeyError: 'ALLOWED_HOSTS'\n"
                                     '2026-06-14T18:02:14Z Stopping Container\n'},
 'a4-debug-page-in-prod': {'expected': 'dev-settings-in-prod',
                           'var': '',
                           'log': 'GET https://shop-web.example.com/admin/missing/ -> 404\n'
                                  '<title>Page not found at /admin/missing/</title>\n'
                                  'Using the URLconf defined in config.urls, Django tried these URL '
                                  'patterns, in this order:\n'
                                  "You're seeing this error because you have DEBUG = True in your Django "
                                  'settings file.\n'},
 'b1-localhost-binding': {'expected': 'port-binding',
                          'var': '',
                          'log': '2026-11-02T14:20:05Z INFO:     Started server process [1]\n'
                                 '2026-11-02T14:20:05Z INFO:     Waiting for application startup.\n'
                                 '2026-11-02T14:20:05Z INFO:     Application startup complete.\n'
                                 '2026-11-02T14:20:05Z INFO:     Uvicorn running on http://127.0.0.1:8000 '
                                 '(Press CTRL+C to quit)\n'
                                 '2026-11-02T14:21:30Z edge: 502 Application failed to respond\n'},
 'b2-node-heap': {'expected': 'out-of-memory',
                  'var': '',
                  'log': '2026-10-21T09:12:40Z > next build\n'
                         '2026-10-21T09:13:58Z <--- Last few GCs --->\n'
                         '2026-10-21T09:13:58Z FATAL ERROR: Reached heap limit Allocation failed - '
                         'JavaScript heap out of memory\n'
                         '2026-10-21T09:13:58Z Build failed with exit code 134\n'},
 'b3-relation-missing': {'expected': 'migrations-not-applied',
                         'var': '',
                         'log': '2026-10-30T16:44:02Z [INFO] Listening at: http://0.0.0.0:8080 (1)\n'
                                '2026-10-30T16:45:10Z Internal Server Error: /orders/\n'
                                '2026-10-30T16:45:10Z django.db.utils.ProgrammingError: relation '
                                '"shop_order" does not exist\n'
                                '2026-10-30T16:45:10Z LINE 1: ...shop_order"."total" FROM "shop_order" ORDER '
                                'BY ...\n'},
 'b4-missing-module': {'expected': 'missing-dependency',
                       'var': 'whitenoise',
                       'log': '2026-09-18T11:02:33Z [INFO] Booting worker with pid: 7\n'
                              '2026-09-18T11:02:34Z   File "/app/config/settings/production.py", line 3, in '
                              '<module>\n'
                              "2026-09-18T11:02:34Z ModuleNotFoundError: No module named 'whitenoise'\n"
                              '2026-09-18T11:02:34Z [INFO] Worker exiting (pid: 7)\n'},
 'c1-healthy-gunicorn': {'expected': None,
                         'var': '',
                         'log': '2026-11-10T08:00:01Z [INFO] Starting gunicorn 22.0.0\n'
                                '2026-11-10T08:00:01Z [INFO] Listening at: http://0.0.0.0:8080 (1)\n'
                                '2026-11-10T08:00:01Z [INFO] Booting worker with pid: 7\n'
                                '2026-11-10T08:05:12Z GET /health 200\n'},
 'c2-graceful-node': {'expected': None,
                      'var': '',
                      'log': '2026-07-08T10:27:01Z Server listening on 0.0.0.0:8080\n'
                             '2026-07-08T10:27:15Z Stopping Container\n'
                             '2026-07-08T10:27:15Z Received SIGTERM, closing the HTTP server\n'
                             '2026-07-08T10:27:15Z Server closed, exit code 0\n'},
 'c3-graceful-gunicorn': {'expected': None,
                          'var': '',
                          'log': '2026-11-11T22:10:00Z [INFO] Handling signal: term\n'
                                 '2026-11-11T22:10:00Z [INFO] Worker exiting (pid: 7)\n'
                                 '2026-11-11T22:10:01Z [INFO] Shutting down: Master\n'}}


def event(case, status="CRASHED", kind="Deployment.crashed", project="shop", service="web"):
    return {
        "type": kind,
        "details": {"id": f"dep-{case}", "source": "GitHub", "status": status, "branch": "main",
                    "commitHash": "4f1c2a9e0b7d", "commitAuthor": "demo", "commitMessage": "Ship the new checkout"},
        "resource": {
            "workspace": {"id": "ws-demo", "name": "demo"},
            "project": {"id": f"proj-{project}", "name": project},
            "environment": {"id": "env-prod", "name": "production", "isEphemeral": False},
            "service": {"id": f"svc-{service}", "name": service},
            "deployment": {"id": f"dep-{case}"},
        },
        "severity": "WARNING",
        "timestamp": "2026-11-14T10:00:00.000Z",
    }


def graphql(log):
    lines = []
    for raw in log.splitlines():
        stamp, _, rest = raw.partition(" ")
        if stamp[:4].isdigit() and "T" in stamp:
            lines.append({"timestamp": stamp, "message": rest})
        else:
            lines.append({"timestamp": None, "message": raw})
    return {"data": {"deploymentLogs": lines}}


cases = []
for name, c in LOGS.items():
    if c["expected"]:
        want = {"suivre": True, "verdict": "panne", "cause_id": c["expected"], "var": c["var"], "alerte": True}
    elif name == "c1-healthy-gunicorn":
        # A crash was announced, the log shows neither a known failure nor a clean stop:
        # the workflow must say it does not know, never stay silent.
        want = {"suivre": True, "verdict": "inconnue", "cause_id": "", "var": "", "alerte": True}
    else:
        want = {"suivre": True, "verdict": "arret-normal", "cause_id": "", "var": "", "alerte": False}
    cases.append({"case": name, "entry": "railway", "settings": {}, "body": event(name), "logs": graphql(c["log"]),
                  "expected": want})

cases += [
    {"case": "d1-deploy-success", "entry": "railway", "settings": {}, "body": event("d1", status="SUCCESS", kind="Deployment.deployed"),
     "logs": None, "expected": {"suivre": False, "verdict": "", "cause_id": "", "var": "", "alerte": False}},
    {"case": "d2-project-not-followed", "entry": "railway", "settings": {"projets_suivis": "shop, notes-api"},
     "body": event("d2", project="blog"), "logs": None,
     "expected": {"suivre": False, "verdict": "", "cause_id": "", "var": "", "alerte": False}},
    {"case": "d3-empty-log", "entry": "railway", "settings": {}, "body": event("d3", status="FAILED", kind="Deployment.failed"),
     "logs": {"data": {"deploymentLogs": []}},
     "expected": {"suivre": True, "verdict": "inconnue", "cause_id": "", "var": "", "alerte": True}},
    {"case": "d4-token-refused", "entry": "railway", "settings": {}, "body": event("d4"),
     "logs": {"errors": [{"message": "Not Authorized"}]},
     "expected": {"suivre": True, "verdict": "inconnue", "cause_id": "", "var": "", "alerte": True}},
]

# Generic entry: what a deploy script, a CI job or another n8n workflow posts.
cases += [
    {"case": "e1-docker-npm", "entry": "direct", "settings": {},
     "body": {"service": "api", "log": LOGS["a1-npm-sigterm"]["log"]},
     "expected": {"suivre": True, "verdict": "panne", "cause_id": "npm-pid1-sigterm", "var": "", "alerte": True}},
    {"case": "e2-ci-lines-module", "entry": "direct", "settings": {},
     "body": {"service": "worker", "projet": "shop", "lines": LOGS["b4-missing-module"]["log"].splitlines()},
     "expected": {"suivre": True, "verdict": "panne", "cause_id": "missing-dependency", "var": "whitenoise", "alerte": True}},
    {"case": "e3-ci-graceful", "entry": "direct", "settings": {},
     "body": {"service": "web", "log": LOGS["c3-graceful-gunicorn"]["log"]},
     "expected": {"suivre": True, "verdict": "arret-normal", "cause_id": "", "var": "", "alerte": False}},
    {"case": "e4-unknown-cause", "entry": "direct", "settings": {},
     "body": {"service": "web", "log": LOGS["c1-healthy-gunicorn"]["log"]},
     "expected": {"suivre": True, "verdict": "inconnue", "cause_id": "", "var": "", "alerte": True}},
    {"case": "e5-no-log-field", "entry": "direct", "settings": {}, "body": {"service": "web"},
     "expected": {"suivre": True, "verdict": "inconnue", "cause_id": "", "var": "", "alerte": True}},
    {"case": "e6-project-not-followed", "entry": "direct", "settings": {"projets_suivis": "shop"},
     "body": {"service": "web", "projet": "blog", "log": LOGS["a3-missing-allowed-hosts"]["log"]},
     "expected": {"suivre": False, "verdict": "", "cause_id": "", "var": "", "alerte": False}},
]

ROOT.mkdir(parents=True, exist_ok=True)
(ROOT / "cases.json").write_text(json.dumps(cases, indent=1, ensure_ascii=False), encoding="utf-8")
(ROOT / "settings.json").write_text(json.dumps({"mon_adresse": "alex@demo-studio.example", "lignes_de_log": 300,
                                                 "projets_suivis": ""}, indent=1), encoding="utf-8")
print(f"{len(cases)} cases written to {ROOT}")
