"""Rebuild the relance-radar test mailbox: 27 sent threads, as the Gmail node returns them.

    python build_threads.py /tmp/relance-cases

Writes threads.json (one item per message, like the Gmail node "thread: get"
with simplify on), settings.json (the "Réglages" node) and expected.json.
The shape comes from the author's notes (22 prospecting emails sent from
19 August to 2 September 2026, 0 reply, the oldest batch 15 days old, and a
follow-up once drafted for a prospect he had lost). Every name and address
is invented.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/relance-cases")
ME = "Alex Demo <alex@demo-studio.example>"
FIRST = ["Camille", "Hugo", "Léa", "Samuel", "Inès", "Noah", "Chloé", "Nadia", "Olivier", "Rose",
         "Jules", "Maya", "Théo", "Sarah", "Louis", "Zoé", "Adam", "Emma", "Félix", "Alice",
         "Victor", "Laura", "Paul", "Julie", "Marc", "Anne", "Eric"]
SUBJECTS = ["Votre site : 3 pages qui manquent", "Proposition de refonte", "Devis pour votre boutique en ligne",
            "Audit SEO de votre site", "Automatiser vos prises de rendez-vous"]


def ms(day, hour=14):
    return str(int(datetime(2026, int(day[:2]), int(day[3:]), hour, tzinfo=timezone.utc).timestamp() * 1000))


def person(i):
    return f"{FIRST[i]} Client <{FIRST[i].lower().replace('é', 'e').replace('è', 'e').replace('ï', 'i').replace('ô', 'o')}@client{i:02d}.example>"


messages, expected = [], []


def thread(n, sends, subject, *, reply=None, bounce=None, draft=None, action, reason):
    tid = f"t{n:02d}"
    to = person(n - 1)
    for k, day in enumerate(sends):
        messages.append({"id": f"{tid}-m{k}", "threadId": tid, "internalDate": ms(day), "From": ME, "To": to,
                         "Subject": subject if k == 0 else f"Re: {subject}", "labels": [{"id": "SENT", "name": "SENT"}],
                         "snippet": "..."})
    if reply:
        messages.append({"id": f"{tid}-r", "threadId": tid, "internalDate": ms(reply), "From": to, "To": ME,
                         "Subject": f"Re: {subject}", "labels": [{"id": "INBOX", "name": "INBOX"}], "snippet": "Merci, on en parle"})
    if bounce:
        messages.append({"id": f"{tid}-b", "threadId": tid, "internalDate": ms(bounce, 15),
                         "From": "Mail Delivery Subsystem <mailer-daemon@googlemail.com>", "To": ME,
                         "Subject": "Delivery Status Notification (Failure)", "labels": [{"id": "INBOX", "name": "INBOX"}],
                         "snippet": "Address not found"})
    if draft:
        messages.append({"id": f"{tid}-d", "threadId": tid, "internalDate": ms(draft), "From": ME, "To": to,
                         "Subject": f"Re: {subject}", "labels": [{"id": "DRAFT", "name": "DRAFT"}], "snippet": "Je reviens vers vous"})
    expected.append({"thread": tid, "to": to, "action": action, "reason": reason})


n = 0
# The real shape: 22 emails, 19 Aug to 2 Sep, no reply.
for day, count in (("08-19", 8), ("08-26", 7), ("08-31", 4), ("09-02", 3)):
    for _ in range(count):
        n += 1
        if n == 8:  # the prospect he had lost, on the exclusion list
            thread(n, [day], SUBJECTS[n % 5], action="ignorer", reason="exclusion")
        elif day in ("08-31", "09-02"):
            thread(n, [day], SUBJECTS[n % 5], action="ignorer", reason="recent")
        else:
            thread(n, [day], SUBJECTS[n % 5], action="relancer", reason="relance1")
# Planted on top of the real shape, one per filter.
thread(23, ["08-20"], SUBJECTS[3], reply="08-21", action="ignorer", reason="replied")
thread(24, ["08-19"], SUBJECTS[4], bounce="08-19", action="ignorer", reason="bounce")
thread(25, ["08-10", "08-17", "08-24"], SUBJECTS[0], action="ignorer", reason="max")
thread(26, ["08-12", "08-26"], SUBJECTS[1], action="relancer", reason="relance2")
thread(27, ["08-19"], SUBJECTS[2], draft="09-02", action="ignorer", reason="draft")

settings = {"mon_adresse": "alex@demo-studio.example", "jours_avant_relance": 5, "relances_max": 2,
            "fenetre_jours": 45, "liste_exclusion": person(7).split("<")[1].rstrip(">"),
            "signature": "Alex Demo\nDemo Studio", "date_du_jour": "2026-09-03"}
ROOT.mkdir(parents=True, exist_ok=True)
(ROOT / "threads.json").write_text(json.dumps([{"json": m} for m in messages], ensure_ascii=False, indent=1), encoding="utf-8")
(ROOT / "settings.json").write_text(json.dumps(settings, ensure_ascii=False, indent=1), encoding="utf-8")
(ROOT / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(expected)} threads, {len(messages)} messages written to {ROOT}")
