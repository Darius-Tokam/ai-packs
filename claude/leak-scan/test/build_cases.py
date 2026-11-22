"""Rebuild the leak-scan test logs.

    python build_cases.py /tmp/leak-cases

Writes, in the given folder:
  app.log     about 2 000 lines of a production-like log (Railway-like
              timestamps, Django, gunicorn, Celery and Node lines, tracebacks)
              with 10 planted leaks, 2 per form, and every trap that must not
              be flagged;
  clean.log   about 500 lines of the same kind with the traps and no leak;
  formats.log 52 single lines in other formats (nginx, curl, Stripe, Sentry,
              Kubernetes, CI, systemd): 17 leaks and 35 lines that are not;
  truth.json  the ground truth: for each planted leak its form, whether it is
              partial, the exact lines that hold it and its values; for each
              trap the lines that hold it.

Every fake secret is assembled at run time from short pieces and random
characters drawn with a fixed seed, so no file of the repo holds a string that
looks like a real key, and the generated logs stay in the given folder: never
commit them. Names, domains and addresses are invented. Standard library only.
"""
import base64
import json
import random
import string
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20260827
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/leak-cases")
rng = random.Random(SEED)

ALNUM = string.ascii_letters + string.digits
URLSAFE = ALNUM + "-_"
HEX = "0123456789abcdef"
UPPER_DIGITS = string.ascii_uppercase + string.digits
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def rand(n, alphabet=ALNUM):
    return "".join(rng.choice(alphabet) for _ in range(n))


def fake_uuid():
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def b64url(obj):
    return base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":")).encode()).decode().rstrip("=")


def fake_jwt(sub):
    return ".".join([b64url({"alg": "HS256", "typ": "JWT"}), b64url({"sub": sub, "exp": 1789000000}), rand(43, URLSAFE)])


# Fake secrets, assembled from pieces: the prefixes are split so that no source
# line looks like a key.
GOOGLE = "AI" + "za"
GEMINI_KEY = GOOGLE + "Sy" + rand(33, URLSAFE)
PAGESPEED_KEY = GOOGLE + "Sy" + rand(33, URLSAFE)
AWS_KEY_ID = "AK" + "IA" + rand(16, UPPER_DIGITS)
S3_SIGS = [rand(64, HEX) for _ in range(5)]
GCS_SIGS = [rand(512, HEX) for _ in range(4)]
META_TOKENS = ["EA" + "AG" + rand(176) for _ in range(3)]
META_CLIENT_SECRET = rand(32, HEX)
META_CODES = ["AQ" + rand(214, URLSAFE) for _ in range(2)]
JWTS = [fake_jwt("user_4821"), fake_jwt("user_77")]
PARTNER_KEY = "wk" + "_" + rand(38)
EMAIL_A = "lea.b%d" % rng.randint(10, 99) + "@" + "courriel-client.fr"
EMAIL_B = "m.ngo%d" % rng.randint(10, 99) + "@" + "boite-perso.net"

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
PSI_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?"
UAS = ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
       "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
       "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
       "python-requests/2.32.3", "Railway-Healthcheck/1.0"]


