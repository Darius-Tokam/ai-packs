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
    """grid (terminal + cards, the default), orgchart (orchestrator + columns), duo (Claude pack + n8n bonus), mesure (bars of a measured comparison), ecart (announced face to real), agent (the Arivex mascot, what goes in and what comes out) or choix (one decision, several paths)."""
    return spec.get("template", "grid")


REPO = HERE.parent.parent
KEEP_PARAMS = ("operation", "resource", "mode")


def prepare(spec, spec_path):
    """duo: read the workflow named in n8n.workflow and keep only what the canvas draws.

    The path is relative to the spec file, or else to the repo root. Only node names,
    types, positions, operation, resource and mode are kept: no credential, no ID."""
    if template(spec) == "agent":
        # the Arivex mascot (head and body from arivex.ca), embedded so the page needs no network
        spec["_mascot"] = {k: "data:image/webp;base64," + base64.b64encode((HERE / "assets" / f"arivex-{k}.webp").read_bytes()).decode()
                           for k in ("head", "body")}
        return spec
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


# The Arivex mascot in a corner of every visual (Darius, 2026-11-15): its eyes look left,
# right, back and blink. "mascot": false removes it; {"pos": "tl"|"tr"|"bl"|"br", "size": 96,
# "x": .., "y": ..} moves it. The "agent" template already has it in the middle.
MASCOT_JS = r"""
(function () {
  const M = window.__MASCOT; if (!M) return;
  const W = M.size, H = Math.round(W * 1.425), cv = document.getElementById('canvas');
  const el = document.createElement('div');
  el.id = 'mz'; el.style.cssText = `position:absolute;z-index:50;width:${W}px;height:${H}px;pointer-events:none;`;
  const pos = M.pos || 'tr';
  if (M.x !== undefined) el.style.left = M.x + 'px'; else if (pos[1] === 'l') el.style.left = '22px'; else el.style.right = '22px';
  if (M.y !== undefined) el.style.top = M.y + 'px'; else if (pos[0] === 't') el.style.top = '14px'; else el.style.bottom = (M.bottom || 180) + 'px';
  el.innerHTML = `<img src="${M.body}" style="position:absolute;left:0;top:${Math.round(W * 0.509)}px;width:${W}px">
    <img src="${M.head}" style="position:absolute;left:0;top:0;width:${W}px">
    <svg id="mzeyes" viewBox="0 0 840 840" style="position:absolute;left:0;top:0;width:${W}px;height:${W}px;overflow:visible"></svg>`;
  cv.appendChild(el);
  const EY = { happy: '<path d="M405 430 Q440 372 475 430" /><path d="M555 430 Q590 372 625 430" />', flat: '<path d="M405 420 H475" /><path d="M555 420 H625" />' };
  function eyes(dx, open) {
    const k = open < 0.35 ? 'flat' : 'happy', sy = open >= 1 ? 1 : Math.max(0.15, open);
    document.getElementById('mzeyes').innerHTML = `<defs><filter id="mzg" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
      <g transform="translate(${dx} ${(1 - sy) * 418}) scale(1 ${sy})"><g filter="url(#mzg)" stroke="#c9b8ff" stroke-width="24" stroke-linecap="round" fill="none">${EY[k]}</g></g>`;
  }
  /* at(seconds): one 2.4 s cycle, gaze left, right, back to the centre, then a blink */
  window.MASCOT = {
    at(sec) {
      const t = ((sec % 2.4) + 2.4) % 2.4 / 2.4;
      const gaze = t < 0.25 ? -Math.sin(t / 0.25 * Math.PI / 2) : t < 0.5 ? -Math.cos((t - 0.25) / 0.25 * Math.PI) :
                   t < 0.75 ? Math.cos((t - 0.5) / 0.25 * Math.PI / 2) : 0;
      const blink = t > 0.84 && t < 0.94 ? Math.abs((t - 0.89) / 0.05) : 1;
      eyes(gaze * 30, blink);
    },
  };
  window.MASCOT.at(0);
})();
"""


def _mascot(spec):
    opt = spec.get("mascot", True)
    if opt is False or template(spec) == "agent":
        return None
    opt = dict(opt) if isinstance(opt, dict) else {}
    opt.setdefault("size", 96)
    for k in ("head", "body"):
        opt[k] = "data:image/webp;base64," + base64.b64encode((HERE / "assets" / f"arivex-{k}.webp").read_bytes()).decode()
    return opt


def build_html(spec):
    html = (HERE / f"{template(spec)}.html").read_text()
    html = html.replace("/*FONTS*/", _font_faces())
    html = html.replace("const S = window.SPEC;",
                        "const S = " + json.dumps(spec, ensure_ascii=False) + ";")
    m = _mascot(spec)
    if m:
        html = html.replace("</body>", "<script>window.__MASCOT = " + json.dumps(m) + ";" + MASCOT_JS + "</script>\n</body>")
    return html


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
    if spec is not None and template(spec) in ("mesure", "ecart", "agent", "choix"):
        warnings = list(page.evaluate("R.warnings"))
        overflow = page.evaluate("""() => [...document.querySelectorAll('.pill, .card, .row .lb, .stat, .sub, .cta .l, .cta .ft, .hd, .cell, .lesson, .band .l, .band .ft, .io, .box, .lane, .lane li, .note')]
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
