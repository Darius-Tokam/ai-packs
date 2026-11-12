"""Build the trap repository used to test pr-squad.

Creates a small Django billing app on `main`, then a branch
`feat/discounts` whose goal is "add a percentage discount to invoices".
The branch carries 7 planted defects. Run:

    python build_trap.py /tmp/trap

The fake secret is assembled at runtime so this file never contains
a string that secret scanners or GitHub push protection would flag.
"""
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/trap").resolve()


def write(rel, content):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip())


def git(*args):
    subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True)


def django(*args):
    subprocess.run([sys.executable, "manage.py", *args], cwd=ROOT, check=True,
                   capture_output=True)


# ---------------------------------------------------------------- main branch
if ROOT.exists():
    subprocess.run(["rm", "-rf", str(ROOT)], check=True)
ROOT.mkdir(parents=True)

write("requirements.txt", """
    Django==5.2.8
    requests==2.32.3
""")

write("manage.py", """
    import os, sys
    if __name__ == "__main__":
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "billing.settings")
        from django.core.management import execute_from_command_line
        execute_from_command_line(sys.argv)
""")

write("pytest.ini", """
    [pytest]
    DJANGO_SETTINGS_MODULE = billing.settings
    python_files = test_*.py
""")

write("billing/__init__.py", "")
write("billing/settings.py", """
    import os
    from pathlib import Path

    BASE_DIR = Path(__file__).resolve().parent.parent
    SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only")
    DEBUG = True
    ALLOWED_HOSTS = ["*"]
    INSTALLED_APPS = ["django.contrib.contenttypes", "django.contrib.auth",
                      "django.contrib.admin", "django.contrib.sessions",
                      "django.contrib.messages", "invoices"]
    MIDDLEWARE = ["django.contrib.sessions.middleware.SessionMiddleware",
                  "django.contrib.auth.middleware.AuthenticationMiddleware",
                  "django.contrib.messages.middleware.MessageMiddleware"]
    ROOT_URLCONF = "billing.urls"
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
                             "NAME": os.environ.get("TRAP_DB", BASE_DIR / "db.sqlite3")}}
    TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates",
                  "APP_DIRS": True, "OPTIONS": {"context_processors": [
                      "django.template.context_processors.request",
                      "django.contrib.auth.context_processors.auth",
                      "django.contrib.messages.context_processors.messages"]}}]
    DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
    USE_TZ = True
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
""")

write("billing/urls.py", """
    from django.urls import path
    from invoices import views

    urlpatterns = [path("invoices/", views.invoice_list)]
""")

write("invoices/__init__.py", "")
write("invoices/migrations/__init__.py", "")
write("invoices/apps.py", """
    from django.apps import AppConfig

    class InvoicesConfig(AppConfig):
        name = "invoices"
""")

write("invoices/models.py", """
    from django.db import models


    class Client(models.Model):
        name = models.CharField(max_length=120)

        def __str__(self):
            return self.name


    class Invoice(models.Model):
        client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="invoices")
        created = models.DateTimeField(auto_now_add=True)


    class Line(models.Model):
        invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
        label = models.CharField(max_length=200)
        unit_price_cents = models.PositiveIntegerField()
        qty = models.PositiveIntegerField(default=1)
""")

write("invoices/services.py", """
    def invoice_total(invoice):
        \"\"\"Total of an invoice in cents.\"\"\"
        return sum(line.unit_price_cents * line.qty for line in invoice.lines.all())
""")

write("invoices/views.py", """
    from django.http import JsonResponse

    from .models import Invoice
    from .services import invoice_total


    def invoice_list(request):
        invoices = Invoice.objects.select_related("client").prefetch_related("lines")
        data = [{"id": inv.id, "client": inv.client.name, "total": invoice_total(inv)}
                for inv in invoices]
        return JsonResponse({"invoices": data})
""")

write("invoices/admin.py", """
    from django.contrib import admin

    from .models import Client, Invoice

    admin.site.register(Client)
    admin.site.register(Invoice)
""")

write("tests/__init__.py", "")
write("tests/test_services.py", """
    import pytest

    from invoices.models import Client, Invoice, Line
    from invoices.services import invoice_total


    @pytest.mark.django_db
    def test_invoice_total_sums_lines():
        inv = Invoice.objects.create(client=Client.objects.create(name="Acme"))
        Line.objects.create(invoice=inv, label="Audit", unit_price_cents=50000, qty=1)
        Line.objects.create(invoice=inv, label="Hosting", unit_price_cents=2500, qty=2)
        assert invoice_total(inv) == 55000
""")

