#!/usr/bin/env python3
"""Mechanical check for a smart-spec Spec file. Standard library only.

  check-spec.py SPEC.md

Proves what a script can prove:
  - the title line `# Spec: <title>`
  - header: `Status` is DRAFT, APPROVED or DONE; `Ticket` is present (`Ticket: none` is allowed)
  - the required headings, each exactly once: Why, Outcome, Behaviour, Acceptance criteria, Test approach, Not covered
  - Acceptance criteria hold at least one `- AC-n:` list line and no `AC-n` twice; a line that mentions an
    AC id any other way (a table row, a lowercase `ac-2`) fails; plain prose and `###` group headings are allowed
  - no `file:line` citation outside a code fence (a Spec says what, never where); it recognises a path
    with a slash, a bare file with a source extension, and Makefile/Dockerfile, not hosts, ports or URLs

It does not judge whether the Spec is good or whether each criterion is testable.

Exit 0: no problems. Exit 1: at least one FAIL line. Exit 2: bad usage or unreadable file.
"""
import argparse
import re
import sys
from pathlib import Path

STATUSES = {"DRAFT", "APPROVED", "DONE"}
REQUIRED = ["Why", "Outcome", "Behaviour", "Acceptance criteria", "Test approach", "Not covered"]
# A cited source file with a line: a path with a slash, a bare file with an unambiguous source extension,
# or Makefile/Dockerfile. Hosts with a port, `Node.js:18` and URLs are not citations.
SRC_EXT = r"(?:py|ts|tsx|jsx|php|rb|go|rs|java|kt|swift|cs|cpp|c|h|sql|vue|svelte|sh|yml|yaml|toml)"
CITE = re.compile(rf"(?<![\w/.-])(?:[\w.@()\[\]-]+/[\w./@()\[\]-]*\.[A-Za-z][A-Za-z0-9]{{0,5}}"
                  rf"|[\w.-]+\.{SRC_EXT}|Makefile|Dockerfile):\d+\b")
URL = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.I)
FENCE = re.compile(r"^\s*(```|~~~)")
FAILS = []


def fail(check, msg):
    FAILS.append(f"FAIL {check}: {msg}")


def field(line, key):
    m = re.search(rf"\b{key}:\s*([^·\n]+?)\s*(?:·|$)", line)
    return m.group(1).strip() if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    a = ap.parse_args()
    path = Path(a.spec)
    if not path.is_file() or path.suffix.lower() != ".md":
        print(f"ERROR [check-spec.py]: {path} is not a Markdown (.md) file", file=sys.stderr)
        print("NEXT: pass the path of the saved Spec file (check it with `ls`), then run again.", file=sys.stderr)
        sys.exit(2)
    lines = path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    if not any(re.match(r"^# Spec:\s*\S", ln) for ln in lines):
        fail("header", "no `# Spec: <title>` line")
    head = {}
    for ln in lines[:12]:
        if ln.startswith("#"):
            continue
        for key in ("Status", "Ticket"):
            v = field(ln, key)
            if v and key not in head:
                head[key] = v
    if head.get("Status") not in STATUSES:
        fail("header", f"Status `{head.get('Status')}` is not one of {sorted(STATUSES)}")
    if "Ticket" not in head:
        fail("header", "no `Ticket:` (use `Ticket: none` when there is none)")
    sections, cur, fence = {}, None, False
    for ln in lines:
        if FENCE.match(ln):
            fence = not fence
            continue
        m = None if fence else re.match(r"^##\s+(.+?)\s*$", ln)
        if m and not ln.startswith("###"):
            cur = m.group(1)
            if cur in sections and cur in REQUIRED:
                fail("sections", f"`## {cur}` is repeated; each required heading appears once")
            sections[cur] = []
        elif cur is not None:
            sections[cur].append(("fence " if fence else "") + ln)
    for h in REQUIRED:
        if h not in sections:
            fail("sections", f"missing `## {h}`")
    ac_lines = sections.get("Acceptance criteria", [])
    ids = []
    for ln in ac_lines:
        if not ln.strip() or ln.startswith((" ", "\t")) or ln.startswith("fence "):
            continue  # blank, an indented continuation, or inside a code fence
        m = re.match(r"^[-*]\s+(AC-\d+):", ln)
        if m:
            ids.append(m.group(1))
        elif re.search(r"\bac-\d+\b", ln, re.I) and not ln.startswith("#"):
            fail("criteria", f"`{ln.strip()[:40]}` mentions an AC id (`AC-n`) but is not a `- AC-n:` list line")
    if "Acceptance criteria" in sections and not ids:
        fail("criteria", "no `- AC-n:` line under `## Acceptance criteria`")
    for ac in sorted({i for i in ids if ids.count(i) > 1}):
        fail("criteria", f"duplicate {ac}")
    fence = False
    for n, ln in enumerate(lines, 1):
        if FENCE.match(ln):
            fence = not fence
            continue
        if not fence and CITE.search(URL.sub(" ", ln)):
            fail("file:line", f"line {n} cites a file and line; a Spec says what, the plan says where")
    if FAILS:
        print("\n".join(FAILS))
        print(f"{len(FAILS)} problem(s) in {path.name}")
        sys.exit(1)
    print(f"OK {path.name}: all mechanical checks passed (this does not judge the Spec itself)")


if __name__ == "__main__":
    main()
