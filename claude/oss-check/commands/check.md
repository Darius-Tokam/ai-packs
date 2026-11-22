---
description: Before installing an open source tool, check what its licence allows for your usage, what the install weighs and which network calls it makes, with 2 agents and one verdict line.
argument-hint: "<folder or cloned repo> [perso|interne|saas|redistribution]"
---

Check this open source tool before it is installed. Arguments given by the user: $ARGUMENTS

1. Find the target from the arguments: a local folder or a cloned repository. For a URL, clone it read-only in a temporary folder: `WORK="$(mktemp -d -t oss-check.XXXXXX)"; git clone --depth 1 <url> "$WORK/repo"`. Never run anything from it.
2. Find the usage: `perso`, `interne`, `saas` or `redistribution`. If the arguments do not give it, ask once, in one sentence.
3. Run `license-reader` for that usage: every licence file, the carve-outs, one status per usage with the exact sentence and its file.
4. Run `install-weigher`: declared dependencies and extras, network calls at first launch or dormant, and the measured weight against an empty baseline if the user agrees to a throwaway install.
5. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/oss_check.py" report <repo> --usage <usage>` (with `--env` and `--baseline` when the install was measured).
6. Print one summary table (| Check | Finding | Source |) and exactly one final line:
   `OSS-CHECK: <OK|ATTENTION|STOP> pour <usage> : licence <...>, <n> paquets, <taille>, <n> appels réseau au démarrage`
   - STOP when the licence forbids the usage;
   - ATTENTION for a partial restriction (carve-out, AGPL for a SaaS, dual licence) or a network call at first launch that the README does not announce;
   - OK otherwise.
   If the review of the agents changes the script's verdict, print the corrected line and one sentence saying what changed and why.

Never install into the user's project, never run the tool, and never present the answer as legal advice: it quotes the files.
