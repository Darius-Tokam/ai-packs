"""Render a pack visual (1080x1350 PNG) from a JSON spec.

    python render.py spec.json out.png

The spec fills tools/visual/grid.html. See claude/pr-squad/visual/spec.json
for a complete example. Uses Playwright with the system Chrome when
present, else Playwright's own Chromium. For the animated version, see
render_gif.py.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _page import launch, layout_warnings, open_page  # noqa: E402

spec_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
spec = json.loads(spec_path.read_text())

with sync_playwright() as p:
    browser = launch(p)
    page = open_page(browser, spec)
    warnings = layout_warnings(page)
    page.locator("#canvas").screenshot(path=str(out_path))
    browser.close()

print(f"wrote {out_path}")
for w in warnings:
    print("WARNING", w)
