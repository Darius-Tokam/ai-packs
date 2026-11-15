"""post-recycler guard: check the 10 recycled formats against platform limits,
the pack rules and the source post.

    python3 check_formats.py --source source.md --dir recycled/ [--allow github.com/me/repo]

Expected files in --dir (missing files are reported, not fatal):
    x-post.md  x-thread.md  threads.md  bluesky.md  carousel.md
    instagram.md  video-script.md  newsletter.md  quote-card.md  story.md
Multi-part formats (x-thread, carousel, story) separate parts with a line "---".
newsletter.md starts with "Objet : ..." or "Subject: ...".
video-script.md: lines between [brackets] are on-screen or camera notes, not spoken.

Checks, for every format:
  - length limit of the platform or of the pack (see LIMITS below);
  - every number comes from the source (no invented figure);
  - every URL comes from the source or from --allow;
  - no long dash (U+2014) and no medium dash (U+2013);
  - hashtags: none, except Instagram (5 at most);
  - opening line different from the other formats.
Exit code 1 if any format fails. Standard library only.
"""
import argparse
import re
import sys
from pathlib import Path

FORMATS = ["x-post", "x-thread", "threads", "bluesky", "carousel", "instagram",
           "video-script", "newsletter", "quote-card", "story"]
URL_RE = re.compile(r"(?:https?://)?(?:[a-z0-9-]+\.)+(?:com|ca|io|dev|app|org|net|fr|co)(?:/[^\s)>\]]*)?", re.I)
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
HASHTAG_RE = re.compile(r"(?<![\w&])#\w+")
SPLIT_RE = re.compile(r"^\s*---\s*$", re.M)


def parts(text):
    return [p.strip() for p in SPLIT_RE.split(text) if p.strip()]


def x_len(text):
    """X counts every URL as 23 characters."""
    return len(URL_RE.sub("x" * 23, text))


def words(text):
    return len(re.findall(r"[\w'’%$/:.+-]+", text))


def spoken(text):
    return "\n".join(l for l in text.splitlines() if not l.strip().startswith("["))


def numbers(text):
    text = re.sub(r"(?m)^\s*\d+/\d+\s*", "", text)  # thread numbering "1/6"
    text = URL_RE.sub(" ", text)
    return {n.replace(",", ".") for n in NUM_RE.findall(text)}


