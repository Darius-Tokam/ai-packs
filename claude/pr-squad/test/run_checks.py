"""Replay the tool-backed checks of pr-squad on the trap repository.

    python build_trap.py /tmp/trap
    python run_checks.py /tmp/trap

Needs: Django 5.2, pytest, pytest-django, detect-secrets, pip-audit.
Prints the raw output of each measurement. The judgment-based agents
(scope-check, bug-hunt reading, pr-writer) run inside Claude Code with
/pr-squad:ship; their results on this repo are in RESULTS.md.
"""
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

TRAP = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/trap").resolve()
PY = sys.executable


def sh(cmd, env=None, check=False):
    res = subprocess.run(cmd, cwd=TRAP, shell=True, capture_output=True, text=True,
                         env={**os.environ, **(env or {})})
    out = (res.stdout + res.stderr).strip()
    if check and res.returncode:
        raise SystemExit(out)
    return res.returncode, out


def section(title):
    print(f"\n=== {title} ===")


BASE = sh("git merge-base HEAD main", check=True)[1]
sh("git checkout -q feat/discounts", check=True)

section("secret-scan: detect-secrets on changed files")
files = sh(f"git diff --name-only {BASE}...HEAD")[1].split()
_, out = sh("detect-secrets scan " + " ".join(files))
import json  # noqa: E402
found = json.loads(out)["results"]
for path, hits in found.items():
    for h in hits:
        print(f"{path}:{h['line_number']} {h['type']}")
section("secret-scan: headers sent to stdout")
print(sh(f"git diff -U0 {BASE}...HEAD | grep -n 'headers' || true")[1])

section("dep-audit: pip-audit on requirements.txt")
print(sh("pip-audit -r requirements.txt --progress-spinner off 2>&1 | tail -n 8")[1])
section("dep-audit: is yaml imported?")
print(sh("grep -rn --include=*.py -E '^\\s*(import yaml|from yaml)' . || echo '0 import of yaml'")[1])

section("migration-guard: rehearsal on a database with rows")
db = Path(tempfile.mkdtemp()) / "rehearsal.sqlite3"
env = {"TRAP_DB": str(db)}
sh(f"git checkout -q {BASE}", check=True)
print(sh(f"{PY} manage.py migrate -v 0", env=env)[1] or "base migrate: OK")
sh(f'{PY} manage.py shell -c "from invoices.models import *; '
   f"c=Client.objects.create(name='Acme'); Invoice.objects.create(client=c)\"", env=env, check=True)
sh("git checkout -q feat/discounts", check=True)
code, out = sh(f"{PY} manage.py migrate -v 0", env=env)
print("branch migrate:", "OK" if code == 0 else out.splitlines()[-1])

section("test-gaps: existing suite on the branch")
print(sh(f"{PY} -m pytest -q -p no:cacheprovider 2>&1 | tail -n 3")[1])

section("test-gaps: tests written for apply_discount")
(TRAP / "tests/test_discount.py").write_text(textwrap.dedent("""
    from invoices.services import apply_discount


    def test_ten_percent():
        assert apply_discount(10000, 10) == 9000


    def test_zero_percent():
        assert apply_discount(10000, 0) == 10000


    def test_result_is_integer_cents():
        assert isinstance(apply_discount(999, 10), int)


    def test_percent_above_100_never_gives_negative_total():
        assert apply_discount(1000, 150) >= 0
""").lstrip())
print(sh(f"{PY} -m pytest -q -p no:cacheprovider tests/test_discount.py 2>&1 | tail -n 4")[1])

section("bug-hunt: failing inputs")
print(sh(f'{PY} -c "from invoices.services import apply_discount as a; '
         f'print(a(1000, 150), a(999, 10))"')[1])

section("query-check: queries for N invoices on /invoices/discounted/")
(TRAP / "tests/test_queries.py").write_text(textwrap.dedent("""
    import pytest
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from invoices.models import Client, Invoice, Line


    def seed(n):
        c = Client.objects.create(name="Acme")
        for i in range(n):
            inv = Invoice.objects.create(client=c, discount_percent=10)
            Line.objects.create(invoice=inv, label="x", unit_price_cents=1000)


    @pytest.mark.django_db
    @pytest.mark.parametrize("n", [20, 40])
    def test_count(client, n, capsys):
        seed(n)
        with CaptureQueriesContext(connection) as ctx:
            client.get("/invoices/discounted/")
        with capsys.disabled():
            print(f"N={n}: {len(ctx.captured_queries)} queries")
""").lstrip())
print(sh(f"{PY} -m pytest -q -p no:cacheprovider tests/test_queries.py 2>&1 | grep -E 'queries|passed|failed'")[1])

section("query-check: same count after select_related + prefetch_related")
views = (TRAP / "invoices/views.py").read_text()
(TRAP / "invoices/views.py").write_text(views.replace(
    "for inv in Invoice.objects.all():",
    'for inv in Invoice.objects.select_related("client").prefetch_related("lines"):'))
print(sh(f"{PY} -m pytest -q -p no:cacheprovider tests/test_queries.py 2>&1 | grep -E 'queries|passed|failed'")[1])
sh("git checkout -q -- invoices/views.py && rm -f tests/test_queries.py tests/test_discount.py")
