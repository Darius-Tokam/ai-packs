"""Render the animated version of a pack visual (1080x1350 GIF) from the same spec.

    python render_gif.py spec.json out.gif

The first frame is the complete static visual, so the post still reads if
LinkedIn shows only that frame. The loop then replays the run: the command
is typed, the agents run one after the other, each card reveals its result,
and the loop ends on the complete visual again.

Optional "anim" block in the spec:
    "anim": {
      "running": "analyse en cours",       # label of the card being run
      "queued": "en attente",              # label of the cards not run yet
      "status_ready": "",                  # status line while typing (HTML)
      "status_running": "{done}/{total} agents terminés",  # status line during the run (HTML)
      "intro_command": "claude",          # optional: typed in the shell first
      "intro_glyph": "$"                  # shell prompt glyph for the intro
    }

With "template": "orgchart" the loop is different: everything goes dark,
the orchestrator lights up, then each column lights up in turn (wire,
"analyse..." then its finding and tag), and the verdict bar comes last.
The label shown while a column runs is labels.running in the spec.

Limits checked at the end: LinkedIn plays a GIF uploaded through the post
composer when it is under 5 MB and 400 frames, otherwise it freezes it on
the first frame. Needs ffmpeg.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _page import launch, layout_warnings, open_page, template  # noqa: E402

MAX_BYTES, MAX_FRAMES = 5 * 1024 * 1024, 400

spec_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
spec = json.loads(spec_path.read_text())
anim = {"running": "analyse en cours", "queued": "en attente", "status_ready": "",
        "status_running": "{done}/{total} agents terminés"}
anim.update(spec.get("anim", {}))
ORG = template(spec) == "orgchart"
if not ORG:
    labels = {"running": anim["running"], "queued": anim["queued"]}
    n_cards = len(spec["cards"])
    total = sum(1 for c in spec["cards"] if not c.get("highlight")) or n_cards
    command_len = len(spec["command"] + spec["command_arg"])

if not shutil.which("ffmpeg"):
    raise SystemExit("ffmpeg is required for the GIF")

frames = []  # (png path, duration in seconds)
work = Path(tempfile.mkdtemp(prefix="gif-frames-"))


def shot(page, seconds):
    path = work / f"f{len(frames):03d}.png"
    page.locator("#canvas").screenshot(path=str(path))
    frames.append((path, seconds))


def run_status(done):
    return anim["status_running"].format(done=done, total=total)


def org_loop(page):
    """Orgchart: dark, orchestrator on, columns one by one, verdict, complete."""
    n = len(spec["columns"])
    base = (spec.get("labels", {}).get("running") or "analyse").rstrip(".… ")

    def org(states, root, verdict, dots=0):
        page.evaluate("([s, r, v, l]) => { R.cols(s); R.root(r); R.verdict(v); R.run(l); }",
                      [states, root, verdict, base + "." * dots])

    org(["done"] * n, False, True)
    shot(page, 1.6)
    org(["hidden"] * n, False, False)
    shot(page, 0.5)
    org(["hidden"] * n, True, False)
    shot(page, 0.45)
    for i in range(n):
        for dots in (1, 2, 3):
            org(["done"] * i + ["running"] + ["hidden"] * (n - i - 1), True, False, dots)
            shot(page, 0.09)
        org(["done"] * (i + 1) + ["hidden"] * (n - i - 1), True, False)
        shot(page, 0.22)
    org(["done"] * n, True, True)
    shot(page, 0.5)
    org(["done"] * n, False, True)
    shot(page, 2.6)


if ORG:
    with sync_playwright() as p:
        browser = launch(p)
        page = open_page(browser, spec)
        warnings = layout_warnings(page, spec)
        org_loop(page)
        browser.close()
else:
    with sync_playwright() as p:
        browser = launch(p)
        page = open_page(browser, spec)
        warnings = layout_warnings(page)
        final_status = spec.get("status_html", "")

        def state(states, tick=0, typed=command_len, hint=True, caret=True, status=final_status):
            page.evaluate("""([states, tick, labels, typed, hint, caret, status]) => {
                R.setCards(states, tick, labels); R.typed(typed); R.hint(hint); R.caret(caret); R.status(status);
            }""", [states, tick, labels, typed, hint, caret, status])

        done_all = ["done"] * n_cards
        # 1. complete visual first
        state(done_all)
        shot(page, 1.4)
        # 2. empty prompt, every agent waiting
        queued = ["queued"] * n_cards
        state(queued, typed=0, hint=False, status=anim["status_ready"])
        # optional shell intro: the tool is launched from the shell before the command
        intro = anim.get("intro_command")
        if intro:
            glyph_in, glyph_out = anim.get("intro_glyph", "$"), spec.get("prompt_glyph", "")
            page.evaluate("([g]) => R.raw(g, '')", [glyph_in])
            shot(page, 0.35)
            for n in range(1, len(intro) + 1):
                page.evaluate("([g, t]) => R.raw(g, t)", [glyph_in, intro[:n]])
                shot(page, 0.07)
            shot(page, 0.3)
            page.evaluate("([g]) => { R.glyph(g); R.typed(0); }", [glyph_out])
        shot(page, 0.35)
        # 3. the command is typed, the slash menu shows the match
        for n in range(3, command_len + 3, 3):
            state(queued, typed=min(n, command_len), hint=True, status=anim["status_ready"])
            shot(page, 0.05)
        shot(page, 0.35)
        # 4. agents run in order, each one reveals its result
        tick = 0
        for i in range(n_cards):
            states = ["done"] * i + ["running"] + ["queued"] * (n_cards - i - 1)
            for _ in range(3 if i < n_cards - 1 else 2):
                state(states, tick=tick, hint=False, status=run_status(min(i, total)))
                shot(page, 0.11)
                tick += 1
        # 5. complete visual again, held, then the loop restarts on the same image
        state(done_all)
        shot(page, 2.6)
        browser.close()

def set_delays(gif_path, delays_cs):
    """Write one delay (in 1/100 s) per frame into the GIF's graphic control blocks.

    ffmpeg encodes at a fixed rate; the real timing of each frame is set here,
    without re-encoding the image data."""
    data = bytearray(gif_path.read_bytes())
    pos = 13
    if data[10] & 0x80:
        pos += 3 * (2 ** ((data[10] & 0x07) + 1))
    found = []
    while pos < len(data):
        block = data[pos]
        if block == 0x3B:
            break
        if block == 0x21:
            label = data[pos + 1]
            if label == 0xF9:
                found.append(pos + 4)
            pos += 2
            while data[pos]:
                pos += data[pos] + 1
            pos += 1
        elif block == 0x2C:
            flags = data[pos + 9]
            pos += 10
            if flags & 0x80:
                pos += 3 * (2 ** ((flags & 0x07) + 1))
            pos += 1
            while data[pos]:
                pos += data[pos] + 1
            pos += 1
        else:
            raise SystemExit(f"unexpected GIF block 0x{block:02x} at {pos}")
    if len(found) != len(delays_cs):
        raise SystemExit(f"{len(found)} frames encoded for {len(delays_cs)} captured")
    for at, cs in zip(found, delays_cs):
        data[at:at + 2] = int(cs).to_bytes(2, "little")
    gif_path.write_bytes(bytes(data))


graph = ("split[a][b];[a]palettegen=max_colors=256:stats_mode=full[p];"
         "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "25", "-i", str(work / "f%03d.png"),
                "-vf", graph, "-fps_mode", "passthrough", "-loop", "0", str(out_path)], check=True)
set_delays(out_path, [round(seconds * 100) for _, seconds in frames])
shutil.rmtree(work, ignore_errors=True)

size = out_path.stat().st_size
print(f"wrote {out_path}: {len(frames)} frames, {size / 1024 / 1024:.2f} MB, "
      f"{sum(s for _, s in frames):.1f} s per loop")
for w in warnings:
    print("WARNING", w)
if size > MAX_BYTES:
    print("WARNING over 5 MB: LinkedIn rejects it")
if len(frames) > MAX_FRAMES:
    print("WARNING over 400 frames: LinkedIn freezes it on the first frame")
