"""Shared helpers for render.py (PNG) and render_gif.py (animated GIF)."""
import base64
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIDTH, HEIGHT, CTA_HEIGHT = 1080, 1350, 168


FONTS = [  # (family, weight, file) ; all under the SIL Open Font License, see fonts/
    ("JetBrains Mono", 400, "JetBrainsMono-400.woff2"),
    ("JetBrains Mono", 700, "JetBrainsMono-700.woff2"),
    ("Inter", 400, "Inter-Regular.woff2"),
    ("Inter", 600, "Inter-SemiBold.woff2"),
    ("Inter", 700, "Inter-Bold.woff2"),
    ("Inter Display", 800, "InterDisplay-ExtraBold.woff2"),
]


def _font_faces():
    faces = []
    for family, weight, name in FONTS:
        f = HERE / "fonts" / name
        if f.exists():
            data = base64.b64encode(f.read_bytes()).decode()
            faces.append(
                "@font-face { font-family: '%s'; font-weight: %d; "
                "src: url(data:font/woff2;base64,%s) format('woff2'); }" % (family, weight, data))
    return "\n".join(faces)


def template(spec):
    """grid (terminal + cards, the default) or orgchart (orchestrator + columns)."""
    return spec.get("template", "grid")


def build_html(spec):
    html = (HERE / f"{template(spec)}.html").read_text()
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


def layout_warnings(page, spec=None):
    if spec is not None and template(spec) == "orgchart":
        return _orgchart_warnings(page)
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


def _orgchart_warnings(page):
    warnings = []
    overflow = page.evaluate("""() => [...document.querySelectorAll('.card, .hd, .sk, .root, .verdict, .cta .l')]
        .filter(e => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1)
        .map(e => e.textContent.trim().slice(0, 40))""")
    if overflow:
        warnings.append(f"overflow in: {overflow}")
    geo = page.evaluate("""() => {
        const b = id => document.getElementById(id).getBoundingClientRect();
        return {cols: b('cols').bottom, vtop: b('verdict').top, vbot: b('verdict').bottom,
                head: document.querySelector('.head').getBoundingClientRect().bottom, root: b('root').top,
                cta: document.querySelector('.cta').getBoundingClientRect().top};
    }""")
    if geo["head"] > geo["root"] - 12:
        warnings.append(f"title bottom {geo['head']:.0f}px runs into the orchestrator ({geo['root']:.0f}px)")
    if geo["cols"] > geo["vtop"] - 12:
        warnings.append(f"columns bottom {geo['cols']:.0f}px runs into the verdict ({geo['vtop']:.0f}px)")
    if geo["vbot"] > geo["cta"] - 12:
        warnings.append(f"verdict bottom {geo['vbot']:.0f}px overlaps the CTA band ({geo['cta']:.0f}px)")
    return warnings
