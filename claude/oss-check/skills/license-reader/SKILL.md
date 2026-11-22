---
name: license-reader
description: Read every licence file of an open source repository (LICENSE*, COPYING*, licences inside sub-directories, SPDX headers, the licence field of package.json, pyproject.toml, setup.cfg, Cargo.toml), find the carve-outs ("except", directories under another licence, dual licensing) and say, for one usage (personal, internal company use, SaaS sold to customers, redistributed in a product), what the files allow, with the exact sentence of 15 words or less and its path. Use before installing or adopting an open source tool or library, or when the user asks whether a licence allows commercial, production or SaaS use. It quotes files and never gives legal advice.
---

# license-reader

You read the licence files and say what they allow for the user's usage. You quote; you never give legal advice and never write "you are allowed" or "it is legal". You write "the file says".

## 1. Get the repository

- Use the local folder the user named. If they gave a URL, clone it read-only in a temporary folder: `WORK="$(mktemp -d -t oss-check.XXXXXX)"; git clone --depth 1 <url> "$WORK/repo"`. Never run anything from the clone.
- Take the usage from the request: `perso` (personal, at home), `interne` (inside a company, production included), `saas` (a service sold to customers), `redistribution` (shipped inside a product or an image you distribute). If the request does not say, ask once, in one sentence.

## 2. Run the script once

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/oss_check.py" license "$REPO" --json
```

It returns the project licence (or the options of a dual licence), the global identifier (`NOASSERTION` when the root LICENSE carves directories out, which is what GitHub shows in that case), every carve-out with its own licence, SPDX headers, NOTICE files, manifest fields, and one status per usage with a quote and its path.

Families: permissive (MIT, BSD, Apache-2.0, ISC, OFL), copyleft (GPL), weak copyleft (LGPL, MPL, EPL), network copyleft (AGPL), source available and not free (BUSL, SSPL, Elastic License, Commons Clause, "proprietary", a text that reserves production or commercial use to a paid licence), commercial.

## 3. Check what the script read, then what it cannot see

Open each file the script quotes and confirm the classification. Then look for what a file scan misses:

- a licence written only in the README ("License" section) or on the website;
- an `ee/`, `enterprise/` or `proprietary/` directory with no licence file of its own: the root LICENSE or the README usually says which licence covers it;
- a trademark or branding clause (keep the logo, do not use the name), a contributor licence agreement, an "Additional Use Grant" (BUSL) that allows some production use;
- binaries, Docker images or compiled jars that ship code from a carved-out directory: say so when the README or the Dockerfile shows it, because the restriction then travels with what the user installs;
- a recent licence change (CHANGELOG, release notes): mention it, but classify the licence of the version the user will install.

A licence named in a CHANGELOG, a comment or the docs is not the project's licence. Do not count it.

## 4. Answer

1. One table: | Usage | Status | Exact sentence (15 words or less) | File |. Status is OK, ATTENTION or STOP:
   - STOP: the project licence forbids the usage (production reserved to a paid licence, no service, no sale, no licence at all for anything but personal use).
   - ATTENTION: a partial restriction (a carved-out directory under a non-free licence, AGPL for a SaaS, a dual licence where the free option has obligations, copyleft for redistribution, an unknown licence).
   - OK: nothing in the files restricts the usage.
2. For each ATTENTION or STOP, one line on what would change it: build without the carved-out directories, take the commercial licence, publish your changes under AGPL, ask the maintainers.
3. When the files do not settle the question, say so and name who can: the maintainers, then a lawyer for a contract.
4. End with exactly one line: `LICENCE: <OK|ATTENTION|STOP> pour <usage> : <label from the script>`.

Answer in the user's language. Keep every quote in the language of the file, 15 words or less, copied exactly.
