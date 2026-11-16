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
    """grid (terminal + cards, the default), orgchart (orchestrator + columns), duo (Claude pack + n8n bonus) or mesure (bars of a measured comparison)."""
    return spec.get("template", "grid")


REPO = HERE.parent.parent
KEEP_PARAMS = ("operation", "resource", "mode")


def prepare(spec, spec_path):
    """duo: read the workflow named in n8n.workflow and keep only what the canvas draws.

    The path is relative to the spec file, or else to the repo root. Only node names,
    types, positions, operation, resource and mode are kept: no credential, no ID."""
    if template(spec) != "duo":
        return spec
    n8n = spec["n8n"]
    if "graph" not in n8n:
        rel = Path(n8n["workflow"])
        path = next((p for p in (Path(spec_path).resolve().parent / rel, REPO / rel) if p.exists()), None)
        if path is None:
            raise SystemExit(f"workflow not found: {rel}")
        wf = json.loads(path.read_text())
        nodes = [{"name": n["name"], "type": n["type"], "position": n.get("position", [0, 0]),
                  "parameters": {k: v for k, v in (n.get("parameters") or {}).items()
                                 if k in KEEP_PARAMS and isinstance(v, str)}}
                 for n in wf.get("nodes", [])]
        n8n["graph"] = {"nodes": nodes, "connections": wf.get("connections", {})}
    return spec


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
    if spec is not None and template(spec) == "duo":
        return _duo_warnings(page)
    if spec is not None and template(spec) == "mesure":
        warnings = list(page.evaluate("R.warnings"))
        overflow = page.evaluate("""() => [...document.querySelectorAll('.pill, .card, .row .lb, .stat, .sub, .cta .l, .cta .ft')]
            .filter(e => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1)
            .map(e => e.textContent.trim().slice(0, 40))""")
        if overflow:
            warnings.append(f"overflow in: {overflow}")
        return warnings
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


def _duo_warnings(page):
    warnings = list(page.evaluate("R.warnings"))
    overflow = page.evaluate("""() => [...document.querySelectorAll('.pill, .hdr, .agent, .stat, .note, .cta .l, .cta .ft')]
        .filter(e => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1)
        .map(e => e.textContent.trim().slice(0, 40))""")
    if overflow:
        warnings.append(f"overflow in: {overflow}")
    geo = page.evaluate("""() => {
        const b = s => document.querySelector(s).getBoundingClientRect();
        const p = [...document.querySelectorAll('.pill')].map(e => e.getBoundingClientRect());
        const pills = p.length ? p[p.length - 1].right - p[0].left : 0;
        const wide = [...document.querySelectorAll('h1 span')].map(e => e.scrollWidth - e.clientWidth);
        return {pills, title: b('h1').bottom, wide: Math.max(0, ...wide), c1: b('#c1').top, c2: b('#c2').bottom, cta: b('.cta').top};
    }""")
    if geo["pills"] > WIDTH - 40:
        warnings.append(f"pills are {geo['pills']:.0f}px wide, wider than the visual")
    if geo["wide"] > 1:
        warnings.append("a title line is wider than the visual: shorten title or title2")
    if geo["title"] > geo["c1"] - 6:
        warnings.append(f"title bottom {geo['title']:.0f}px runs into card 1 ({geo['c1']:.0f}px)")
    if geo["c2"] > geo["cta"] - 12:
        warnings.append(f"card 2 bottom {geo['c2']:.0f}px overlaps the CTA band ({geo['cta']:.0f}px)")
    return warnings
