#!/usr/bin/env python3
"""Mechanical check for a smart-adr ADR file. Standard library only.

  check-adr.py ADR.md [--root DIR]

Proves what a script can prove:
  - the title line `# ADR: <title>`
  - header: `Status` is PROPOSED, ACCEPTED or SUPERSEDED; `Ticket` is present
  - the required headings, each exactly once: Context, Decision, Why record this
  - `Why record this` holds at least three list lines, bulleted or numbered (one per test the decision passed)
  - a SUPERSEDED ADR names `Superseded by:`, and every `Supersedes:` or `Superseded by:` path (written
    from the project root, so it works across the dated folders) exists under --root (default: .); a
    path that leaves the root, or that points at the ADR itself, is refused; an ACCEPTED ADR that
    supersedes another needs that one SUPERSEDED, with its `Superseded by:` pointing back

It does not judge whether the decision passes the three tests, only that the reasons are written down.

Exit 0: no problems. Exit 1: at least one FAIL line. Exit 2: bad usage or unreadable file.
"""
import argparse
import re
import sys
from pathlib import Path

STATUSES = {"PROPOSED", "ACCEPTED", "SUPERSEDED"}
REQUIRED = ["Context", "Decision", "Why record this"]
FENCE = re.compile(r"^\s*(```|~~~)")
FAILS = []


def fail(check, msg):
    FAILS.append(f"FAIL {check}: {msg}")


def field(line, key):
    m = re.search(rf"\b{key}:\s*([^·\n]+?)\s*(?:·|$)", line)
    return m.group(1).strip() if m else None


def header_of(path):
    """Status and Superseded-by of another ADR file (first 12 lines, up to its first section)."""
    h = {}
    for ln in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()[:12]:
        if ln.startswith("## "):
            break
        if ln.startswith("#"):
            continue
        for key in ("Status", "Superseded by"):
            v = field(ln, key)
            if v and key not in h:
                h[key] = v
    return h


def check_chain(old, this, shown, status, base):
    """An accepted ADR that supersedes another must find the other closed, and pointing back here."""
    oh = header_of(old)
    ostatus = oh.get("Status", "").upper()
    if status == "ACCEPTED" and ostatus != "SUPERSEDED":
        fail("links", f"`Supersedes: {shown}` is still {ostatus or 'without a status'}; run "
                      f"`ticket-tools.py set-status {shown} SUPERSEDED --superseded-by <this ADR>`")
    if ostatus == "SUPERSEDED":
        back = oh.get("Superseded by")
        if not back or (base / back).resolve() != this:
            fail("links", f"`Supersedes: {shown}` is SUPERSEDED but its `Superseded by:` does not point at this ADR")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("adr")
    ap.add_argument("--root", default=".", help="project root that Supersedes / Superseded by paths are relative to")
    a = ap.parse_args()
    path = Path(a.adr)
    if not path.is_file() or path.suffix.lower() != ".md":
        print(f"ERROR [check-adr.py]: {path} is not a Markdown (.md) file", file=sys.stderr)
        print("NEXT: pass the path of the saved ADR file (check it with `ls`), then run again.", file=sys.stderr)
        sys.exit(2)
    lines = path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    if not any(re.match(r"^# ADR:\s*\S", ln) for ln in lines):
        fail("header", "no `# ADR: <title>` line")
    head = {}
    for ln in lines[:12]:
        if ln.startswith("## "):
            break  # the header ends at the first section; prose below it is not a header field
        if ln.startswith("#"):
            continue
        for key in ("Status", "Ticket", "Supersedes", "Superseded by"):
            v = field(ln, key)
            if v and key not in head:
                head[key] = v
    status = head.get("Status", "").upper()  # compared without case, like ticket-tools set-status
    if status not in STATUSES:
        fail("header", f"Status `{head.get('Status')}` is not one of {sorted(STATUSES)}")
    if "Ticket" not in head:
        fail("header", "no `Ticket:`")
    if status == "SUPERSEDED" and "Superseded by" not in head:
        fail("header", "Status is SUPERSEDED but there is no `Superseded by:`")
    base = Path(a.root).resolve()
    for key in ("Supersedes", "Superseded by"):
        if key in head:
            target = (base / head[key]).resolve()
            if not target.is_relative_to(base):
                fail("links", f"`{key}: {head[key]}` leaves the project root")
            elif not target.is_file():
                fail("links", f"`{key}: {head[key]}` does not exist")
            elif target == path.resolve():
                fail("links", f"`{key}: {head[key]}` points at this ADR itself")
            elif key == "Supersedes":
                check_chain(target, path.resolve(), head[key], status, base)
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
        elif cur is not None and not fence:
            sections[cur].append(ln)
    for h in REQUIRED:
        if h not in sections:
            fail("sections", f"missing `## {h}`")
    if "Why record this" in sections:
        items = [ln for ln in sections["Why record this"] if re.match(r"^\s*(?:[-*]|\d+[.)])\s+\S", ln)]
        if len(items) < 3:
            fail("sections", "`## Why record this` needs three list lines, one for each test the decision passed (bulleted or numbered)")
    if FAILS:
        print("\n".join(FAILS))
        print(f"{len(FAILS)} problem(s) in {path.name}")
        sys.exit(1)
    print(f"OK {path.name}: all mechanical checks passed (this does not judge the decision itself)")


if __name__ == "__main__":
    main()