class Log:
    def __init__(self, start, host):
        self.lines, self.t, self.host = [], start, host

    def tick(self, lo=0.05, hi=9.0):
        self.t += timedelta(seconds=rng.uniform(lo, hi))

    def iso(self):
        return self.t.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (self.t.microsecond // 1000)

    def dj(self):
        return self.t.strftime("%Y-%m-%d %H:%M:%S,") + "%03d" % (self.t.microsecond // 1000)

    def clf(self):
        return "%02d/%s/%d:%s +0000" % (self.t.day, MONTHS[self.t.month - 1], self.t.year, self.t.strftime("%H:%M:%S"))

    def ms(self):
        return int(self.t.timestamp() * 1000)

    def put(self, *msgs):
        ts, start = self.iso(), len(self.lines) + 1
        self.lines.extend("%s %s" % (ts, m) for m in msgs)
        return list(range(start, start + len(msgs)))

    # line makers, each moves the clock first
    def access(self, path, status=200, method="GET", ref="-"):
        self.tick()
        ip = "10.250.%d.%d" % (rng.randint(0, 255), rng.randint(1, 254))
        size = 0 if status in (301, 302, 304) else rng.randint(120, 48000)
        return self.put('%s - - [%s] "%s %s HTTP/1.1" %d %d "%s" "%s"' % (
            ip, self.clf(), method, path, status, size, ref, rng.choice(UAS)))

    def django(self, level, logger, msg):
        self.tick()
        return self.put("%s %s %s %s" % (level, self.dj(), logger, msg))

    def pino(self, level, msg, **fields):
        self.tick()
        rec = {"level": level, "time": self.ms(), "pid": 7, "hostname": self.host, "reqId": fake_uuid()}
        rec.update(fields)
        rec["msg"] = msg
        return self.put(json.dumps(rec, separators=(",", ":")))

    def raw(self, *msgs):
        self.tick()
        return self.put(*msgs)


# ---------------------------------------------------------------- background traffic

def background(log):
    n = rng.randint(1, 900)
    k = rng.random()
    if k < 0.34:
        path = rng.choice(["/health", "/api/sites/%d/articles" % n, "/api/articles/%d" % n, "/dashboard/",
                           "/api/sites/%d/rankings?range=30d" % n, "/static/app.%s.js" % rand(8, HEX),
                           "/static/app.%s.css" % rand(8, HEX), "/api/notifications/unread", "/favicon.ico",
                           "/api/sites/%d/keywords?page=1&per_page=50" % n])
        return log.access(path, rng.choice([200] * 12 + [304, 404]))
    if k < 0.58:
        return log.django(*rng.choice([
            ("INFO", "articles.tasks", "article %d generated in %.1fs" % (n, rng.uniform(1, 9))),
            ("INFO", "seo.rank", "snapshot site=%d keywords=%d" % (n, rng.randint(20, 400))),
            ("INFO", "seo.crawl", "crawled %d pages for site %d" % (rng.randint(3, 300), n)),
            ("INFO", "billing.sync", "webhook invoice.paid processed in %.2fs" % rng.uniform(0.1, 2)),
            ("WARNING", "django.request", "Not Found: /wp-login.php"),
            ("INFO", "django.request", "request_id=%s path=/api/sites/%d/ status=200" % (fake_uuid(), n)),
        ]))
    if k < 0.74:
        log.tick()
        return log.put("[%s: INFO/ForkPoolWorker-%d] Task seo.tasks.refresh_rankings[%s] succeeded in %.2fs: None" % (
            log.dj(), rng.randint(1, 4), fake_uuid(), rng.uniform(0.2, 8)))
    method, url = rng.choice([("GET", "/api/posts?limit=20"), ("GET", "/api/posts/%d" % n),
                              ("POST", "/api/posts/%d/publish" % n), ("GET", "/api/me")])
    return log.pino(30, "request completed", req={"method": method, "url": url},
                    res={"statusCode": rng.choice([200, 200, 200, 201, 304])}, responseTime=rng.randint(2, 380))


def boot(log, kind):
    out = log.raw("Starting Container")
    if kind == "django":
        out += log.raw("[%s] [1] [INFO] Starting gunicorn 22.0.0" % log.t.strftime("%Y-%m-%d %H:%M:%S +0000"))
        out += log.raw("[%s] [1] [INFO] Listening at: http://0.0.0.0:8080 (1)" % log.t.strftime("%Y-%m-%d %H:%M:%S +0000"))
    else:
        out += log.pino(30, "Server listening on 0.0.0.0:8080")
    return out


# ---------------------------------------------------------------- the 10 planted leaks

def gemini_429(log):
    """L1: the Gemini HTTPError, one line with the key on each failed call of the 429 loop."""
    log.tick()
    return log.put(
        "ERROR %s seo.gemini Gemini call failed for article %d" % (log.dj(), rng.randint(100, 999)),
        "Traceback (most recent call last):",
        '  File "/app/seo/gemini_client.py", line 58, in generate',
        "    resp.raise_for_status()",
        '  File "/usr/local/lib/python3.12/site-packages/requests/models.py", line 1024, in raise_for_status',
        "    raise HTTPError(http_error_msg, response=self)",
        "requests.exceptions.HTTPError: 429 Client Error: Too Many Requests for url: %s?key=%s" % (GEMINI_URL, GEMINI_KEY),
    )[-1:]


def pagespeed_cut(log, prefix):
    """L2: a PageSpeed error whose handler truncates the message at 120 characters, inside the key."""
    msg = (prefix + PSI_URL + "url=https%3A%2F%2F" + rng.choice(["a.example", "b.example"]) + "&key=" + PAGESPEED_KEY)[:120]
    visible = msg[msg.index("&key=") + 5:]
    assert 8 <= len(visible) < len(PAGESPEED_KEY), visible
    return log.django("WARNING", "seo.pagespeed", msg), visible


def s3_presigned(log, i):
    """L3: an S3 presigned URL (24 h) logged with its signature; 5 objects, one signer."""
    log.tick()
    url = ("https://app-media-prod.s3.eu-west-3.amazonaws.com/renders/2026/09/15/visual-%d.png?"
           "X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=%s%%2F20260915%%2Feu-west-3%%2Fs3%%2Faws4_request"
           "&X-Amz-Date=20260915T%sZ&X-Amz-Expires=86400&X-Amz-SignedHeaders=host&X-Amz-Signature=%s") % (
        rng.randint(1000, 9999), AWS_KEY_ID, log.t.strftime("%H%M%S"), S3_SIGS[i])
    return log.put("INFO %s media.renders visual ready %s" % (log.dj(), url))


def gcs_signed(log, i):
    """L4: a GCS V4 signed URL (48 h) logged by a Node worker; 4 objects, one service account."""
    log.tick()
    url = ("https://storage.googleapis.com/app-renders-prod/2026/09/15/carousel-%d-%d.png?"
           "X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Credential=renders-signer%%40app-prod-41.iam.gserviceaccount.com"
           "%%2F20260915%%2Fauto%%2Fstorage%%2Fgoog4_request&X-Goog-Date=20260915T%sZ&X-Goog-Expires=172800"
           "&X-Goog-SignedHeaders=host&X-Goog-Signature=%s") % (rng.randint(10, 99), i + 1, log.t.strftime("%H%M%S"), GCS_SIGS[i])
    return log.pino(30, "carousel slide uploaded", url=url)


def oauth_token_callback(log, i):
    """L5: an OAuth callback that receives access_token in its query string, in the access log."""
    return log.access("/auth/meta/callback/?access_token=%s&data_access_expiration_time=1797000000&expires_in=5183944"
                      "&state=st_%s" % (META_TOKENS[i], rand(10)), 302, ref="https://www.facebook.com/")


def oauth_code_exchange(log, i):
    """L6: the token exchange logged by urllib3 at DEBUG, with client_secret and code in the URL."""
    log.tick()
    return log.put('DEBUG %s urllib3.connectionpool https://graph.facebook.com:443 "GET /v19.0/oauth/access_token?'
                   'client_id=1093874412345678&redirect_uri=https%%3A%%2F%%2Fapp.example.net%%2Fauth%%2Fmeta%%2Fcallback%%2F'
                   '&client_secret=%s&code=%s HTTP/1.1" 200 None' % (log.dj(), META_CLIENT_SECRET, META_CODES[i]))


def bearer_dump(log, i):
    """L7: pino logs the request with its headers: Authorization: Bearer <user JWT>."""
    return log.pino(30, "incoming request", req={
        "method": "POST", "url": "/api/posts/schedule",
        "headers": {"host": "api.app.example.net", "authorization": "Bearer " + JWTS[i % 2],
                    "content-type": "application/json", "user-agent": "Mozilla/5.0"}})


def api_key_dump(log):
    """L8: console.log(req.headers) of a webhook, printed by Node on several lines."""
    log.tick()
    out = log.put("incoming webhook headers {",
                  "  host: 'hooks.app.example.net',",
                  "  'user-agent': 'partner-sync/2.1',",
                  "  'x-api-key': '%s'," % PARTNER_KEY,
                  "  'content-type': 'application/json',",
                  "  'x-request-id': '%s'" % fake_uuid(),
                  "}")
    return out[3:4]


def email_a(log, i):
    """L9: a client email in a Django log line."""
    if i == 0:
        return log.django("INFO", "shop.checkout", "order %d confirmed for %s" % (rng.randint(8000, 8999), EMAIL_A))
    return log.django("INFO", "mailer", "receipt sent to %s" % EMAIL_A)


def email_b(log, i):
    """L10: a client email in a Node log line."""
    if i == 0:
        return log.pino(30, "invoice sent", to=EMAIL_B, invoiceId="inv_2026_0915_%d" % rng.randint(10, 99))
    return log.pino(40, "bounce received", recipient=EMAIL_B)


# ---------------------------------------------------------------- traps (must not be flagged)

TRAPS = {
    "T01": ("sort_key=created_at", lambda log: log.access("/api/projects?sort_key=created_at&order=desc")),
    "T02": ("?page=2&per_page=50", lambda log: log.access("/api/sites/%d/keywords?page=2&per_page=50" % rng.randint(1, 99))),
    "T03": ("token_count=1532, max_tokens=", lambda log: log.django(
        "INFO", "seo.gemini", "usage model=gemini-2.0-flash prompt_tokens=812 token_count=1532 max_tokens=2048")),
    "T04": ("SHA git (40 et 7 caractères)", lambda log: log.raw("[deploy] commit %s (%s) \"fix rankings cron\"" % (
        rand(40, HEX), rand(7, HEX)))),
    "T05": ("UUID d'identifiant de requête", lambda log: log.raw("request headers: host=api.app.example.net x-request-id=%s"
                                                                " request_id=%s" % (fake_uuid(), fake_uuid()))),
    "T06": ("empreinte sha256 et ETag", lambda log: log.django(
        "INFO", "media.storage", "upload stored sha256=%s etag=\"%s\" size=%d" % (rand(64, HEX), rand(32, HEX),
                                                                                 rng.randint(1000, 90000)))),
    "T07": ("key= vide", lambda log: log.access("/api/search?q=seo+audit&key=", 400)),
    "T08": ("valeurs déjà masquées ([REDACTED], ***, ****abcd)", lambda log: (
        log.django("ERROR", "seo.gemini", "retry failed for url: %s?key=[REDACTED]" % GEMINI_URL)
        + log.django("DEBUG", "api.auth", "forwarding request with Authorization: Bearer ***")
        + log.django("INFO", "partner.sync", "configured api_key=****a1b2 endpoint=https://partner.example.net/v2")
        + log.pino(30, "login attempt", body={"email": "[REDACTED]", "password": "********"}))),
    "T09": ("le mot password dans une phrase", lambda log: (
        log.django("INFO", "accounts", "password reset email sent to user %d" % rng.randint(1000, 9999))
        + log.django("WARNING", "accounts", "invalid password for user %d (attempt 2/5)" % rng.randint(10, 99)))),
    "T10": ("e-mails réservés ou de test, expéditeur no-reply", lambda log: (
        log.django("INFO", "accounts", "invitation sent to support@example.com and qa+signup@example.org")
        + log.django("INFO", "accounts", "test account jane@staging.test bounced to ops@alerts.invalid")
        + log.django("INFO", "mailer", "receipt sent from no-reply@notify-mail.io (reply-to noreply@notify-mail.io)"))),
    "T11": ("callback OAuth refusé, sans code", lambda log: log.access(
        "/auth/meta/callback/?error=access_denied&error_reason=user_denied&state=st_%s" % rand(10), 302)),
    "T12": ("code= hors OAuth (code promo, code HTTP)", lambda log: (
        log.access("/api/checkout?code=WELCOME10")
        + log.access("/api/coupons/apply?code=BLACKFRIDAY2026VIP&cart=%d" % rng.randint(100, 999))
        + log.django("WARNING", "seo.rank", "upstream returned code=503 for /v1/rankings"))),
    "T13": ("URL S3 publique sans signature", lambda log: log.django(
        "INFO", "media.renders", "logo url https://app-media-prod.s3.eu-west-3.amazonaws.com/public/logo.png")),
    "T14": ("logo@2x.png et git@github.com", lambda log: (
        log.access("/static/img/logo@2x.png") + log.raw("[build] cloning git@github.com:acme-labs/app.git"))),
    "T15": ("PageSpeed coupé avant la clé, timeout sans clé", lambda log: (
        log.django("WARNING", "seo.pagespeed", ("PageSpeed fetch failed for " + PSI_URL + "url=https%3A%2F%2Fshop.example.com"
                                                "&strategy=mobile&category=performance&key=" + PAGESPEED_KEY)[:120])
        + log.raw("requests.exceptions.ReadTimeout: HTTPSConnectionPool(host='www.googleapis.com', port=443): "
                  "Read timed out. (read timeout=30)"))),
    "T16": ("phrases sur l'authentification", lambda log: (
        log.django("WARNING", "api.auth", "Authorization header missing for /api/posts")
        + log.pino(40, "401 invalid or expired token", userId=12))),
    "T17": ("cookie csrftoken", lambda log: log.django(
        "DEBUG", "api.debug", "cookie: csrftoken=%s; django_language=fr" % rand(32))),
    "T18": ("jeton de pagination next_page_token", lambda log: log.access(
        "/api/feed?next_page_token=%s&limit=20" % rand(40))),
    "T19": ("f-string de l'URL dans une trace", lambda log: (
        log.django("ERROR", "seo.gemini", "client init failed")
        + log.put("Traceback (most recent call last):",
                  '  File "/app/seo/gemini_client.py", line 51, in generate',
                  '    url = f"{GEMINI_URL}:generateContent?key={api_key}"',
                  "TypeError: unsupported format string passed to NoneType.__format__"))),
}


def run_events(log, events, truth_traps):
    for kind, arg in events:
        if kind == "bg":
            background(log)
        elif kind == "trap":
            truth_traps.setdefault(arg, []).extend(TRAPS[arg][1](log))
        else:
            arg()


def build_app():
    log = Log(datetime(2026, 9, 15, 6, 2, 11, 482000, tzinfo=timezone.utc), "web-6f9c8d7b5-x2kqp")
    leaks = {k: [] for k in ("L01", "L02", "L03", "L04", "L05", "L06", "L07", "L08", "L09", "L10")}
    visible = []
    traps = {}
    boot(log, "django")

    def add(lid, fn):
        return lambda: leaks[lid].extend(fn())

    def add_cut(prefix):
        def go():
            lines, vis = pagespeed_cut(log, prefix)
            leaks["L02"].extend(lines)
            visible.append(vis)
        return go

    planted = [add("L01", lambda: gemini_429(log)) for _ in range(150)]
    planted += [add_cut("PSI 500 for "), add_cut("PSI 500 for "), add_cut("PSI: ")]
    planted += [add("L03", lambda i=i: s3_presigned(log, i)) for i in range(5)]
    planted += [add("L04", lambda i=i: gcs_signed(log, i)) for i in range(4)]
    planted += [add("L05", lambda i=i: oauth_token_callback(log, i)) for i in range(3)]
    planted += [add("L06", lambda i=i: oauth_code_exchange(log, i)) for i in range(2)]
    planted += [add("L07", lambda i=i: bearer_dump(log, i)) for i in range(4)]
    planted += [add("L08", lambda: api_key_dump(log)) for _ in range(3)]
    planted += [add("L09", lambda i=i: email_a(log, i)) for i in range(2)]
    planted += [add("L10", lambda i=i: email_b(log, i)) for i in range(2)]
    # the first part of the day is calm: the quota runs out later and the 429 loop starts
    early = [("bg", None)] * 180 + [("trap", t) for t in TRAPS]
    rng.shuffle(early)
    late = [("bg", None)] * 640 + [("leak", fn) for fn in planted] + [("trap", t) for t in TRAPS for _ in range(2)]
    rng.shuffle(late)
    run_events(log, early + late, traps)
    return log, leaks, visible, traps


def build_clean():
    log = Log(datetime(2026, 9, 16, 6, 0, 3, 117000, tzinfo=timezone.utc), "web-6f9c8d7b5-q8wzn")
    traps = {}
    boot(log, "node")
    events = [("bg", None)] * 430 + [("trap", t) for t in TRAPS for _ in range(2)]
    rng.shuffle(events)
    run_events(log, events, traps)
    return log, traps


def build_formats():
    """Single lines in formats the app log does not use (nginx, curl, Stripe, Sentry, Kubernetes, CI, systemd).
    Each line is either a leak or not: the scan must flag exactly the first group."""
    hexa = HEX
    lower_digits = string.ascii_lowercase + string.digits
    leak = [
        "GET /maps/api/geocode/json?address=Paris&key=" + GOOGLE + "Sy" + rand(33, URLSAFE),
        "Authorization: Basic " + base64.b64encode(("admin:" + rand(12)).encode()).decode(),
        'curl -H "Authorization: Bearer sk-' + "proj-" + rand(48) + '" https://api.example.net/v1/chat',
        "redis://default:" + rand(24) + "@redis.railway.internal:6379",
        "export GITHUB_TOKEN=gh" + "p_" + rand(36),
        '{"apiKey":"' + rand(12) + "9" + rand(12) + '"}',
        "token refresh ok access_token=ya" + "29." + rand(60, URLSAFE),
        "slack post failed token=xo" + "xb-" + rand(10, string.digits) + "-" + rand(24),
        "aws_secret_access_key=" + rand(40),
        "GET /v2/forecast?apikey=" + rand(32, hexa) + "&q=Lyon",
        "GET /mail/v3/send?key=key-" + rand(32, lower_digits),
        "Set-Cookie: sessionid=" + rand(32) + "; HttpOnly; Path=/",
        "https://acct.blob.core.windows.net/c/a.png?sv=2024-05-04&se=2026-09-16T10%3A00%3A00Z&sr=b&sp=r&sig="
        + rand(43) + "%3D",
        "https://d111.cloudfront.net/a.png?Expires=1789000000&Signature=" + rand(120) + "&Key-Pair-Id=K2JCJMDEHXQW5F",
        "user=jean.d" + str(rng.randint(10, 99)) + "@" + "entreprise-cliente.fr action=login",
        "GET /oauth2/callback?code=4/0Ae" + rand(70, URLSAFE) + "&scope=email HTTP/1.1",
        '"password": "' + rand(10) + '"',
    ]
    clean = [
        "stripe evt_1PqXyZAbCdEf123 checkout.session.completed cus_QwErTy123 pi_3PqXyZAbCdEf456",
        "stripe publishable pk_" + "live_" + rand(24),
        "GET /api/v1/items?sort=-created_at&page_size=100 HTTP/1.1",
        "Cache restored from key: node-cache-Linux-x64-npm-" + rand(40, hexa),
        "restore cache key=build-cache-v3-linux-2026",
        "cache key=user_profile_12345_v2 hit",
        "release key=release-2026-09-15-build-4821",
        'ETag: W/"5e-abc123"',
        "x-amz-request-id: 4442587FB7D0A2F9 x-amz-id-2: " + rand(40),
        "traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        "session_id=" + fake_uuid(),
        "Set-Cookie: session=; Max-Age=0; Path=/",
        "Set-Cookie: sessionid=deleted; expires=Thu, 01 Jan 1970 00:00:00 GMT",
        "password_changed=true user=42",
        "GET /login?next=%2Fdashboard%3Ftoken%3Dabc123def456 HTTP/1.1",
        'WWW-Authenticate: Bearer realm="api", error="invalid_token"',
        "INFO token refreshed for user 42",
        "api_key_id=12 api_key_name=prod",
        '{"password_hash": "pbkdf2_sha256$600000$' + rand(22) + '", "token_type": "Bearer", "expires_in": 3600}',
        "client_id=1234567890-abc.apps.googleusercontent.com",
        'Error from server (NotFound): secrets "db-credentials" not found',
        'level=info msg="loaded config" path=/etc/app/config.yaml',
        "set key=value pairs in the form",
        "docker pull ghcr.io/org/app@sha256:" + rand(64, hexa),
        "npm install @scope/pkg@1.2.3",
        '{"request":{"headers":{"Authorization":"[Filtered]","Cookie":"[Filtered]"}}}',
        "X-Api-Key: ${PARTNER_API_KEY}",
        "Authorization: Bearer YOUR_TOKEN",
        "Authorization: Bearer <token>",
        "token=expired_session_retry",
        "Created symlink /etc/systemd/system/multi-user.target.wants/container-getty@1.service",
        "upload key=uploads/2026/09/15/a.png bucket=media",
        "redis GET key=session:4821:profile",
        "stripe.error.AuthenticationError: Invalid API Key provided: sk_" + "live_" + "*" * 20 + "abcd",
        '{"level":"warn","auth_token":"Missing Or Expired Session","path":"/api/me"}',
    ]
    lines = [(t, True) for t in leak] + [(t, False) for t in clean]
    rng.shuffle(lines)
    return lines


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    app, leaks, visible, traps = build_app()
    clean, clean_traps = build_clean()
    formats = build_formats()
    (OUT / "app.log").write_text("\n".join(app.lines) + "\n", encoding="utf-8")
    (OUT / "clean.log").write_text("\n".join(clean.lines) + "\n", encoding="utf-8")
    (OUT / "formats.log").write_text("\n".join(t for t, _ in formats) + "\n", encoding="utf-8")
    spec = {
        "L01": ("clé Gemini dans l'URL, message de HTTPError répété par la boucle de 429", "url-secret", False,
                [GEMINI_KEY]),
        "L02": ("clé PageSpeed coupée par un handler qui tronque à 120 caractères", "url-secret", True,
                [PAGESPEED_KEY] + visible),
        "L03": ("URL présignée S3 (24 h) avec sa signature, 5 objets", "presigned-url", False, [AWS_KEY_ID] + S3_SIGS),
        "L04": ("URL signée GCS (48 h) avec sa signature, 4 objets", "presigned-url", False, GCS_SIGS),
        "L05": ("callback OAuth avec access_token dans la query string", "oauth-callback", False, META_TOKENS),
        "L06": ("échange OAuth avec client_secret et code dans l'URL", "oauth-callback", False,
                [META_CLIENT_SECRET] + META_CODES),
        "L07": ("en-tête Authorization: Bearer dans le log de requête pino", "auth-header", False, JWTS),
        "L08": ("en-tête x-api-key dans un console.log(req.headers)", "auth-header", False, [PARTNER_KEY]),
        "L09": ("e-mail de client dans un log Django", "email", False, [EMAIL_A]),
        "L10": ("e-mail de client dans un log Node", "email", False, [EMAIL_B]),
    }
    truth = {
        "seed": SEED,
        "app_log": {"file": "app.log", "lines": len(app.lines)},
        "clean_log": {"file": "clean.log", "lines": len(clean.lines)},
        "leaks": [{"id": lid, "name": name, "form": form, "partial": partial, "lines": sorted(leaks[lid]),
                   "secrets": secrets} for lid, (name, form, partial, secrets) in spec.items()],
        "traps": [{"id": tid, "name": TRAPS[tid][0], "lines": sorted(traps[tid])} for tid in sorted(traps)],
        "clean_traps": [{"id": tid, "name": TRAPS[tid][0], "lines": sorted(clean_traps[tid])} for tid in sorted(clean_traps)],
        "gemini": {"url": GEMINI_URL, "key": GEMINI_KEY},
        "formats": {"file": "formats.log", "leak_lines": [i + 1 for i, (_, x) in enumerate(formats) if x],
                    "clean_lines": [i + 1 for i, (_, x) in enumerate(formats) if not x]},
    }
    (OUT / "truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=1), encoding="utf-8")
    n_leak_lines = sum(len(v) for v in leaks.values())
    print("app.log: %d lines, 10 leaks on %d lines, %d trap lines" % (
        len(app.lines), n_leak_lines, sum(len(v) for v in traps.values())))
    print("clean.log: %d lines, 0 leak, %d trap lines" % (len(clean.lines), sum(len(v) for v in clean_traps.values())))
    print("formats.log: %d lines, %d leaking, %d not" % (len(formats), sum(x for _, x in formats),
                                                        sum(not x for _, x in formats)))
    print("truth.json written to", OUT)


if __name__ == "__main__":
    main()
