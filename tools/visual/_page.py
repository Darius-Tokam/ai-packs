"""Shared helpers for render.py (PNG) and render_gif.py (animated GIF)."""
import base64
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIDTH, HEIGHT, CTA_HEIGHT = 1080, 1350, 168


def _font_faces():
    faces = []
    for weight in (400, 700):
        f = HERE / "fonts" / f"JetBrainsMono-{weight}.woff2"
        if f.exists():
            data = base64.b64encode(f.read_bytes()).decode()
            faces.append(
                "@font-face { font-family: 'JetBrains Mono'; font-weight: %d; "
                "src: url(data:font/woff2;base64,%s) format('woff2'); }" % (weight, data))
    return "\n".join(faces)


def build_html(spec):
    html = (HERE / "grid.html").read_text()
    html = html.replace("/*FONTS*/", _font_faces())
    return html.replace("const S = window.SPEC;",
                        "const S = " + json.dumps(spec, ensure_ascii=False) + ";")


def launch(p):
    for kwargs in ({"executable_path": "/usr/bin/google-chrome"}, {}):
        try:
            return p.chromium.launch(**kwargs)
        except Exception:
            continue
    raise SystemExit("no Chromium available: run `python -m playwright install chromium`")


def open_page(browser, spec):
    page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
    page.set_content(build_html(spec), wait_until="load")
    page.evaluate("document.fonts.ready")
    return page


def layout_warnings(page):
    warnings = []
    overflow = page.evaluate("""() => [...document.querySelectorAll('.card, .window, .hint')]
        .filter(e => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1)
        .map(e => (e.querySelector('.ct')||e).textContent.trim().slice(0, 40))""")
    if overflow:
        warnings.append(f"overflow in: {overflow}")
    bottom = page.evaluate("document.querySelector('.window').getBoundingClientRect().bottom")
    if bottom > HEIGHT - CTA_HEIGHT - 12:
        warnings.append(f"window bottom {bottom:.0f}px overlaps the CTA band")
    return warnings
