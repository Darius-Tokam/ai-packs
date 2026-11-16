#!/usr/bin/env python3
"""Check a freelance quote against the client's brief before sending it.

    python3 quote_check.py quote.md brief.md [--tax TPS=5 --tax TVQ=9.975] [--json]

The quote is a markdown table (item, hours, rate, amount) followed by total
lines (subtotal, one line per tax, total). The brief is the client's text.

Checks, in order:
  math      each line (hours x rate = amount), the subtotal, each tax, the total
  missing   a feature the brief asks for that no quote line covers
  hidden    a quoted feature whose hidden work the brief hints at (time zones,
            cancellations, roles...) while the quote line does not mention it
For lines with hidden work, prints an hours range using a x1.2 to x2.0 margin.
French and English. Standard library only. Exit code 1 when something is found.
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Feature families: how the brief and the quote name them, and the work they hide.
# hidden: (label, signal in the brief, words that show the quote line covers it)
FAMILIES = [
    {"id": "booking", "label": "réservation / booking",
     "rx": r"r[ée]serv(?:ation|er|ent|ez|e)s?\b|prise de rendez-vous|rendez-vous en ligne|\bbooking\b|\bbook (?:a|their) (?:session|class|slot)",
     "hidden": [
         ("fuseaux horaires", r"fuseaux?|time ?zones?|international|plusieurs pays|\bau Qu[ée]bec et en France|en France et au Qu[ée]bec|\bin (?:Canada|the US) and (?:in )?(?:France|Europe)|abroad|[àa] l'[ée]tranger",
          r"fuseau|time ?zone"),
         ("annulation et report", r"annul|report(?:er)?\b|d[ée]placer (?:une|sa|leur) s[ée]ance|cancel|reschedul",
          r"annul|report|cancel|reschedul"),
     ]},
    {"id": "payment", "label": "paiement en ligne / payment",
     "rx": r"paiement|payer en ligne|payent en ligne|\bstripe\b|carte de cr[ée]dit|\bcheckout\b|\bpayments?\b|\bpay online\b",
     "hidden": [
         ("remboursements", r"rembours|refund", r"rembours|refund"),
         ("abonnements", r"abonnement|mensuel|subscription|monthly plan", r"abonnement|subscription"),
     ]},
    {"id": "accounts", "label": "comptes et connexion / accounts",
     "rx": r"\bcomptes?\b|connexion|inscription|s'inscrire|espace (?:client|membre)|\blogin\b|sign ?up|user accounts?",
     "hidden": [
         ("rôles et accès séparés", r"r[ôo]les?|leur propre (?:acc[èe]s|horaire|espace)|son propre (?:acc[èe]s|horaire|espace)|permissions?|own (?:access|schedule|login)",
          r"r[ôo]le|permission|acc[èe]s s[ée]par|propre acc[èe]s"),
     ]},
    {"id": "admin", "label": "tableau de bord / admin",
     "rx": r"tableau de bord|\badmin|back-?office|dashboard|gestion des (?:r[ée]servations|clients|commandes)"},
    {"id": "multilingual", "label": "plusieurs langues / languages",
     "rx": r"multilingue|bilingue|en fran[çc]ais et en anglais|fran[çc]ais et anglais|anglais et fran[çc]ais|traduction|\bbilingual\b|French and English|English and French|translation"},
    {"id": "notifications", "label": "courriels et notifications automatiques",
     "rx": r"notifications?|courriels? (?:automatiques?|de (?:rappel|confirmation))|e-?mails? (?:automatiques?|de (?:rappel|confirmation))|\bSMS\b|reminder e-?mails?|confirmation e-?mails?|rappels? (?:par courriel|automatiques?)"},
    {"id": "import", "label": "reprise des données / import",
     "rx": r"\bimport|reprendre (?:mes|nos|les) (?:donn[ée]es|clients)|fichier excel|\bCSV\b|migrat(?:ion|e) (?:des|our|my) (?:donn[ée]es|data)"},
    {"id": "search", "label": "recherche et filtres",
     "rx": r"recherche|filtres?|\bsearch\b|\bfilters?\b"},
    {"id": "mobile", "label": "application mobile",
     "rx": r"application mobile|app mobile|\biOS\b|\bAndroid\b|mobile app"},
    {"id": "integrations", "label": "intégrations (API, agenda, outils)",
     "rx": r"int[ée]gration|synchronis|Google (?:Agenda|Calendar)|\bZoom\b|Mailchimp|QuickBooks|\bAPI\b"},
    {"id": "hosting", "label": "hébergement et mise en ligne",
     "rx": r"h[ée]bergement|mise en ligne|mettre en ligne|nom de domaine|\bhosting\b|\bdeploy|go live|domain name"},
    {"id": "support", "label": "formation, maintenance, garantie",
     "rx": r"formation|maintenance|garantie|\bsupport\b|\btraining\b|warranty"},
]
MARGIN = (1.2, 2.0)
NUM = r"-?\d[\d\s  .,]*"


def num(text):
    """Parse 3 050,00 / 3,050.00 / 3050 / 9,975 into a float."""
    t = re.sub(r"[\s  $€]", "", text)
    if "," in t and "." in t:
        t = t.replace(",", "") if t.rfind(".") > t.rfind(",") else t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    return float(t)


def parse_quote(text):
    lines, totals, header = [], {"taxes": []}, None
    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if header is None:
                header = [c.lower() for c in cells]
                continue
            if set("".join(cells)) <= set("-: "):
                continue
            def col(*names):
                for i, h in enumerate(header):
                    if any(x in h for x in names):
                        return cells[i] if i < len(cells) else ""
                return ""
            item = col("poste", "item", "description", "livrable")
            try:
                hours, rate, amount = num(col("heure", "hour")), num(col("taux", "rate")), num(col("montant", "amount", "total"))
            except ValueError:
                continue
            lines.append({"n": n, "item": item, "hours": hours, "rate": rate, "amount": amount})
            continue
        m = re.match(r"^\**\s*(sous-total|subtotal|total)\s*\**\s*:?\s*\**\s*(" + NUM + r")", s, re.I)
        if m:
            totals["subtotal" if m.group(1).lower() in ("sous-total", "subtotal") else "total"] = (n, num(m.group(2)))
            continue
        m = re.match(r"^\**\s*([A-Za-zÀ-ÿ]{2,6})\s*\(\s*(" + NUM + r")\s*%\s*\)\s*\**\s*:?\s*\**\s*(" + NUM + r")", s)
        if m:
            totals["taxes"].append({"n": n, "name": m.group(1).upper(), "rate": num(m.group(2)), "amount": num(m.group(3))})
    return lines, totals


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip(" -*") for p in parts if p.strip(" -*")]


def check(quote_text, brief_text, taxes=None):
    lines, totals = parse_quote(quote_text)
    quote_items = " \n".join(l["item"] for l in lines)
    quote_all = quote_text
    found = []
    # 1. math
    for l in lines:
        want = round(l["hours"] * l["rate"], 2)
        if abs(want - l["amount"]) > 0.01:
            found.append({"kind": "math", "id": "math-line", "where": f"quote:{l['n']}",
                          "what": f"« {l['item']} » : {l['hours']:g} h x {l['rate']:g} = {want:.2f}, le devis écrit {l['amount']:.2f}"})
    if lines and "subtotal" in totals:
        n, sub = totals["subtotal"]
        s = round(sum(l["amount"] for l in lines), 2)
        if abs(s - sub) > 0.01:
            found.append({"kind": "math", "id": "math-subtotal", "where": f"quote:{n}",
                          "what": f"la somme des lignes donne {s:.2f}, le sous-total écrit {sub:.2f}"})
    base = totals["subtotal"][1] if "subtotal" in totals else round(sum(l["amount"] for l in lines), 2)
    wanted_rates = dict(taxes or {})
    for t in totals["taxes"]:
        rate = wanted_rates.get(t["name"], t["rate"])
        want = round(base * rate / 100, 2)
        if abs(rate - t["rate"]) > 1e-9:
            found.append({"kind": "math", "id": "math-tax-rate", "where": f"quote:{t['n']}",
                          "what": f"{t['name']} écrite à {t['rate']:g} %, le taux donné est {rate:g} %"})
        if abs(want - t["amount"]) > 0.01:
            found.append({"kind": "math", "id": "math-tax", "where": f"quote:{t['n']}",
                          "what": f"{t['name']} à {rate:g} % de {base:.2f} = {want:.2f}, le devis écrit {t['amount']:.2f}"})
    for name in wanted_rates:
        if not any(t["name"] == name for t in totals["taxes"]):
            found.append({"kind": "math", "id": "math-tax-missing", "where": "quote",
                          "what": f"{name} ({wanted_rates[name]:g} %) attendue, aucune ligne dans le devis"})
    if "total" in totals:
        n, tot = totals["total"]
        want = round(base + sum(t["amount"] for t in totals["taxes"]), 2)
        if abs(want - tot) > 0.01:
            found.append({"kind": "math", "id": "math-total", "where": f"quote:{n}",
                          "what": f"sous-total et taxes donnent {want:.2f}, le total écrit {tot:.2f}"})
    # 2. missing and 3. hidden work
    brief_sents = sentences(brief_text)
    risky_hours = 0.0
    risky_lines = set()
    for fam in FAMILIES:
        asked = [s for s in brief_sents if re.search(fam["rx"], s, re.I)]
        if not asked:
            continue
        quoted = [l for l in lines if re.search(fam["rx"], l["item"], re.I)]
        if not quoted:
            found.append({"kind": "missing", "id": f"missing-{fam['id']}", "where": "brief",
                          "what": f"{fam['label']} : demandé (« {asked[0][:110]} »), aucune ligne du devis ne le chiffre"})
            continue
        for label, signal, covered in fam.get("hidden", []):
            hint = [s for s in brief_sents if re.search(signal, s, re.I)]
            if not hint:
                continue
            if any(re.search(covered, l["item"], re.I) for l in quoted) or re.search(covered, quote_all, re.I):
                continue
            l = quoted[0]
            found.append({"kind": "hidden", "id": f"hidden-{fam['id']}-{label.split()[0]}", "where": f"quote:{l['n']}",
                          "what": f"« {l['item']} » ({l['hours']:g} h) : le brief laisse entendre {label} (« {hint[0][:110]} »), la ligne ne le prévoit pas"})
            if l["n"] not in risky_lines:
                risky_lines.add(l["n"])
                risky_hours += l["hours"]
    total_hours = sum(l["hours"] for l in lines)
    rng = None
    if risky_hours:
        rng = (round(total_hours + risky_hours * (MARGIN[0] - 1), 1), round(total_hours + risky_hours * (MARGIN[1] - 1), 1))
    return {"lines": len(lines), "hours": total_hours, "findings": found,
            "risky_hours": risky_hours, "hours_range": rng,
            "unpriced": [f["id"].split("-", 1)[1] for f in found if f["kind"] == "missing"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quote")
    ap.add_argument("brief")
    ap.add_argument("--tax", action="append", default=[], help="NAME=RATE, e.g. TPS=5 or TVA=20")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    taxes = {}
    for t in a.tax:
        k, _, v = t.partition("=")
        taxes[k.strip().upper()] = num(v)
    res = check(Path(a.quote).read_text(encoding="utf-8"), Path(a.brief).read_text(encoding="utf-8"), taxes)
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 1 if res["findings"] else 0
    print(f"{res['lines']} lines, {res['hours']:g} h quoted")
    for kind, title in (("math", "Calculs"), ("missing", "Demandé, pas chiffré"), ("hidden", "Travail caché")):
        items = [f for f in res["findings"] if f["kind"] == kind]
        if items:
            print(f"\n## {title} ({len(items)})")
            for f in items:
                print(f"- [{f['id']}] {f['what']} ({f['where']})")
    if res["hours_range"]:
        lo, hi = res["hours_range"]
        print(f"\nAvec une marge de x{MARGIN[0]:g} à x{MARGIN[1]:g} sur les lignes à travail caché : {lo:g} à {hi:g} h au lieu de {res['hours']:g} h, hors postes non chiffrés.")
    n = len(res["findings"])
    print(f"\nQUOTE VERDICT: {'SEND' if not n else f'FIX FIRST ({n})'}")
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
