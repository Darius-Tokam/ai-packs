---
name: check-before-install
description: Run the full oss-check procedure (license-reader, then install-weigher, then one verdict line) when the user asks, in any language, whether they can use an open source library or tool for their work or product, or asks to check a repository's licence, install weight or offline behaviour before installing it ("est-ce que je peux utiliser cette lib au travail ?", "vérifie la licence de cet outil avant que je l'installe", "combien pèse cette install ?", "can I use this library commercially?", "check this repo's license before I install it"). Same procedure as /oss-check:check, started by the request instead of the command.
---

# check-before-install

The user wants to know, before installing an open source tool, whether its licence allows their usage and what the install costs. Run the same procedure as `/oss-check:check`.

1. Find the target: a local folder, a cloned repository, or a URL to clone read-only in a temporary folder (`WORK="$(mktemp -d -t oss-check.XXXXXX)"; git clone --depth 1 <url> "$WORK/repo"`). For a package name (pip, npm), find its source repository from the package page the user points at, or ask once.
2. Find the usage: "au travail", "in production" or "at my company" is `interne`; "for my SaaS", "to sell" or "commercially" is `saas`; "in my product" or "in my Docker image" is `redistribution`; "for me", "at home" is `perso`. If nothing says it, ask once, in one sentence.
3. Run `license-reader` for that usage.
4. Run `install-weigher`. Install in a throwaway venv only if the user says yes; otherwise keep the static measures.
5. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/oss_check.py" report "$REPO" --usage <usage>` (add `--env "$WORK/tool" --baseline "$WORK/temoin"` when the install was measured) and print its last line, `OSS-CHECK: <OK|ATTENTION|STOP> pour <usage> : licence <...>, <n> paquets, <taille>, <n> appels réseau au démarrage`. If the review of the two agents changes the verdict, print the corrected line and one sentence saying what changed and why.

Never install into the user's project, never run the tool, and never present the answer as legal advice: it quotes the files.
