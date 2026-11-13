"""invoice-chaser core: reconcile invoices with bank deposits, then plan the reminders.

    python3 chase.py check  --invoices invoices.csv --bank bank.csv [--as-of 2026-11-12] [--terms 30]
                            [--taxes "TPS:5,TVQ:9.975"] [--out chase_out]
    python3 chase.py verify --plan chase_out/plan.json --emails emails/

Standard input files (ledger-import converts any export to them):

    invoices.csv  number,client,client_email,issue_date,due_date,subtotal,tax1,tax2,total,status
    bank.csv      date,amount,memo

status is what your books say: paid, unpaid or partial. Dates are YYYY-MM-DD.
Amounts use a dot as decimal separator. Only the standard library is used.

check writes plan.json, plan.csv and report.md into --out and prints the report.
verify reads drafted reminder emails (one .md file per client, first line
"client: <name>") and flags every invoice number or amount that does not
match the plan. Exit code 1 when verify finds a problem.
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

CENT = Decimal("0.01")
LEVELS = [(45, "L3"), (15, "L2"), (1, "L1")]  # minimum days overdue -> level
LEVEL_NAMES = {"L1": "rappel courtois", "L2": "relance ferme", "L3": "dernier avis"}


def money(s):
    s = (s or "").strip().replace("$", "").replace(" ", "").replace(" ", "")
    return Decimal(s or "0").quantize(CENT, ROUND_HALF_UP)


def fmt(d):
    """1380.5 -> '1 380,50 $' (French Canadian format)."""
    q = f"{d.quantize(CENT):,.2f}"
    return q.replace(",", " ").replace(".", ",") + " $"


def parse_day(s):
    s = (s or "").strip()
    return date.fromisoformat(s) if s else None


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def client_tokens(name):
    """Distinctive words of a client name, used to recognise it in a bank memo."""
    stop = {"inc", "ltee", "ltd", "llc", "sarl", "sas", "the", "les", "and", "et", "demo"}
    return [w for w in re.findall(r"[a-z0-9]+", name.lower()) if len(w) > 2 and w not in stop]


def load(args):
    invoices = []
    with open(args.invoices, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            invoices.append({
                "number": r["number"].strip(), "client": r["client"].strip(),
                "client_email": r.get("client_email", "").strip(),
                "issue_date": parse_day(r["issue_date"]), "due_date": parse_day(r.get("due_date")),
                "subtotal": money(r["subtotal"]), "tax1": money(r.get("tax1")),
                "tax2": money(r.get("tax2")), "total": money(r["total"]),
                "status": r.get("status", "unpaid").strip().lower(),
            })
    deposits = []
    with open(args.bank, newline="", encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f)):
            amt = money(r["amount"])
            if amt > 0:
                deposits.append({"id": i, "date": parse_day(r["date"]), "amount": amt,
                                 "memo": r.get("memo", "").strip(), "used": Decimal("0")})
    return invoices, deposits


def check(args):
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    rates = []
    for part in (args.taxes or "").split(","):
        if part.strip():
            name, pct = part.split(":")
            rates.append((name.strip(), Decimal(pct.strip()) / 100))
    invoices, deposits = load(args)
    findings = []  # (severity, agent, invoice, message)

    def add(sev, agent, inv, msg):
        findings.append({"severity": sev, "agent": agent, "invoice": inv, "message": msg})

    # bank-match: 1) memo cites the invoice number, 2) exact total + client name in memo
    by_number = {i["number"]: i for i in invoices}
    for inv in invoices:
        inv["paid"] = Decimal("0")
        inv["match"] = []
    for dep in deposits:
        cited = [n for n in by_number if norm(n) and norm(n) in norm(dep["memo"])]
        for n in cited:
            inv = by_number[n]
            part = min(dep["amount"] - dep["used"], inv["total"] - inv["paid"])
            if part > 0:
                inv["paid"] += part
                dep["used"] += part
                inv["match"].append(f"{dep['date']} {fmt(part)} ({dep['memo']})")
    for dep in deposits:
        if dep["used"] > 0:
            continue
        memo = dep["memo"].lower()
        cands = [i for i in invoices if i["paid"] == 0 and i["total"] == dep["amount"]
                 and any(t in memo for t in client_tokens(i["client"]))]
        if len(cands) == 1:
            inv = cands[0]
            inv["paid"] = dep["amount"]
            dep["used"] = dep["amount"]
            inv["match"].append(f"{dep['date']} {fmt(dep['amount'])} ({dep['memo']}) [probable: amount + client name]")
            if inv["status"] != "paid":
                add("FIX", "bank-match", inv["number"],
                    f"deposit of {fmt(dep['amount'])} on {dep['date']} has no invoice number but matches "
                    f"amount and client: probably paid, confirm then mark paid")
    for inv in invoices:
        bal = inv["total"] - inv["paid"]
        inv["balance"] = bal
        if inv["status"] != "paid" and inv["paid"] == inv["total"] and not any("probable" in m for m in inv["match"]):
            add("FIX", "bank-match", inv["number"],
                f"marked {inv['status']} in the books but paid in full: {inv['match'][0]}. Do not chase, mark paid")
        elif 0 < inv["paid"] < inv["total"]:
            add("FIX", "bank-match", inv["number"],
                f"partial payment {fmt(inv['paid'])} of {fmt(inv['total'])}: chase the balance {fmt(bal)} only")
        elif inv["status"] == "paid" and inv["paid"] == 0:
            add("NOTE", "bank-match", inv["number"], "marked paid but no deposit found in this bank export")
        if inv["status"] == "paid" and inv["paid"] == 0:
            inv["balance"] = Decimal("0")
    leftovers = [d for d in deposits if d["used"] < d["amount"]]
    for d in leftovers:
        add("NOTE", "bank-match", "-", f"deposit {fmt(d['amount'] - d['used'])} on {d['date']} ({d['memo']}) matches no invoice")

    # tax-check
    for inv in invoices:
        for (name, rate), field in zip(rates, ("tax1", "tax2")):
            expected = (inv["subtotal"] * rate).quantize(CENT, ROUND_HALF_UP)
            if abs(inv[field] - expected) > CENT:
                add("BLOCK", "tax-check", inv["number"],
                    f"{name} is {fmt(inv[field])}, expected {fmt(expected)} ({(rate * 100).normalize()} % of {fmt(inv['subtotal'])}). "
                    f"Fix the invoice before any reminder")
                inv["hold"] = "tax"
        computed = inv["subtotal"] + inv["tax1"] + inv["tax2"]
        if abs(computed - inv["total"]) > CENT:
            add("BLOCK", "tax-check", inv["number"],
                f"total {fmt(inv['total'])} differs from subtotal + taxes {fmt(computed)}")
            inv["hold"] = "total"

    # duplicate-guard: same client, same issue date, same total; numbering gaps
    seen = {}
    for inv in sorted(invoices, key=lambda i: i["number"]):
        key = (norm(inv["client"]), inv["issue_date"], inv["total"])
        if key in seen:
            add("BLOCK", "duplicate-guard", inv["number"],
                f"same client, date and total as {seen[key]}: probable duplicate. Cancel it or confirm it")
            inv["hold"] = "duplicate"
        else:
            seen[key] = inv["number"]
    groups = defaultdict(list)
    for inv in invoices:
        m = re.match(r"^(.*?)(\d+)$", inv["number"])
        if m:
            groups[m.group(1)].append((int(m.group(2)), len(m.group(2))))
    for prefix, nums in groups.items():
        values = sorted(n for n, _ in nums)
        width = max(w for _, w in nums)
        for missing in sorted(set(range(values[0], values[-1] + 1)) - set(values)):
            add("FIX", "duplicate-guard", f"{prefix}{missing:0{width}d}",
                "missing from the sequence: never issued, deleted or forgotten in the export? Check before your tax return")

    # aging
    buckets = {"pas encore due": Decimal(0), "1-30": Decimal(0), "31-60": Decimal(0), "61-90": Decimal(0), "90+": Decimal(0)}
    for inv in invoices:
        if inv["due_date"] is None:
            inv["due_date"] = inv["issue_date"] + timedelta(days=args.terms)
            inv["due_assumed"] = True
            add("FIX", "aging", inv["number"],
                f"no due date: {args.terms}-day terms assumed, due {inv['due_date']}. Put the due date on the invoice")
        inv["days"] = (as_of - inv["due_date"]).days
        if inv["balance"] <= 0 or inv.get("hold") == "duplicate":
            continue
        d = inv["days"]
        b = "pas encore due" if d <= 0 else "1-30" if d <= 30 else "31-60" if d <= 60 else "61-90" if d <= 90 else "90+"
        buckets[b] += inv["balance"]

    # priority + plan
    plan = []
    for inv in invoices:
        if inv["balance"] <= 0:
            continue
        d = inv["days"]
        level = next((lv for lim, lv in LEVELS if d >= lim), None)
        action = "hold" if inv.get("hold") else ("chase" if level else "wait")
        plan.append({
            "number": inv["number"], "client": inv["client"], "client_email": inv["client_email"],
            "due_date": str(inv["due_date"]), "due_assumed": bool(inv.get("due_assumed")),
            "days_overdue": max(d, 0), "total": str(inv["total"]), "paid": str(inv["paid"]),
            "balance": str(inv["balance"]), "level": level if action == "chase" else None,
            "action": action, "hold_reason": inv.get("hold"),
            "score": str((inv["balance"] * max(d, 0)).quantize(CENT)),
        })
    plan.sort(key=lambda p: (p["action"] != "chase", -Decimal(p["score"])))
    chase = [p for p in plan if p["action"] == "chase"]
    if chase:
        top = chase[0]
        add("NOTE", "priority", top["number"],
            f"chase first: {fmt(Decimal(top['balance']))}, {top['days_overdue']} days late ({top['client']})")

    by_client = defaultdict(list)
    for p in chase:
        by_client[p["client"]].append(p)
    emails = []
    for client, items in by_client.items():
        lvl = max(i["level"] for i in items)
        emails.append({"client": client, "to": items[0]["client_email"], "level": lvl,
                       "invoices": [i["number"] for i in items],
                       "amount": str(sum(Decimal(i["balance"]) for i in items))})
    emails.sort(key=lambda e: -Decimal(e["amount"]))

    to_recover = sum((Decimal(p["balance"]) for p in chase), Decimal(0))
    held = sum((Decimal(p["balance"]) for p in plan if p["action"] == "hold"), Decimal(0))
    found_paid = [f for f in findings if f["agent"] == "bank-match" and f["severity"] == "FIX" and "partial" not in f["message"]]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    result = {"as_of": str(as_of), "terms": args.terms, "invoices": len(invoices),
              "to_recover": str(to_recover), "held": str(held),
              "buckets": {k: str(v) for k, v in buckets.items()},
              "findings": findings, "plan": plan, "emails": emails}
    (out / "plan.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(out / "plan.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["number", "client", "due_date", "days_overdue", "balance", "action", "level", "next_step"])
        for p in plan:
            nxt = (f"{LEVEL_NAMES[p['level']]} {as_of}" if p["action"] == "chase" else
                   f"corriger ({p['hold_reason']}) avant relance" if p["action"] == "hold" else
                   f"rappel courtois le {date.fromisoformat(p['due_date']) + timedelta(days=1)}")
            w.writerow([p["number"], p["client"], p["due_date"], p["days_overdue"], p["balance"], p["action"], p["level"] or "", nxt])

    lines = [f"# invoice-chaser report, as of {as_of}", "",
             f"{len(invoices)} invoices, {len(deposits)} deposits.", "", "## Findings", "",
             "| Severity | Agent | Invoice | Finding |", "|---|---|---|---|"]
    order = {"BLOCK": 0, "FIX": 1, "NOTE": 2}
    for f_ in sorted(findings, key=lambda x: (order[x["severity"]], x["agent"], x["invoice"])):
        lines.append(f"| {f_['severity']} | {f_['agent']} | {f_['invoice']} | {f_['message']} |")
    lines += ["", "## Aging of unpaid balances", "", "| Bucket | Amount |", "|---|---|"]
    lines += [f"| {k} | {fmt(v)} |" for k, v in buckets.items()]
    lines += ["", "## Chase plan (highest balance x days first)", "",
              "| Invoice | Client | Days late | Balance | Action |", "|---|---|---|---|---|"]
    for p in plan:
        act = p["level"] + " " + LEVEL_NAMES[p["level"]] if p["action"] == "chase" else p["action"] + (f" ({p['hold_reason']})" if p["hold_reason"] else "")
        lines.append(f"| {p['number']} | {p['client']} | {p['days_overdue']} | {fmt(Decimal(p['balance']))} | {act} |")
    lines += ["", "## Emails to draft (one per client)", "", "| Client | Level | Invoices | Amount |", "|---|---|---|---|"]
    for e in emails:
        lines.append(f"| {e['client']} | {e['level']} | {', '.join(e['invoices'])} | {fmt(Decimal(e['amount']))} |")
    n_block = sum(1 for f_ in findings if f_["severity"] == "BLOCK")
    n_fix = sum(1 for f_ in findings if f_["severity"] == "FIX")
    lines += ["", f"CHASE VERDICT: {fmt(to_recover)} to recover on {len(chase)} invoices, "
              f"{len(emails)} emails, {fmt(held)} on hold ({n_block} BLOCK, {n_fix} FIX)"]
    report = "\n".join(lines) + "\n"
    (out / "report.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


AMOUNT_RE = re.compile(
    r"(?P<fr>\d{1,3}(?:[   ]\d{3})*(?:,\d{2})?)[   ]?\$"
    r"|\$[ ]?(?P<en>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)")


def amounts_in(text):
    vals = []
    for m in AMOUNT_RE.finditer(text):
        if m.group("fr"):
            s = re.sub(r"[   ]", "", m.group("fr")).replace(",", ".")
        else:
            s = m.group("en").replace(",", "")
        vals.append(Decimal(s).quantize(CENT))
    return vals


def verify(args):
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    rows = {p["number"]: p for p in plan["plan"]}
    numbers_re = re.compile("|".join(sorted({re.escape(re.match(r"^(.*?)\d+$", n).group(1)) for n in rows}, key=len, reverse=True)) + r"\d+") if rows else None
    expected = {e["client"]: e for e in plan["emails"]}
    problems, checked = [], 0
    for path in sorted(Path(args.emails).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        checked += 1
        m = re.match(r"client:\s*(.+)", text)
        client = m.group(1).strip() if m else None
        if client not in expected:
            problems.append(f"{path.name}: client {client!r} has no email in the plan")
            continue
        e = expected[client]
        cited = set(numbers_re.findall(text)) if numbers_re else set()
        for n in sorted(cited):
            if n not in rows:
                problems.append(f"{path.name}: invoice {n} is not in the plan (paid, unknown or never issued)")
            elif rows[n]["client"] != client:
                problems.append(f"{path.name}: invoice {n} belongs to {rows[n]['client']}")
            elif rows[n]["action"] == "hold":
                problems.append(f"{path.name}: invoice {n} is on hold ({rows[n]['hold_reason']}), fix it before chasing")
            elif rows[n]["action"] == "wait":
                problems.append(f"{path.name}: invoice {n} is not due yet (due {rows[n]['due_date']}), do not chase it")
        for n in e["invoices"]:
            if n not in cited:
                problems.append(f"{path.name}: invoice {n} is overdue for this client but missing from the email")
        allowed = {Decimal(rows[n]["balance"]) for n in e["invoices"]} | {Decimal(e["amount"])}
        allowed |= {Decimal(rows[n]["total"]) for n in e["invoices"]} | {Decimal(rows[n]["paid"]) for n in e["invoices"]}
        for a in amounts_in(text):
            if a not in allowed:
                problems.append(f"{path.name}: amount {fmt(a)} matches no balance, total or payment of this client")
        if chr(0x2014) in text or chr(0x2013) in text:
            problems.append(f"{path.name}: contains a long or medium dash")
    for p in problems:
        print("PROBLEM", p)
    print(f"VERIFY: {checked} emails checked, {len(problems)} problems")
    return 1 if problems else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--invoices", required=True)
    c.add_argument("--bank", required=True)
    c.add_argument("--as-of")
    c.add_argument("--terms", type=int, default=30)
    c.add_argument("--taxes", default="", help='e.g. "TPS:5,TVQ:9.975" or "VAT:20"')
    c.add_argument("--out", default="chase_out")
    v = sub.add_parser("verify")
    v.add_argument("--plan", required=True)
    v.add_argument("--emails", required=True)
    a = ap.parse_args()
    sys.exit(check(a) if a.cmd == "check" else verify(a))


if __name__ == "__main__":
    main()
