"""Build the invoice-chaser test books: a fictional freelance designer, 21 invoices,
one bank export, and 8 planted defects.

    python build_dataset.py /tmp/books

Every client is fictional ("Demo ..." names, example.com addresses). Taxes follow
Quebec rules: TPS 5 % and TVQ 9.975 %, both on the price before taxes
(Revenu Quebec, "Calcul des taxes"). As-of date of the test: 2026-11-12.
"""
import csv
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/books")
OUT.mkdir(parents=True, exist_ok=True)
C = Decimal("0.01")
TPS, TVQ = Decimal("0.05"), Decimal("0.09975")

CLIENTS = {
    "Alpha": "Demo Alpha inc.", "Bravo": "Demo Bravo", "Charlie": "Demo Charlie",
    "Delta": "Demo Delta", "Echo": "Demo Echo inc.", "Foxtrot": "Demo Foxtrot", "Golf": "Demo Golf",
}

# number, client key, issue date, due date ("" = missing), subtotal, status in the books
ROWS = [
    ("F-2026-001", "Alpha", "2026-05-04", "2026-06-03", "1200", "paid"),
    ("F-2026-002", "Bravo", "2026-05-12", "2026-06-11", "800", "paid"),
    ("F-2026-003", "Charlie", "2026-05-20", "2026-06-19", "2500", "paid"),
    ("F-2026-004", "Delta", "2026-06-02", "2026-07-02", "1800", "unpaid"),    # defect 8: 133 days late
    ("F-2026-005", "Alpha", "2026-06-15", "2026-07-15", "950", "paid"),
    ("F-2026-006", "Echo", "2026-06-28", "2026-07-28", "600", "paid"),
    ("F-2026-007", "Bravo", "2026-07-06", "2026-08-05", "1400", "unpaid"),    # defect 1: paid, books say unpaid
    ("F-2026-008", "Foxtrot", "2026-07-20", "2026-08-19", "700", "unpaid"),
    ("F-2026-009", "Charlie", "2026-08-03", "2026-09-02", "3000", "paid"),
    ("F-2026-010", "Golf", "2026-08-14", "2026-09-13", "1000", "unpaid"),     # defect 2: partial payment
    ("F-2026-011", "Delta", "2026-08-25", "2026-09-24", "450", "unpaid"),
    ("F-2026-012", "Echo", "2026-09-01", "2026-10-01", "1250", "unpaid"),     # defect 3: paid without reference
    ("F-2026-013", "Alpha", "2026-09-10", "", "2200", "unpaid"),              # defect 7: no due date
    # F-2026-014 never appears                                                # defect 5: gap in numbering
    ("F-2026-015", "Foxtrot", "2026-09-22", "2026-10-22", "900", "unpaid"),
    ("F-2026-016", "Bravo", "2026-09-30", "2026-10-30", "1600", "unpaid"),    # defect 6: TVQ at 9.5 %
    ("F-2026-017", "Golf", "2026-10-05", "2026-11-04", "500", "unpaid"),
    ("F-2026-018", "Golf", "2026-10-05", "2026-11-04", "500", "unpaid"),      # defect 4: duplicate of 017
    ("F-2026-019", "Charlie", "2026-10-15", "2026-11-14", "1750", "unpaid"),
    ("F-2026-020", "Delta", "2026-10-28", "2026-11-27", "2100", "unpaid"),
    ("F-2026-021", "Echo", "2026-11-03", "2026-12-03", "650", "unpaid"),
    ("F-2026-022", "Alpha", "2026-11-09", "2026-12-09", "1300", "unpaid"),
]


def r(x):
    return x.quantize(C, ROUND_HALF_UP)


totals = {}
with open(OUT / "invoices.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["number", "client", "client_email", "issue_date", "due_date", "subtotal", "tax1", "tax2", "total", "status"])
    for num, key, issued, due, sub, status in ROWS:
        s = Decimal(sub)
        tps = r(s * TPS)
        tvq = r(s * (Decimal("0.095") if num == "F-2026-016" else TVQ))
        total = s + tps + tvq
        totals[num] = total
        w.writerow([num, CLIENTS[key], f"facturation@{key.lower()}.example.com", issued, due,
                    f"{s:.2f}", f"{tps:.2f}", f"{tvq:.2f}", f"{total:.2f}", status])

DEPOSITS = [
    ("2026-06-01", totals["F-2026-001"], "Virement Demo Alpha F-2026-001"),
    ("2026-06-10", totals["F-2026-002"], "Interac F-2026-002 Demo Bravo"),
    ("2026-06-25", totals["F-2026-003"], "Paiement facture F-2026-003"),
    ("2026-07-14", totals["F-2026-005"], "Virement Demo Alpha F-2026-005"),
    ("2026-07-30", totals["F-2026-006"], "Demo Echo F-2026-006"),
    ("2026-08-04", totals["F-2026-007"], "Virement Demo Bravo F-2026-007"),       # defect 1
    ("2026-09-01", totals["F-2026-009"], "Paiement F-2026-009"),
    ("2026-09-20", Decimal("600.00"), "Demo Golf acompte F-2026-010"),            # defect 2
    ("2026-10-03", totals["F-2026-012"], "DEMO ECHO INC PAIEMENT"),               # defect 3
    ("2026-10-31", Decimal("0.42"), "Interets compte"),
]
with open(OUT / "bank.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["date", "amount", "memo"])
    for d, amt, memo in DEPOSITS:
        w.writerow([d, f"{amt:.2f}", memo])
    w.writerow(["2026-10-15", "-89.00", "Abonnement logiciel"])

EXPECTED = [
    {"id": 1, "defect": "F-2026-007 payee mais marquee impayee", "agent": "bank-match", "invoice": "F-2026-007", "severity": "FIX"},
    {"id": 2, "defect": "F-2026-010 payee en partie (600 $)", "agent": "bank-match", "invoice": "F-2026-010", "severity": "FIX"},
    {"id": 3, "defect": "F-2026-012 payee sans numero de facture dans le virement", "agent": "bank-match", "invoice": "F-2026-012", "severity": "FIX"},
    {"id": 4, "defect": "F-2026-018 doublon de F-2026-017", "agent": "duplicate-guard", "invoice": "F-2026-018", "severity": "BLOCK"},
    {"id": 5, "defect": "F-2026-014 absente de la numerotation", "agent": "duplicate-guard", "invoice": "F-2026-014", "severity": "FIX"},
    {"id": 6, "defect": "F-2026-016 TVQ calculee a 9,5 %", "agent": "tax-check", "invoice": "F-2026-016", "severity": "BLOCK"},
    {"id": 7, "defect": "F-2026-013 sans date d'echeance", "agent": "aging", "invoice": "F-2026-013", "severity": "FIX"},
    {"id": 8, "defect": "F-2026-004 la plus en retard (133 jours) passe en tete", "agent": "priority", "invoice": "F-2026-004", "severity": "NOTE"},
]
(OUT / "expected.json").write_text(json.dumps(EXPECTED, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote {OUT}/invoices.csv ({len(ROWS)} invoices), bank.csv ({len(DEPOSITS) + 1} lines), expected.json (8 planted defects)")
