---
name: install-weigher
description: Measure what installing an open source tool costs before you adopt it. Weight - packages and megabytes of the install minus an empty baseline, the heaviest packages, the known heavy ones that rarely serve the goal (pandas, numpy, sympy, torch, onnxruntime, transformers), heavy packages hidden behind an optional extra, and what one stack contains of another. Network - the calls the code makes at first launch or keeps dormant (model downloads from huggingface.co, licence key services, telemetry, update checks), found by reading the code, with the environment variable that cuts them. Use when the user asks how heavy an install is, what a tool pulls with it, or whether it really works offline.
---

# install-weigher

You measure what the install costs: disk, dependencies, and what goes out on the network. The script measures; you check what it found and what it cannot see.

## 1. Without installing anything

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/oss_check.py" weigh "$REPO" --json
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/oss_check.py" network "$REPO" --json
```

- `weigh` on a source repository reads pyproject.toml, setup.cfg or package.json: the base dependencies, each optional extra, and the known heavy packages hidden behind an extra (`pip install tool[all]` is not `pip install tool`).
- `network` reads the code without running it. Each call is either `premier lancement` (no guard: it runs as soon as the code path runs) or `dormant` (behind a licence key, an API key or an option whose default is off). Comments, docstrings, tests and docs are ignored. It lists the environment variables found in the code that cut a call (`HF_HUB_OFFLINE`, `OFFLINE_MODE`, `DO_NOT_TRACK`) and whether the README promises something like "no external connections".

## 2. Measured weight, only with the user's yes

Installing downloads packages and can run setup code, so ask once before doing it. Then work in a temporary folder, never in the user's project or global environment, and never run the tool itself:

```bash
WORK="$(mktemp -d -t oss-check.XXXXXX)"
python3 -m venv "$WORK/temoin"
python3 -m venv "$WORK/tool"
"$WORK/tool/bin/pip" install --only-binary=:all: "<tool>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/oss_check.py" weigh "$WORK/tool" --baseline "$WORK/temoin" --json
```

- The empty baseline removes pip and setuptools from the count. Sizes are apparent sizes of the files listed in each RECORD, 1 Mo = 1 000 000 bytes.
- To compare two options (an all-in-one tool and a stack of small libraries), install each in its own venv and add `--compare "$WORK/other"`: the script says how many packages of one are already in the other.
- For Node: `npm install --prefix "$WORK/tool" --ignore-scripts "<package>"`, then weigh `"$WORK/tool/node_modules"`.
- If `--only-binary` fails, tell the user that the fallback builds from source and runs the package's setup code, and ask again.

## 3. Check the network findings

Open every `file:line` the script gives.

- A `premier lancement` call: follow it from the entry point (main, startup, lifespan, the Docker entrypoint). If it only runs when the user uses one feature, say so and call it "on first use of <feature>". If it runs at start, it is the cost of the first launch: on a machine already cut from the network, the tool may not start.
- A `dormant` call: name the key or option that wakes it and its default.
- Check each switch variable in the code: what it cuts and its default.
- Look for what the script cannot read: downloads in a Dockerfile or entrypoint script (`curl`, `wget`), model names in config defaults, calls inside compiled code (jar, wheel binaries, minified JS). Say plainly that compiled code was not read.
- Static reading says who the code can call, not what it sends. Never claim to know what a call sends.

## 4. Report

1. Weight: | Packages | Size | Heaviest | Known heavy, rarely useful for the goal |, plus the extras and the comparison when measured.
2. Network: | Call | File:line | When | Setting that cuts it |, and the README promise next to what the code does.
3. End with exactly one line: `INSTALL: <n> paquets, <taille>, <n> appels réseau au démarrage, <n> dormants`.

Answer in the user's language. Never install anything without a yes, never run the tool, never touch the user's environment.