write(".gitignore", "db.sqlite3\n__pycache__/\n*.pyc\n")

django("makemigrations", "invoices")
git("init", "-q", "-b", "main")
git("config", "user.email", "trap@example.com")
git("config", "user.name", "Trap")
git("add", "-A")
git("commit", "-q", "-m", "Billing app: clients, invoices, lines")

# ------------------------------------------------- feature branch, 7 defects
git("checkout", "-q", "-b", "feat/discounts")

# D6: a dependency pinned to a version with a known CVE.
write("requirements.txt", """
    Django==5.2.8
    requests==2.32.3
    PyYAML==5.3.1
""")

# D1: a live-looking Stripe key hardcoded in settings.
fake_key = "sk_" + "live_" + "51Hx" + "Q8vT3mRkLw9ZpN2cYb7eJd"
settings = (ROOT / "billing/settings.py").read_text()
settings = settings.replace(
    'STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")',
    f'STRIPE_SECRET_KEY = "{fake_key}"  # TODO move to env',
)
(ROOT / "billing/settings.py").write_text(settings)

# D5: NOT NULL column added without default on a table that already has rows.
models = (ROOT / "invoices/models.py").read_text()
models = models.replace(
    "    created = models.DateTimeField(auto_now_add=True)\n",
    "    created = models.DateTimeField(auto_now_add=True)\n"
    "    discount_percent = models.IntegerField()\n",
)
(ROOT / "invoices/models.py").write_text(models)
write("invoices/migrations/0002_invoice_discount_percent.py", """
    from django.db import migrations, models


    class Migration(migrations.Migration):
        dependencies = [("invoices", "0001_initial")]
        operations = [
            migrations.AddField(
                model_name="invoice",
                name="discount_percent",
                field=models.IntegerField(),
                preserve_default=False,
            ),
        ]
""")

# D2 + D3: new function with no test, money as float, no bound on percent.
write("invoices/services.py", """
    def invoice_total(invoice):
        \"\"\"Total of an invoice in cents.\"\"\"
        return sum(line.unit_price_cents * line.qty for line in invoice.lines.all())


    def apply_discount(total_cents, percent):
        \"\"\"Total after a percentage discount.\"\"\"
        return total_cents - total_cents * percent / 100
""")

# D4: new view with an N+1 query pattern.
write("invoices/views.py", """
    from django.http import JsonResponse

    from .models import Invoice
    from .services import apply_discount, invoice_total


    def invoice_list(request):
        invoices = Invoice.objects.select_related("client").prefetch_related("lines")
        data = [{"id": inv.id, "client": inv.client.name, "total": invoice_total(inv)}
                for inv in invoices]
        return JsonResponse({"invoices": data})


    def discounted_invoices(request):
        print("DEBUG headers", dict(request.headers))
        data = []
        for inv in Invoice.objects.all():
            total = invoice_total(inv)
            data.append({"client": inv.client.name,
                         "total": apply_discount(total, inv.discount_percent)})
        return JsonResponse({"invoices": data})
""")
write("billing/urls.py", """
    from django.urls import path
    from invoices import views

    urlpatterns = [path("invoices/", views.invoice_list),
                   path("invoices/discounted/", views.discounted_invoices)]
""")

# D7: change unrelated to the branch goal (admin export of every client).
write("invoices/admin.py", """
    import csv

    from django.contrib import admin
    from django.http import HttpResponse

    from .models import Client, Invoice


    @admin.action(description="Export all clients")
    def export_all_clients(modeladmin, request, queryset):
        response = HttpResponse(content_type="text/csv")
        writer = csv.writer(response)
        for client in Client.objects.all():
            writer.writerow([client.id, client.name])
        return response


    @admin.register(Client)
    class ClientAdmin(admin.ModelAdmin):
        actions = [export_all_clients]


    admin.site.register(Invoice)
""")

git("add", "-A")
git("commit", "-q", "-m", "Add percentage discount to invoices")
print(f"trap repo ready at {ROOT} (branch feat/discounts, base main)")
