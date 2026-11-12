#!/usr/bin/env python3
"""Build the JSON manifest read by the n8n workflow "ai-packs : publier sur GitHub".

Usage:
    python tools/publish/manifest.py out.json PATH [PATH ...]

Each PATH is a file or a directory, relative to the repo root (run from the root).
Directories are walked recursively. Executable files keep mode 100755.
Output: {"files": [{"path": "...", "b64": "...", "mode": "100644"}]}
"""
import base64
import json
import os
import stat
import sys

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv"}
SKIP_FILES = {".DS_Store"}
MAX_FILES = 150


def collect(paths):
    out = []
    for p in paths:
        p = os.path.normpath(p)
        if p.startswith("..") or os.path.isabs(p):
            sys.exit(f"refused path outside the repo: {p}")
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for f in sorted(files):
                    if f not in SKIP_FILES and not f.endswith(".pyc"):
                        out.append(os.path.join(root, f))
        elif os.path.isfile(p):
            out.append(p)
        else:
            sys.exit(f"not found: {p}")
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    out_path, paths = sys.argv[1], collect(sys.argv[2:])
    if len(paths) > MAX_FILES:
        sys.exit(f"{len(paths)} files, max {MAX_FILES}: send only what changed")
    files = []
    for p in paths:
        with open(p, "rb") as fh:
            data = fh.read()
        mode = "100755" if os.stat(p).st_mode & stat.S_IXUSR else "100644"
        files.append({"path": p.replace(os.sep, "/"), "b64": base64.b64encode(data).decode(), "mode": mode})
    with open(out_path, "w") as fh:
        json.dump({"files": files}, fh)
    size = os.path.getsize(out_path)
    print(f"{len(files)} files, {size / 1024:.0f} KB -> {out_path}")
    for f in files:
        print(f"  {f['mode']} {f['path']}")


if __name__ == "__main__":
    main()
