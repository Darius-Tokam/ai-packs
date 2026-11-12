---
name: dep-audit
description: Audit the dependencies a branch adds or changes - known CVEs, unused additions, unpinned versions, risky licenses. Use on any diff that touches requirements.txt, pyproject.toml, poetry.lock, package.json, lockfiles, go.mod or Cargo.toml.
---

# dep-audit

## 1. What changed

```bash
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)
git diff "$BASE"...HEAD -- requirements*.txt pyproject.toml poetry.lock uv.lock package.json package-lock.json pnpm-lock.yaml yarn.lock go.mod Cargo.toml
```

List each added, removed or version-changed package.

## 2. Known vulnerabilities

Run the ecosystem's auditor and keep its raw output:

```bash
pip-audit -r requirements.txt            # Python (pip install pip-audit)
npm audit --omit=dev                     # Node
pnpm audit --prod                        # pnpm
govulncheck ./...                        # Go
cargo audit                              # Rust
```

Report each vulnerability on a package the branch touched with its ID (CVE, GHSA or PYSEC) and the first fixed version. Vulnerabilities on untouched packages go in one NOTE line: they predate this branch.

## 3. Is the new package used?

For each added package, search for its import name in the diff and the codebase (`yaml` for PyYAML, `bs4` for beautifulsoup4). An added package that nothing imports is a FIX: remove it or say why it is there.

## 4. Pinning and license

- Unpinned or open ranges (`requests`, `>=2`) in an application: FIX, pin it.
- GPL or AGPL license in a closed-source or SaaS project: NOTE for the author to decide. Read it with `pip show <pkg>` or the package page.

## 5. Report

```
BLOCK | requirements.txt | PyYAML==5.3.1 | PYSEC-2021-142 / CVE-2020-14343, arbitrary code execution, fixed in 5.4 | pip-audit | bump to the latest 6.x
FIX   | requirements.txt | PyYAML added, never imported | grep yaml: 0 hit | remove it
```

End with `DEPS VERDICT: CLEAN` or `DEPS VERDICT: <n> BLOCK, <m> FIX`.
