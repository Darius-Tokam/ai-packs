#!/usr/bin/env python3
"""Find the API keys, tokens, signed URLs and client emails exposed in logs.

    python3 leak_scan.py app.log [more.log ...]      Markdown report (French)
    railway logs | python3 leak_scan.py              read the log on stdin
    python3 leak_scan.py app.log --json              JSON report
    python3 leak_scan.py app.log --redact out.log    also write a masked copy
    python3 leak_scan.py --filter python             print a logging.Filter class
    python3 leak_scan.py --filter node               print a redaction module for Node

Five forms of leak are found:
  1. a secret in clear: a URL query parameter or a named field (key, api_key,
     token, access_token, client_secret, password, secret...) or a known key
     shape anywhere in a line (Google AIza, Stripe sk_live_, sk-, GitHub ghp_,
     AWS AKIA, Slack xoxb-, JWT...), or the password of a connection URL;
  2. a presigned URL logged with its signature (X-Amz-Signature,
     X-Goog-Signature, Azure SAS sig with se/sp/sv);
  3. OAuth secrets in a URL (code, access_token, id_token, client_secret on an
     oauth, callback, redirect or login path);
  4. an auth header copied into the log (Authorization: Bearer or Basic,
     x-api-key, x-goog-api-key, session cookie);
  5. a client email address (personal data).

Findings are grouped by distinct secret: a key repeated on 400 lines is one
leak with its count, first and last line. A key cut at the end of a line by a
truncating log handler is reported as a partial leak ("fuite partielle").
The report never prints a full secret: the first 4 characters (a quarter of
the value under 16 characters) and the length, so it is safe to paste.

Exit codes: 0 no leak, 1 leak(s) found, 2 bad input (missing, unreadable or
binary file, no input, unknown option). Standard library only.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.0.0"

# ---- leak-scan core: begin ----
# What counts as a leak on one log line, and how it is masked. `leak_scan.py
# --filter python` prints this block unchanged inside the filter, so the filter
# masks exactly what the scan reports. Standard library only.
import re

_A = re.ASCII
_AI = re.ASCII | re.IGNORECASE

# Known key shapes, found anywhere in a line.
SHAPES = (
    ("google-api-key", r"AIza[0-9A-Za-z_\-]{35}"),
    ("stripe-live-key", r"(?:sk|rk)_live_[0-9A-Za-z]{20,}"),
    ("github-token", r"gh[pousr]_[0-9A-Za-z]{36}|github_pat_[0-9A-Za-z_]{40,}"),
    ("gitlab-token", r"glpat-[0-9A-Za-z_\-]{20}"),
    ("aws-access-key-id", r"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    ("slack-token", r"xox[abprs]-[0-9A-Za-z\-]{10,}"),
    ("huggingface-token", r"hf_[0-9A-Za-z]{34}"),
    ("sendgrid-key", r"SG\.[0-9A-Za-z_\-]{22}\.[0-9A-Za-z_\-]{43}"),
    ("google-oauth-token", r"ya29\.[0-9A-Za-z_\-]{20,}"),
    ("sk-api-key", r"sk-(?:proj-|svcacct-|admin-|ant-)?[0-9A-Za-z_\-]{20,}"),
    ("jwt", r"eyJ[0-9A-Za-z_\-]{8,}\.eyJ[0-9A-Za-z_\-]{8,}\.[0-9A-Za-z_\-]{8,}"),
)
_SHAPE_ANY = "|".join("(?:%s)" % p for _, p in SHAPES)
_SHAPE_FULL = re.compile("(?:%s)" % _SHAPE_ANY, _A)
# The start of a known key: a value that starts like one, is shorter than the
# full shape and ends the line was cut by a truncating handler.
_PREFIXES = r"AIza|sk_live_|rk_live_|gh[pousr]_|github_pat_|glpat-|AKIA|ASIA|xox[abprs]-|hf_|sk-proj-|sk-ant-"
_PREFIX = re.compile("(?:%s)" % _PREFIXES, _A)
_TAIL_SRC = r"[ \t\r]*(?:\.\.\.|\u2026|\[truncated\]|\(truncated\))?[ \t\r]*$"
_TAIL = re.compile(_TAIL_SRC, _A)

_VAL = r"[^ \t\r&\"'<>#,;)}\]]+"
_L = r"(?<![0-9A-Za-z_\-])"
_R = r"(?![0-9A-Za-z_\-])"
_NAMES = (r"(?:[0-9A-Za-z]+[_\-])*(?:api[_\-]?key|access[_\-]?key|secret[_\-]?key|private[_\-]?key"
          r"|client[_\-]?secret|secret|password|passwd|(?:access|refresh|id|auth|session)[_\-]?token|token)")

# (priority, rule, regex). On overlapping matches the lowest priority wins.
# Every regex has a group v (the value to mask) and most have a group n (the name).
_RULES = (
    (0, "userinfo", re.compile(
        r"(?<![0-9A-Za-z+.\-])(?P<n>[A-Za-z][0-9A-Za-z+.\-]*)://[^:/?#@ \t\r\"'<>]+:(?P<v>[^@/?# \t\r\"'<>]+)@", _A)),
    (1, "auth-header", re.compile(
        _L + r"(?:proxy-)?authorization[\"']?[ \t]*[:=][ \t]*[\"']?(?P<n>bearer|basic|token|bot|apikey)[ \t]+"
        r"(?P<v>[0-9A-Za-z._~+/=\-]+)", _AI)),
    (1, "key-header", re.compile(
        _L + r"(?P<n>x-api-key|x-goog-api-key|api-key|x-auth-token|x-access-token|private-token|x-functions-key"
        r"|x-rapidapi-key|ocp-apim-subscription-key|x-amz-security-token)[\"']?[ \t]*:[ \t]*[\"']?"
        r"(?P<v>[^ \t\r\"',;}\]]+)", _AI)),
    (2, "presigned", re.compile(
        r"(?<=[?&])(?P<n>X-Amz-Signature|X-Goog-Signature|X-Amz-Security-Token|sig|Signature)=(?P<v>" + _VAL + ")", _A)),
    (3, "oauth-code", re.compile(r"(?<=[?&#])(?P<n>code)=(?P<v>" + _VAL + ")", _A)),
    (4, "param", re.compile(r"(?<![0-9A-Za-z_.\-])(?P<n>" + _NAMES + r"|key)=(?P<v>" + _VAL + ")", _AI)),
    (4, "json-field", re.compile(
        r"(?<![0-9A-Za-z_])[\"'](?P<n>" + _NAMES + r")[\"'][ \t]*:[ \t]*[\"'](?P<v>[^\"'\r\n]+)[\"']", _AI)),
    (5, "shape", re.compile(_L + "(?P<v>" + _SHAPE_ANY + ")" + _R, _A)),
    (6, "partial", re.compile(_L + r"(?P<v>(?:" + _PREFIXES + r")[0-9A-Za-z_\-]{4,})(?=" + _TAIL_SRC + ")", _A)),
    (7, "email", re.compile(
        r"(?<![0-9A-Za-z._%+\-])(?P<v>[0-9A-Za-z][0-9A-Za-z._%+\-]*(?:@|%40)"
        r"(?:[0-9A-Za-z](?:[0-9A-Za-z\-]*[0-9A-Za-z])?\.)+[A-Za-z]{2,24})(?![0-9A-Za-z\-])", _A)),
)
_COOKIE = re.compile(_L + r"(?:set-)?cookie[\"']?[ \t]*:[ \t]*[\"']?(?P<c>[^\"'\r\n]+)", _AI)
_COOKIE_PAIR = re.compile(r"(?:^|;)[ \t]*(?P<n>[0-9A-Za-z_.\-]+)=(?P<v>[^; \t\r\"']+)", _A)
_COOKIE_NAME = re.compile(r"sess|sid|auth|token|jwt|remember", _AI)
_CSRF = re.compile(r"csrf|xsrf", _AI)

# Values that are not secrets: already masked, templates, placeholders.
_MASKED = re.compile(r"\*{2,}|REDACTED|FILTERED|MASKED|HIDDEN|REMOVED|^x{4,}$|^\.{3,}$|^\u2022", _AI)
_TEMPLATE = re.compile(r"^(?:\{|\$|%\(|%[sd]$|<|your[_\-]|my[_\-])", _AI)
_PLACEHOLDERS = ("null", "none", "nil", "undefined", "true", "false", "empty", "expired", "invalid", "missing",
                 "required", "string", "secret", "token", "password", "pass", "your_api_key", "api_key")
_HAS_DIGIT = re.compile(r"[0-9]", _A)
_HAS_ALPHA = re.compile(r"[A-Za-z]", _A)
_HAS_UPPER = re.compile(r"[A-Z]", _A)
_HAS_LOWER = re.compile(r"[a-z]", _A)
_KEYLIKE = re.compile(r"[0-9A-Za-z_\-]{20,}", _A)
_DIGITS = re.compile(r"[0-9]+", _A)
# token names that are not secrets: pagination, CSRF, counters
_NOT_SECRET_PREFIX = re.compile(
    r"(?:^|_)(?:page|next|cursor|continuation|sync|csrf|xsrf|resume|pagination|max|total|prompt|completion|num|count)"
    r"(?:_|$)", _A)
_SAS = re.compile(r"[?&](?:sv|se|sp|sr|spr)=", _A)
_LEGACY_SIG = re.compile(r"[?&](?:Expires|Key-Pair-Id|AWSAccessKeyId|GoogleAccessId)=", _A)
_OAUTH_PATH = re.compile(r"oauth|callback|redirect|authori[sz]e|/auth(?:/|$)|/token(?:/|$)|sign[_\-]?in|login|/connect/",
                         _AI)
_RESERVED = ("example.com", "example.org", "example.net")
# reserved names, file extensions (logo@2x.png) and systemd units (getty@tty1.service) are not addresses
_NO_EMAIL_TLD = ("test", "invalid", "example", "localhost", "local", "internal", "png", "jpg", "jpeg", "gif",
                 "svg", "webp", "ico", "js", "css", "map", "json", "txt", "html", "py", "ts", "log", "conf", "yml",
                 "yaml", "toml", "ini", "lock", "service", "socket", "timer", "mount", "slice", "scope", "device")
_NOREPLY = re.compile(r"(?:no[\-_.]?reply|do[\-_.]?not[\-_.]?reply|mailer-daemon|postmaster|bounces?)(?:[+.\-_]|$)", _AI)
_STOPS = " \t\r\"'<>`"


def _tok_span(line, s, e):
    """Span of the whitespace or quote delimited token around [s, e): the URL a parameter belongs to."""
    i = s
    while i > 0 and line[i - 1] not in _STOPS:
        i -= 1
    j = e
    while j < len(line) and line[j] not in _STOPS:
        j += 1
    return i, j


def _tok(line, s, e):
    i, j = _tok_span(line, s, e)
    return line[i:j]


def _path(tok):
    return re.split(r"[?#]", tok, maxsplit=1)[0]


def _email_ok(v):
    local, _, domain = v.replace("%40", "@").rpartition("@")
    d, low = domain.lower(), local.lower()
    if d[d.rfind(".") + 1:] in _NO_EMAIL_TLD:
        return False
    if any(d == r or d.endswith("." + r) for r in _RESERVED):
        return False
    if d.endswith("gserviceaccount.com") or d.endswith("noreply.github.com"):
        return False
    return not (low == "git" or _NOREPLY.match(low))


def _check(rule, name, v, line, s, e):
    if rule == "email":
        return _email_ok(v)
    if not v or _MASKED.search(v) or _TEMPLATE.search(v) or v.lower() in _PLACEHOLDERS:
        return False
    if rule == "shape":
        return True
    if rule == "partial":
        return len(v) >= 8 and not _SHAPE_FULL.fullmatch(v)
    if rule == "userinfo":
        return len(v) >= 4 and not (_DIGITS.fullmatch(v) and len(v) <= 5)
    if rule in ("auth-header", "key-header", "cookie"):
        return len(v) >= 8
    if rule == "presigned":
        tok = _tok(line, s, e)
        if name == "sig":
            return len(v) >= 16 and bool(_SAS.search(tok))
        if name == "Signature":
            return len(v) >= 16 and bool(_LEGACY_SIG.search(tok))
        return len(v) >= 16
    if rule == "oauth-code":
        return len(v) >= 10 and not _DIGITS.fullmatch(v) and bool(_OAUTH_PATH.search(_path(_tok(line, s, e))))
    n = name.lower().replace("-", "_")
    if n == "key":  # a bare "key" is often a cache or object key: it needs a random-looking part
        return bool(_SHAPE_FULL.fullmatch(v)) or bool(_KEYLIKE.fullmatch(v) and any(
            len(seg) >= 8 and _HAS_ALPHA.search(seg) and _HAS_DIGIT.search(seg) for seg in re.split(r"[\-_]", v)))
    if n.endswith("token") and _NOT_SECRET_PREFIX.search(n[:-5]):
        return False
    if n.endswith("password") or n.endswith("passwd"):
        return len(v) >= 4
    if " " in v or "\t" in v:  # a phrase ("Invalid Session Token"), not a secret
        return False
    return len(v) >= 8 and bool(_HAS_DIGIT.search(v) or (len(v) >= 16 and _HAS_UPPER.search(v) and _HAS_LOWER.search(v)))


def find_hits(line):
    """Leaks on one line: sorted (start, end, rule, name, value, partial) tuples, never overlapping."""
    cands = []
    for order, (prio, rule, rx) in enumerate(_RULES):
        for m in rx.finditer(line):
            s, e = m.span("v")
            name = m.groupdict().get("n") or ""
            if _check(rule, name, m.group("v"), line, s, e):
                cands.append((prio, s, e, order, rule, name, m.group("v")))
    for m in _COOKIE.finditer(line):
        base = m.start("c")
        for k in _COOKIE_PAIR.finditer(m.group("c")):
            name, v = k.group("n"), k.group("v")
            if _COOKIE_NAME.search(name) and not _CSRF.search(name) and _check("cookie", name, v, line, 0, 0):
                cands.append((1, base + k.start("v"), base + k.end("v"), 99, "cookie", name, v))
    cands.sort(key=lambda c: (c[0], c[1], c[1] - c[2], c[3]))
    kept = []
    for c in cands:
        if all(c[2] <= k[1] or c[1] >= k[2] for k in kept):
            kept.append(c)
    kept.sort(key=lambda c: c[1])
    hits = []
    for _, s, e, _, rule, name, v in kept:
        partial = (rule != "email" and bool(_PREFIX.match(v)) and not _SHAPE_FULL.fullmatch(v)
                   and bool(_TAIL.match(line, e)))
        hits.append((s, e, rule, name, v, partial))
    return hits


def mark(rule):
    return "[REDACTED_EMAIL]" if rule == "email" else "[REDACTED]"


def redact_line(line, hits=None):
    """The line with every leaked value replaced by [REDACTED] (or [REDACTED_EMAIL])."""
    for s, e, rule, _, _, _ in reversed(find_hits(line) if hits is None else hits):
        line = line[:s] + mark(rule) + line[e:]
    return line


def redact(text):
    return "\n".join(redact_line(line) for line in str(text).split("\n"))
# ---- leak-scan core: end ----


# ---------------------------------------------------------------- grouping

FORMS = {
    "url-secret": "clé ou secret en clair",
    "presigned-url": "URL présignée avec sa signature",
    "oauth-callback": "secret OAuth dans une URL",
    "auth-header": "en-tête d'authentification recopié",
    "email": "adresse e-mail de client",
}
SHAPE_LABELS = {
    "google-api-key": "clé d'API Google", "stripe-live-key": "clé Stripe live", "github-token": "jeton GitHub",
    "gitlab-token": "jeton GitLab", "aws-access-key-id": "identifiant de clé AWS", "slack-token": "jeton Slack",
    "huggingface-token": "jeton Hugging Face", "sendgrid-key": "clé SendGrid", "sk-api-key": "clé d'API sk-",
    "google-oauth-token": "jeton OAuth Google",
    "jwt": "jeton JWT",
}
PREFIX_KIND = (("AIza", "google-api-key", 39), ("sk_live_", "stripe-live-key", None), ("rk_live_", "stripe-live-key", None),
               ("github_pat_", "github-token", None), ("gh", "github-token", 40), ("glpat-", "gitlab-token", 26),
               ("AKIA", "aws-access-key-id", 20), ("ASIA", "aws-access-key-id", 20), ("xox", "slack-token", None),
               ("hf_", "huggingface-token", 37), ("sk-", "sk-api-key", None))
OAUTH_NAMES = ("code", "access_token", "id_token", "refresh_token", "client_secret", "token", "auth_token")
OAUTH_PREF = ("access_token", "id_token", "refresh_token", "token", "auth_token", "code")
URLISH = ("param", "presigned", "oauth-code", "shape", "partial", "userinfo")
ROTATE = "le correctif arrête la fuite, il n'efface pas ce qui est déjà dans les logs."
ROTATE_ALL = "Renouvelle chaque clé trouvée (rotation) : " + ROTATE
NOT_SEEN = ("Ce que le scan ne voit pas : une clé d'un format inconnu sans nom de paramètre reconnaissable, "
            "un secret encodé (base64, URL encodée deux fois), un secret coupé sur plusieurs lignes. "
            "Zéro fuite ici ne prouve pas qu'une clé n'a jamais fui ailleurs.")
_HTTPERR = re.compile(r"(?:Client|Server) Error.*for url:", re.ASCII)


def _norm(name):
    return name.lower().replace("-", "_")


def shape_kind(v):
    for kind, pat in SHAPES:
        if re.fullmatch(pat, v, re.ASCII):
            return kind
    return None


def prefix_kind(v):
    for prefix, kind, full in PREFIX_KIND:
        if v.startswith(prefix):
            return kind, full
    return None, None


def _kind(h):
    if h[2] == "email":
        return "email"
    if h[5] or h[2] == "partial":
        return prefix_kind(h[4])[0]
    return shape_kind(h[4])


def _hit_name(h):
    """How a secondary hit is named in the report: its parameter, or what its shape is."""
    if h[2] == "shape":
        return SHAPE_LABELS.get(_kind(h), "secret")
    return _norm(h[3]) if h[3] else h[2]


def _durable(h, form):
    """A durable secret (an API key, a client secret) is grouped by value; per-request ones by where they leak."""
    rule = h[2]
    if rule in ("presigned", "oauth-code", "cookie", "email"):
        return False
    kind = _kind(h)
    if kind == "jwt":
        return False
    if rule == "auth-header":
        return h[3].lower() == "basic" or kind is not None
    if form == "oauth-callback" and kind is None and _norm(h[3]) in OAUTH_NAMES and _norm(h[3]) != "client_secret":
        return False
    return True


def _occurrences(line, hits):
    """Hits of one URL belong together (code + client_secret, signature + access key id)."""
    occ = {}
    for h in hits:
        span = (h[0], h[1])
        if h[2] in URLISH:
            i, j = _tok_span(line, h[0], h[1])
            if "?" in line[i:j] or "#" in line[i:j]:
                span = (i, j)
        occ.setdefault(span, []).append(h)
    return [(line[a:b], hs) for (a, b), hs in occ.items()]


def _classify(tok, hs):
    rules = [h[2] for h in hs]
    if "presigned" in rules:
        return "presigned-url"
    if "email" in rules:
        return "email"
    if any(r in ("auth-header", "key-header", "cookie") for r in rules):
        return "auth-header"
    if (("?" in tok or "#" in tok) and _OAUTH_PATH.search(_path(tok))
            and any(h[2] == "oauth-code" or (h[2] == "param" and _norm(h[3]) in OAUTH_NAMES) for h in hs)):
        return "oauth-callback"
    return "url-secret"


def _endpoint(tok):
    p = re.sub(r"^[A-Za-z][A-Za-z0-9+.\-]*://", "", _path(tok))
    p = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", "{id}", p)
    return re.sub(r"[0-9]+", "{n}", p)


def _signer(tok, hs):
    for h in hs:
        if h[2] == "shape" and h[4][:4] in ("AKIA", "ASIA"):
            return h[4]
    m = re.search(r"[?&](?:X-Amz-Credential|X-Goog-Credential|GoogleAccessId|AWSAccessKeyId)=([^&]+?)(?:%2F|/|&|$)", tok)
    if m:
        return m.group(1)
    m = re.match(r"(?:[A-Za-z][A-Za-z0-9+.\-]*://)?([^/?#]+)", tok)
    return m.group(1) if m else tok


def _expires(tok):
    m = re.search(r"[?&]X-(?:Amz|Goog)-Expires=([0-9]+)", tok)
    if m:
        s = int(m.group(1))
        return "%d h" % (s // 3600) if s >= 3600 and s % 3600 == 0 else ("%d min" % (s // 60) if s >= 60 else "%d s" % s)
    m = re.search(r"[?&]se=([^&]+)", tok)
    if m:
        return "jusqu'au " + m.group(1).replace("%3A", ":")
    m = re.search(r"[?&]Expires=([0-9]{9,11})(?:&|$)", tok)
    if m:
        return "jusqu'au " + datetime.fromtimestamp(int(m.group(1)), timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return None


def _group_key(form, tok, hs):
    if form == "presigned-url":
        sigs = [h for h in hs if h[2] == "presigned"]
        prim = next((h for h in sigs if h[3] != "X-Amz-Security-Token"), sigs[0])
        return ("presigned", _signer(tok, hs)), prim
    if form == "email":
        return ("email", hs[0][4].replace("%40", "@").lower()), hs[0]
    durable = [h for h in hs if _durable(h, form)]
    if durable:
        return ("v", durable[0][4]), durable[0]
    if form == "oauth-callback":
        prim = sorted(hs, key=lambda h: OAUTH_PREF.index(_norm(h[3])) if _norm(h[3]) in OAUTH_PREF else 9)[0]
        return ("oauth", _endpoint(tok), tuple(sorted({_norm(h[3]) for h in hs}))), prim
    prim = hs[0]
    if form == "auth-header":
        return ("cookie" if prim[2] == "cookie" else "header", prim[3].lower()), prim
    if prim[2] == "shape" and _kind(prim) == "jwt":
        return ("jwt",), prim
    return ("ep", _endpoint(tok), _norm(prim[3])), prim


def _label(form, prim):
    rule, name = prim[2], prim[3]
    kind = _kind(prim)
    base = SHAPE_LABELS.get(kind)
    if form == "email":
        return "adresse e-mail"
    if form == "presigned-url":
        return {"X-Amz-Signature": "URL présignée S3", "X-Amz-Security-Token": "URL présignée S3",
                "X-Goog-Signature": "URL signée Google Cloud Storage", "sig": "URL SAS Azure"}.get(name, "URL signée")
    if rule == "userinfo":
        return "mot de passe dans une URL %s://" % name
    if rule == "auth-header":
        return "en-tête Authorization %s" % name.capitalize()
    if rule == "key-header":
        return "en-tête %s" % name.lower()
    if rule == "cookie":
        return "cookie %s" % name
    if rule == "oauth-code":
        return "code OAuth"
    if rule in ("param", "json-field"):
        where = "paramètre" if rule == "param" else "champ"
        if form == "oauth-callback" and not base:
            return "%s dans une URL OAuth" % name
        return "%s, %s %s" % (base or "secret", where, name)
    return base or "secret"


def _advice(g):
    form, prim, count = g["form"], g["prim"], len(g["lines"])
    names = set(g["names"])
    kind = _kind(prim)
    if form == "presigned-url":
        exp = " (ici %s)" % g["expires"] if g["expires"] else ""
        return ("L'URL présignée est loggée avec sa signature : quiconque lit ce log peut ouvrir l'objet tant que "
                "la signature est valide%s." % exp,
                "Logge la clé de l'objet (le chemin sans la query string), jamais l'URL signée. Renvoie l'URL signée "
                "au client sans l'écrire dans les logs.",
                "Si l'objet est sensible, renouvelle la clé qui a signé (rotation), sinon laisse expirer la signature : "
                + ROTATE)
    if form == "oauth-callback":
        parts = []
        if "code" in names:
            parts.append("le code s'échange contre un jeton pendant quelques minutes")
        if names & {"access_token", "id_token", "refresh_token", "token", "auth_token"}:
            parts.append("le jeton donne accès au compte de l'utilisateur")
        if "client_secret" in names:
            parts.append("le client_secret permet de se faire passer pour ton application")
        listed = sorted(names)
        listed = " et ".join([", ".join(listed[:-1]), listed[-1]]) if len(listed) > 1 else listed[0]
        return ("L'URL OAuth est loggée avec sa query string, et %s y %s en clair : %s." % (
                    listed, "passent" if len(names) > 1 else "passe", ", ".join(parts)),
                "Logge le chemin de l'URL OAuth sans la query string (log d'accès compris, et logs DEBUG de requests "
                "ou urllib3). Fais l'échange du code en POST, client_secret dans le corps de la requête, jamais dans "
                "l'URL.",
                ("Renouvelle le client_secret dans la console du fournisseur (rotation) : " if "client_secret" in names
                 else "Révoque les jetons concernés et ferme les sessions (rotation) : ") + ROTATE)
    if form == "auth-header":
        return ("Les en-têtes de la requête sont écrits tels quels dans le log : un dump de req.headers, le "
                "sérialiseur de requête du logger ou un middleware de debug.",
                "Ne logge jamais les en-têtes bruts : garde une liste blanche (méthode, chemin, user-agent) ou masque "
                "authorization, cookie et x-api-key avant l'écriture (pino : option redact).",
                ("Renouvelle la clé (rotation) : " if _durable(prim, form)
                 else "Révoque les jetons concernés et ferme les sessions (rotation) : ") + ROTATE)
    if form == "email":
        return ("Une adresse e-mail de client, donnée personnelle, est écrite dans le log.",
                "Logge l'identifiant du client (user_id ou customer_id), pas son adresse.",
                "Purge ces lignes ou raccourcis la rétention des logs : " + ROTATE)
    if prim[2] == "userinfo":
        return ("Une URL de connexion contient son mot de passe (%s://utilisateur:mot_de_passe@hôte), souvent "
                "DATABASE_URL affichée au démarrage ou dans une erreur de connexion." % prim[3],
                "Ne logge jamais l'URL de connexion : logge l'hôte et le nom de la base.",
                "Change le mot de passe (rotation) : " + ROTATE)
    action = ("Change le mot de passe (rotation) : " if _norm(prim[3]).endswith(("password", "passwd"))
              else "Révoque les jetons concernés et ferme les sessions (rotation) : " if kind == "jwt"
              else "Renouvelle la clé (rotation) : ")
    if g["in_url"]:
        cause = ("Le secret passe en paramètre d'URL. Tout ce qui écrit l'URL le recopie : le message d'une exception "
                 "HTTP (raise_for_status() y met l'URL complète, paramètres compris), response.url, les logs DEBUG de "
                 "requests ou urllib3, le log d'accès du proxy.")
        if g["httperror"]:
            cause += " Ici, c'est le message d'une HTTPError : un except qui appelle logger.exception(...) l'écrit tel quel."
        if count >= 20:
            cause += (" La fuite revient sur %s lignes : chaque appel qui échoue réécrit la clé%s." % (
                num(count), ", et une boucle de réessais sur des 429 (quota épuisé) en ajoute une à chaque appel"
                if g["http429"] else ""))
        header = ("x-goog-api-key" if kind == "google-api-key"
                  else "celui que l'API documente, souvent Authorization")
        fix = ("Passe la clé dans un en-tête (%s), jamais dans l'URL. Dans le except, logge le code HTTP et le chemin "
               "sans la query string, pas l'exception brute ni response.url." % header)
        return cause, fix, action + ROTATE
    return ("Le secret est écrit en clair dans le log : un objet de configuration, une variable d'environnement ou "
            "un corps de requête loggé tel quel.",
            "Retire ce champ du log avant l'écriture (ou n'en garde que les 4 premiers caractères).",
            action + ROTATE)


def _safe(s):
    return s.encode("utf-8", "surrogateescape").decode("utf-8", "replace")


def mask(v):
    """First 4 characters (a quarter under 16 characters), never the value."""
    v = _safe(v)
    return v[:4 if len(v) >= 16 else len(v) // 4] + "***"


def num(n):
    return "{:,}".format(n).replace(",", " ")


def _window(line, hits, prim):
    """The masked line, cut around the leak."""
    pos = prim[0]
    for h in hits:
        if h[0] < prim[0]:
            pos += len(mark(h[2])) - (h[1] - h[0])
    masked = _safe(redact_line(line, hits)).replace("`", "'")
    a, b = max(0, pos - 110), min(len(masked), pos + 70)
    return ("\u2026" if a else "") + masked[a:b] + ("\u2026" if b < len(masked) else "")


def scan(texts):
    """texts: list of (name, text). Returns the report as a dict."""
    groups, files = {}, []
    for fi, (fname, text) in enumerate(texts):
        parts = text.split("\n")
        n = len(parts) - (1 if parts and parts[-1] == "" else 0)
        files.append({"path": fname, "lines": n})
        for ln, line in enumerate(parts[:n], 1):
            if not line:
                continue
            hits = find_hits(line)
            for tok, hs in _occurrences(line, hits):
                form = _classify(tok, hs)
                key, prim = _group_key(form, tok, hs)
                g = groups.get(key)
                if g is None:
                    g = groups[key] = {"key": key, "form": form, "forms": {}, "prim": prim, "values": {}, "names": {},
                                       "lines": {}, "partial_lines": {}, "partial_only": True, "visible": [],
                                       "in_url": False, "httperror": False, "http429": False, "expires": None,
                                       "window": _window(line, hits, prim)}
                g["forms"][form] = g["forms"].get(form, 0) + 1
                g["values"][prim[4]] = 1
                for h in hs:
                    if h is not prim and h[2] != "partial":
                        g["names"][_hit_name(h)] = 1
                    elif h[3]:
                        g["names"][_norm(h[3])] = 1
                g["lines"][(fi, ln)] = 1
                if prim[5]:
                    g["partial_lines"][(fi, ln)] = 1
                    g["visible"].append(len(prim[4]))
                else:
                    g["partial_only"] = False
                g["in_url"] |= "?" in tok or "#" in tok
                if _HTTPERR.search(line):
                    g["httperror"] = True
                    g["http429"] |= " 429 " in line
                if form == "presigned-url" and not g["expires"]:
                    g["expires"] = _expires(tok)
    # a key cut by truncation joins the longer or full key it starts with
    for key in sorted((k for k in groups if k[0] == "v"), key=lambda k: len(k[1])):
        g = groups[key]
        if not g["partial_only"]:
            continue
        longer = [k for k in groups if k[0] == "v" and len(k[1]) > len(key[1]) and k[1].startswith(key[1])]
        if longer:
            t = groups[max(longer, key=lambda k: len(k[1]))]
            for f in ("lines", "partial_lines", "values", "names"):
                t[f].update(g[f])
            for f, c in g["forms"].items():
                t["forms"][f] = t["forms"].get(f, 0) + c
            t["visible"] += g["visible"]
            t["httperror"] |= g["httperror"]
            t["in_url"] |= g["in_url"]
            del groups[key]
    findings, flagged = [], set()
    order = list(FORMS)
    for g in groups.values():
        g["lines"] = sorted(g["lines"])
    for g in sorted(groups.values(), key=lambda g: (order.index(g["form"]), g["lines"][0])):
        prim = g["prim"]
        cause, fix, after = _advice(g)
        loc = [{"file": files[fi]["path"], "line": ln} for fi, ln in g["lines"]]
        flagged.update(g["lines"])
        value = max(g["values"], key=len) if g["partial_only"] else prim[4]
        expected = prefix_kind(value)[1] if g["visible"] else None
        prim_name = _norm(prim[3]) if prim[3] else ""
        findings.append({
            "id": len(findings) + 1,
            "form": g["form"],
            "form_label": FORMS[g["form"]],
            "forms": sorted(g["forms"]),
            "what": _label(g["form"], prim),
            "excerpt": mask(value),
            "length": len(value),
            "partial": g["partial_only"],
            "status": "fuite partielle" if g["partial_only"] else "fuite complète",
            "partial_lines": len(g["partial_lines"]),
            "visible_chars": [min(g["visible"]), max(g["visible"])] if g["visible"] else None,
            "expected_length": expected,
            "count": len(loc),
            "distinct_values": 1 if g["key"][0] == "v" else len(g["values"]),
            "also": [n for n in g["names"] if n != prim_name],
            "expires": g["expires"],
            "first": loc[0],
            "last": loc[-1],
            "lines": loc,
            "masked_line": g["window"],
            "cause": cause,
            "fix": fix,
            "after": after,
        })
    return {"tool": "leak-scan", "version": VERSION, "files": files,
            "lines_read": sum(f["lines"] for f in files), "leaks_found": len(findings),
            "lines_flagged": len(flagged), "findings": findings, "rotate": ROTATE_ALL if findings else None}


# ---------------------------------------------------------------- report

def _plural(n, one, many):
    return "%s %s" % (num(n), one if n == 1 else many)


def _ref(res, loc):
    return str(loc["line"]) if len(res["files"]) == 1 else "%s:%d" % (loc["file"], loc["line"])


def _excerpt(f):
    s = "`%s` (%d car.)" % (f["excerpt"], f["length"])
    if f["partial"]:
        vis = f["visible_chars"]
        seen = "%d" % vis[0] if vis[0] == vis[1] else "%d à %d" % tuple(vis)
        s = "`%s` (%s car. visibles%s), fuite partielle" % (
            f["excerpt"], seen, " sur %d" % f["expected_length"] if f["expected_length"] else "")
    return s


def to_markdown(res):
    out = []
    read = ", ".join("`%s` (%s)" % (f["path"], _plural(f["lines"], "ligne", "lignes")) for f in res["files"])
    fs = res["findings"]
    if not fs:
        out += ["# leak-scan : aucune fuite trouvée", "",
                "Lu : %s. Aucune des 5 formes de fuite n'apparaît." % read, "", NOT_SEEN]
        if res.get("redacted"):
            out += ["", "Copie masquée écrite : `%s` (0 ligne modifiée)." % res["redacted"]["path"]]
        return "\n".join(out) + "\n"
    out += ["# leak-scan : %s" % _plural(len(fs), "fuite trouvée", "fuites trouvées"), "",
            "Lu : %s. **%s** sur %s." % (read, _plural(len(fs), "fuite distincte", "fuites distinctes"),
                                         _plural(res["lines_flagged"], "ligne", "lignes")),
            "Chaque extrait garde les 4 premiers caractères et la longueur : ce rapport ne recopie aucun secret "
            "complet, tu peux le coller.", "",
            "| # | Forme | Ce qui fuit | Extrait masqué | Lignes | Première | Dernière |",
            "|---|---|---|---|---|---|---|"]
    for f in fs:
        out.append("| %d | %s | %s | %s | %d | %s | %s |" % (
            f["id"], f["form_label"], f["what"], _excerpt(f), f["count"], _ref(res, f["first"]),
            _ref(res, f["last"])))
    for f in fs:
        refs = ", ".join(_ref(res, loc) for loc in f["lines"][:10])
        more = " et %s" % _plural(f["count"] - 10, "autre", "autres") if f["count"] > 10 else ""
        first = f["what"].split(" ")[0]
        title = f["what"] if "_" in first or "-" in first else f["what"][0].upper() + f["what"][1:]
        vals = "" if f["distinct_values"] == 1 else ", %s" % _plural(f["distinct_values"], "valeur distincte",
                                                                     "valeurs distinctes")
        out += ["", "## %d. %s" % (f["id"], title), "",
                "- **Forme** : %s. **Extrait** : %s%s." % (f["form_label"], _excerpt(f), vals),
                "- **Lignes** : %s (%s%s)." % (_plural(f["count"], "ligne", "lignes"), refs, more)]
        if f["also"]:
            out.append("- **Aussi dans la même URL** : %s." % ", ".join(f["also"]))
        if f["partial"]:
            out.append("- **Fuite partielle** : la ligne a été coupée au milieu de la clé par le handler de logs. "
                       "Une partie suffit à reconnaître la clé, et la clé entière a pu fuir ailleurs : traite-la "
                       "comme une fuite complète.")
        elif f["partial_lines"]:
            out.append("- Dont %s où la clé est coupée en fin de ligne." % _plural(f["partial_lines"], "ligne",
                                                                                   "lignes"))
        out += ["- **Ligne masquée** : `%s`" % f["masked_line"],
                "- **Cause** : %s" % f["cause"],
                "- **Correctif** : %s" % f["fix"],
                "- **Ensuite** : %s" % f["after"]]
    out += ["", "## Pour que ça ne revienne pas", "",
            "1. Corrige la cause de chaque fuite, ci-dessus.",
            "2. Ajoute un filtre qui masque ces formes avant l'écriture du log : "
            "`python3 leak_scan.py --filter python > leak_filter.py` (une classe `logging.Filter` à poser sur "
            "chaque handler) ou `python3 leak_scan.py --filter node > redact.js`.",
            "3. Pour partager ce log sans les secrets : `python3 leak_scan.py <log> --redact <copie>`."]
    if res.get("redacted"):
        out += ["", "Copie masquée écrite : `%s` (%s)." % (
            res["redacted"]["path"], _plural(res["redacted"]["lines_changed"], "ligne modifiée", "lignes modifiées"))]
    out += ["", "**%s**" % ROTATE_ALL]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- filters

PY_HEAD = '''"""Log filter generated by leak-scan %s (https://github.com/Darius-Tokam/ai-packs, MIT).

Masks API keys, tokens, presigned URL signatures, OAuth secrets, auth headers
and client email addresses before a log record is written: the message, its
arguments and the traceback (logger.exception included). Same rules as the scan.

Save this file as leak_filter.py in your project, then put the filter on every
handler (a filter on a logger does not see the records of its child loggers):

    import logging
    from leak_filter import RedactSecretsFilter
    for handler in logging.getLogger().handlers:
        handler.addFilter(RedactSecretsFilter())

Django: in settings.LOGGING, add
    "filters": {"redact": {"()": "yourapp.leak_filter.RedactSecretsFilter"}},
then "filters": ["redact"] on each handler.

It masks what goes through logging only. print() is not covered, and the access
log of gunicorn or uvicorn has its own handlers: give them the same filter
(gunicorn --log-config-dict, uvicorn --log-config).
"""
import logging

'''

PY_TAIL = '''

class RedactSecretsFilter(logging.Filter):
    """Masks leaked values in the message, its arguments and the traceback of each record."""

    def filter(self, record):
        try:
            msg = record.getMessage()
            clean = redact(msg)
            if clean != msg:
                record.msg, record.args = clean, ()
            if record.exc_info and not record.exc_text:
                record.exc_text = logging.Formatter().formatException(record.exc_info)
            if record.exc_text:
                record.exc_text = redact(record.exc_text)
            if record.stack_info:
                record.stack_info = redact(record.stack_info)
        except Exception:  # a log filter must never break logging
            pass
        return True
'''

NODE_TEMPLATE = r"""'use strict';
// Log redaction generated by leak-scan __VERSION__ (https://github.com/Darius-Tokam/ai-packs, MIT).
// Masks API keys, tokens, presigned URL signatures, OAuth secrets, auth headers and
// client email addresses before a log line is written. Same rules as the scan. Node 16+.
//
// Save as redact.js, then either mask everything written to stdout and stderr:
//   require('./redact').install();
// or pass a pino destination:
//   const { redactSecrets } = require('./redact');
//   const logger = pino({}, { write: (s) => process.stdout.write(redactSecrets(s)) });

const D = __DATA__;
const rx = ([src, flags], extra = '') => new RegExp(src, flags + extra);
const RULES = D.rules.map(([prio, rule, src, flags]) => [prio, rule, new RegExp(src, flags + 'gd')]);
const COOKIE = rx(D.cookie, 'gd');
const COOKIE_PAIR = rx(D.cookie_pair, 'gd');
const COOKIE_NAME = rx(D.cookie_name);
const CSRF = rx(D.csrf);
const SHAPE_FULL = new RegExp('^(?:' + D.shape_any + ')$');
const PREFIX = new RegExp('^(?:' + D.prefixes + ')');
const TAIL = new RegExp(D.tail, 'y');
const MASKED = rx(D.masked);
const TEMPLATE = rx(D.template);
const PLACEHOLDERS = new Set(D.placeholders);
const HAS_DIGIT = /[0-9]/;
const HAS_ALPHA = /[A-Za-z]/;
const HAS_UPPER = /[A-Z]/;
const HAS_LOWER = /[a-z]/;
const KEYLIKE = /^[0-9A-Za-z_\-]{20,}$/;
const DIGITS = /^[0-9]+$/;
const NOT_SECRET_PREFIX = rx(D.not_secret_prefix);
const SAS = rx(D.sas);
const LEGACY_SIG = rx(D.legacy_sig);
const OAUTH_PATH = rx(D.oauth_path);
const NOREPLY = new RegExp('^(?:' + D.noreply[0] + ')', D.noreply[1]);
const RESERVED = D.reserved;
const NO_EMAIL_TLD = new Set(D.no_email_tld);
const STOPS = D.stops;

function tok(line, s, e) {
  let i = s;
  while (i > 0 && !STOPS.includes(line[i - 1])) i--;
  let j = e;
  while (j < line.length && !STOPS.includes(line[j])) j++;
  return line.slice(i, j);
}

const path = (t) => t.split(/[?#]/)[0];

function emailOk(v) {
  const w = v.split('%40').join('@');
  const at = w.lastIndexOf('@');
  const local = w.slice(0, at).toLowerCase();
  const d = w.slice(at + 1).toLowerCase();
  if (NO_EMAIL_TLD.has(d.slice(d.lastIndexOf('.') + 1))) return false;
  if (RESERVED.some((r) => d === r || d.endsWith('.' + r))) return false;
  if (d.endsWith('gserviceaccount.com') || d.endsWith('noreply.github.com')) return false;
  return !(local === 'git' || NOREPLY.test(local));
}

function check(rule, name, v, line, s, e) {
  if (rule === 'email') return emailOk(v);
  if (!v || MASKED.test(v) || TEMPLATE.test(v) || PLACEHOLDERS.has(v.toLowerCase())) return false;
  if (rule === 'shape') return true;
  if (rule === 'partial') return v.length >= 8 && !SHAPE_FULL.test(v);
  if (rule === 'userinfo') return v.length >= 4 && !(DIGITS.test(v) && v.length <= 5);
  if (rule === 'auth-header' || rule === 'key-header' || rule === 'cookie') return v.length >= 8;
  if (rule === 'presigned') {
    const t = tok(line, s, e);
    if (name === 'sig') return v.length >= 16 && SAS.test(t);
    if (name === 'Signature') return v.length >= 16 && LEGACY_SIG.test(t);
    return v.length >= 16;
  }
  if (rule === 'oauth-code') return v.length >= 10 && !DIGITS.test(v) && OAUTH_PATH.test(path(tok(line, s, e)));
  const n = name.toLowerCase().replace(/-/g, '_');
  if (n === 'key') {
    return SHAPE_FULL.test(v)
      || (KEYLIKE.test(v) && v.split(/[-_]/).some((g) => g.length >= 8 && HAS_ALPHA.test(g) && HAS_DIGIT.test(g)));
  }
  if (n.endsWith('token') && NOT_SECRET_PREFIX.test(n.slice(0, -5))) return false;
  if (n.endsWith('password') || n.endsWith('passwd')) return v.length >= 4;
  if (v.includes(' ') || v.includes('\t')) return false;
  return v.length >= 8 && (HAS_DIGIT.test(v) || (v.length >= 16 && HAS_UPPER.test(v) && HAS_LOWER.test(v)));
}

function findHits(line) {
  const c = [];
  RULES.forEach(([prio, rule, re], order) => {
    for (const m of line.matchAll(re)) {
      const [s, e] = m.indices.groups.v;
      const name = m.groups.n === undefined ? '' : m.groups.n;
      if (check(rule, name, m.groups.v, line, s, e)) c.push([prio, s, e, order, rule, name, m.groups.v]);
    }
  });
  for (const m of line.matchAll(COOKIE)) {
    const base = m.indices.groups.c[0];
    for (const k of m.groups.c.matchAll(COOKIE_PAIR)) {
      const name = k.groups.n;
      const v = k.groups.v;
      if (COOKIE_NAME.test(name) && !CSRF.test(name) && check('cookie', name, v, line, 0, 0)) {
        const [s, e] = k.indices.groups.v;
        c.push([1, base + s, base + e, 99, 'cookie', name, v]);
      }
    }
  }
  c.sort((a, b) => a[0] - b[0] || a[1] - b[1] || (a[1] - a[2]) - (b[1] - b[2]) || a[3] - b[3]);
  const kept = [];
  for (const h of c) if (kept.every((k) => h[2] <= k[1] || h[1] >= k[2])) kept.push(h);
  kept.sort((a, b) => a[1] - b[1]);
  return kept.map(([, s, e, , rule, name, v]) => {
    TAIL.lastIndex = e;
    const partial = rule !== 'email' && PREFIX.test(v) && !SHAPE_FULL.test(v) && TAIL.test(line);
    return { start: s, end: e, rule, name, value: v, partial };
  });
}

function redactLine(line) {
  const hits = findHits(line);
  for (let i = hits.length - 1; i >= 0; i--) {
    const h = hits[i];
    line = line.slice(0, h.start) + (h.rule === 'email' ? '[REDACTED_EMAIL]' : '[REDACTED]') + line.slice(h.end);
  }
  return line;
}

function redactSecrets(text) {
  return String(text).split('\n').map(redactLine).join('\n');
}

function install(streams = [process.stdout, process.stderr]) {
  for (const s of streams) {
    const write = s.write.bind(s);
    s.write = (chunk, ...rest) => write(
      typeof chunk === 'string' ? redactSecrets(chunk)
        : Buffer.isBuffer(chunk) ? redactSecrets(chunk.toString('utf8')) : chunk, ...rest);
  }
}

module.exports = { redactSecrets, redactLine, findHits, install };
"""


def _js(rx):
    return [rx.pattern.replace("(?P<", "(?<"), "i" if rx.flags & re.IGNORECASE else ""]


def filter_code(lang):
    if lang == "python":
        src = Path(__file__).read_text(encoding="utf-8")
        a = src.index("# ---- leak-scan core: begin ----")
        b = src.index("# ---- leak-scan core: end ----") + len("# ---- leak-scan core: end ----")
        return PY_HEAD % VERSION + src[a:b] + "\n" + PY_TAIL
    data = {
        "rules": [[prio, rule] + _js(r) for prio, rule, r in _RULES],
        "cookie": _js(_COOKIE), "cookie_pair": _js(_COOKIE_PAIR), "cookie_name": _js(_COOKIE_NAME),
        "csrf": _js(_CSRF), "shape_any": _SHAPE_ANY, "prefixes": _PREFIXES, "tail": _TAIL_SRC,
        "masked": _js(_MASKED), "template": _js(_TEMPLATE), "placeholders": list(_PLACEHOLDERS),
        "not_secret_prefix": _js(_NOT_SECRET_PREFIX), "sas": _js(_SAS), "legacy_sig": _js(_LEGACY_SIG),
        "oauth_path": _js(_OAUTH_PATH), "noreply": _js(_NOREPLY), "reserved": list(_RESERVED),
        "no_email_tld": list(_NO_EMAIL_TLD), "stops": _STOPS,
    }
    return NODE_TEMPLATE.replace("__VERSION__", VERSION).replace("__DATA__", json.dumps(data, indent=1))


# ---------------------------------------------------------------- main

def _fail(msg):
    print("leak-scan: " + msg, file=sys.stderr)
    return 2


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(
        prog="leak_scan.py",
        description="Find API keys, tokens, signed URLs and client emails exposed in logs. "
                    "Exit 0: no leak, 1: leak(s) found, 2: bad input.")
    ap.add_argument("files", nargs="*", help="log files (none or '-': read stdin)")
    ap.add_argument("--json", action="store_true", help="JSON report instead of Markdown")
    ap.add_argument("--redact", metavar="OUT",
                    help="also write a copy of the log with every leak masked (a folder when several files)")
    ap.add_argument("--filter", choices=("python", "node"),
                    help="print a ready-to-paste log filter (logging.Filter class or Node module) and exit")
    args = ap.parse_args(argv)

    if args.filter:
        if args.files:
            print("leak-scan: --filter prints the filter only, the files are not read", file=sys.stderr)
        sys.stdout.write(filter_code(args.filter))
        return 0

    raw = []
    if not args.files or args.files == ["-"]:
        if sys.stdin is None or sys.stdin.isatty():
            ap.print_usage(sys.stderr)
            return _fail("give a log file, or send the log on stdin")
        raw.append(("stdin", sys.stdin.buffer.read()))
    else:
        for f in args.files:
            p = Path(f)
            if not p.is_file():
                return _fail("file not found: %s" % f)
            try:
                raw.append((f, p.read_bytes()))
            except OSError as e:
                return _fail("cannot read %s: %s" % (f, e.strerror))
    for name, data in raw:
        if b"\x00" in data:
            return _fail("%s is not a text log (NUL bytes)" % name)
    texts = [(name, data.decode("utf-8", "surrogateescape")) for name, data in raw]
    res = scan(texts)

    if args.redact:
        out = Path(args.redact)
        try:
            if len(texts) == 1:
                targets = [out]
            else:
                out.mkdir(parents=True, exist_ok=True)
                targets = [out / ("%d-%s" % (i + 1, Path(name).name)) for i, (name, _) in enumerate(texts)]
            changed = 0
            for (name, text), target in zip(texts, targets):
                lines = text.split("\n")
                clean = [redact_line(line) for line in lines]
                changed += sum(a != b for a, b in zip(lines, clean))
                target.write_bytes("\n".join(clean).encode("utf-8", "surrogateescape"))
        except OSError as e:
            return _fail("cannot write %s: %s" % (args.redact, e.strerror))
        res["redacted"] = {"path": str(out), "lines_changed": changed}

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        sys.stdout.write(to_markdown(res))
    return 1 if res["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