def check_limits(fmt, text):
    errs, info = [], ""
    if fmt == "x-post":
        n = x_len(text)
        info = f"{n}/280 car."
        if n > 280:
            errs.append(f"{n} characters, X limit is 280")
    elif fmt == "x-thread":
        ps = parts(text)
        lens = [x_len(p) for p in ps]
        info = f"{len(ps)} posts, max {max(lens) if lens else 0}/280"
        for i, n in enumerate(lens, 1):
            if n > 280:
                errs.append(f"post {i}: {n} characters, X limit is 280")
        if not 3 <= len(ps) <= 8:
            errs.append(f"{len(ps)} posts, the pack wants 3 to 8")
    elif fmt == "threads":
        n = len(text.encode("utf-8"))
        info = f"{n}/500 octets"
        if n > 500:
            errs.append(f"{n} UTF-8 bytes ({len(text)} characters), Threads limit is 500 (accents count double)")
    elif fmt == "bluesky":
        n = len(text)
        info = f"{n}/300 car."
        if n > 300:
            errs.append(f"{n} characters, Bluesky limit is 300")
    elif fmt == "carousel":
        ps = parts(text)
        w = [words(p) for p in ps]
        info = f"{len(ps)} slides, max {max(w) if w else 0} mots"
        if not 5 <= len(ps) <= 10:
            errs.append(f"{len(ps)} slides, the pack wants 5 to 10")
        for i, n in enumerate(w, 1):
            if n > 30:
                errs.append(f"slide {i}: {n} words, the pack allows 30")
    elif fmt == "instagram":
        n = len(text)
        tags = HASHTAG_RE.findall(text)
        info = f"{n}/2200 car., {len(tags)} hashtags"
        if n > 2200:
            errs.append(f"{n} characters, Instagram limit is 2200")
        if len(tags) > 5:
            errs.append(f"{len(tags)} hashtags, the pack allows 5")
    elif fmt == "video-script":
        n = words(spoken(text))
        info = f"{n} mots dits"
        if not 55 <= n <= 90:
            errs.append(f"{n} spoken words, the pack wants 55 to 90 (about 30 seconds)")
    elif fmt == "newsletter":
        first, _, body = text.partition("\n")
        subject = re.sub(r"^(objet|subject)\s*:\s*", "", first.strip(), flags=re.I)
        n, wb = len(subject), words(body)
        info = f"objet {n}/60 car., {wb} mots"
        if not re.match(r"^(objet|subject)\s*:", first.strip(), re.I):
            errs.append("first line must be 'Objet : ...' or 'Subject: ...'")
        if n > 60:
            errs.append(f"subject {n} characters, the pack allows 60")
        if not 80 <= wb <= 250:
            errs.append(f"body {wb} words, the pack wants 80 to 250")
    elif fmt == "quote-card":
        n = words(text)
        info = f"{n}/20 mots"
        if n > 20:
            errs.append(f"{n} words, the pack allows 20")
    elif fmt == "story":
        ps = parts(text)
        w = [words(p) for p in ps]
        info = f"{len(ps)} écrans, max {max(w) if w else 0} mots"
        if not 3 <= len(ps) <= 5:
            errs.append(f"{len(ps)} screens, the pack wants 3 to 5")
        for i, n in enumerate(w, 1):
            if n > 15:
                errs.append(f"screen {i}: {n} words, the pack allows 15")
    return errs, info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--allow", action="append", default=[], help="URL allowed even if absent from the source")
    a = ap.parse_args()
    source = Path(a.source).read_text(encoding="utf-8")
    src_nums = numbers(source)
    src_urls = {u.lower().rstrip("/.") for u in URL_RE.findall(source)} | {u.lower().rstrip("/") for u in a.allow}
    d = Path(a.dir)
    rows, failed, openings = [], 0, {}
    for fmt in FORMATS:
        f = d / f"{fmt}.md"
        if not f.exists():
            rows.append((fmt, "MISSING", "", [f"{f.name} not found"]))
            failed += 1
            continue
        text = f.read_text(encoding="utf-8").strip()
        errs, info = check_limits(fmt, text)
        invented = sorted(numbers(text) - src_nums, key=lambda s: (len(s), s))
        if invented:
            errs.append("numbers not in the source: " + ", ".join(invented))
        urls = {u.lower().rstrip("/.") for u in URL_RE.findall(text)}
        foreign = sorted(u for u in urls if not any(u.startswith(s) or s.startswith(u) for s in src_urls))
        if foreign:
            errs.append("URLs not in the source: " + ", ".join(foreign))
        if chr(0x2014) in text or chr(0x2013) in text:
            errs.append("long or medium dash")
        if fmt != "instagram" and HASHTAG_RE.findall(text):
            errs.append("hashtags outside Instagram: " + " ".join(HASHTAG_RE.findall(text)))
        first = re.sub(r"^(objet|subject)\s*:\s*", "", text.splitlines()[0], flags=re.I).strip().lower()
        first = re.sub(r"^\d+/\d+\s*", "", first)
        if first in openings:
            errs.append(f"same opening line as {openings[first]}")
        openings.setdefault(first, fmt)
        rows.append((fmt, "FAIL" if errs else "PASS", info, errs))
        failed += bool(errs)
    print("| Format | Résultat | Mesure | Problèmes |")
    print("|---|---|---|---|")
    for fmt, status, info, errs in rows:
        print(f"| {fmt} | {status} | {info} | {'; '.join(errs)} |")
    print(f"\nGUARD VERDICT: {len(FORMATS) - failed}/{len(FORMATS)} formats PASS"
          + (f", {failed} to rewrite" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
