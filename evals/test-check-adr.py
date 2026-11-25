#!/usr/bin/env python3
"""Tests for skills/smart-adr/scripts/check-adr.py. Standard library only.

  python3 -I evals/test-check-adr.py

Exit 0: all pass. Exit 1: at least one failure.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "smart-adr" / "scripts" / "check-adr.py"
FAILS = []

GOOD = """# ADR: Keep plans as files in the repository
Status: PROPOSED · Ticket: APP-ADR-002 · Related: APP-FEAT-004 · Run reference: plans-as-files + 2026-11-25

## Context
Plans must survive a closed session and be readable by any agent.

## Decision
Plans are Markdown files under the project folder, not entries in a service.

## Why record this
- Costly to undo: every skill and every old plan reads that folder.
- Not obvious from the code: a reader would expect a database.
- A genuine trade-off: a service gives search; files give offline review.

## Options considered
A hosted service.
"""


def run(text, *extra, name="adr.md", files=None):
    with tempfile.TemporaryDirectory() as d:
        for rel, body in (files or {}).items():
            q = Path(d) / rel
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_text(body)
        p = Path(d) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), str(p), "--root", d, *extra], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr


def check(name, cond, detail=""):
    if not cond:
        FAILS.append(f"FAIL {name} {detail}")


def main():
    rc, out = run(GOOD)
    check("valid ADR prints OK", rc == 0 and out.startswith("OK"), out)
    rc, out = run(GOOD.replace("Status: PROPOSED", "Status: OPEN"))
    check("status outside the lifecycle fails", rc == 1 and "Status" in out, out)
    for h in ("Context", "Decision", "Why record this"):
        rc, out = run(GOOD.replace(f"## {h}\n", f"## {h} notes\n"))
        check(f"missing {h} fails", rc == 1 and h in out, out)
    rc, out = run(GOOD.replace(" · Ticket: APP-ADR-002", ""))
    check("missing Ticket fails", rc == 1 and "Ticket" in out, out)
    rc, out = run(GOOD.replace("Status: PROPOSED", "Status: SUPERSEDED"))
    check("SUPERSEDED without Superseded by fails", rc == 1 and "Superseded by" in out, out)
    rc, out = run(GOOD.replace("Status: PROPOSED", "Status: SUPERSEDED").replace("Ticket:", "Superseded by: new.md · Ticket:"),
                  files={"new.md": GOOD})
    check("SUPERSEDED with an existing Superseded by passes", rc == 0, out)
    rc, out = run(GOOD.replace("Ticket:", "Supersedes: gone.md · Ticket:"))
    check("Supersedes path that does not exist fails", rc == 1 and "gone.md" in out, out)
    rc, out = run(GOOD.replace("Ticket:", "Supersedes: old.md · Ticket:"), files={"old.md": GOOD})
    check("Supersedes path that exists passes", rc == 0, out)
    rc, out = run(GOOD.replace("Ticket:", "Supersedes: ../../etc/passwd · Ticket:"))
    check("Supersedes may not leave the project root", rc == 1 and "passwd" in out and "root" in out, out)
    rc, out = run(GOOD.replace("Ticket:", "Supersedes: .agents/adr/2026/11/20/old.md · Ticket:"),
                  files={".agents/adr/2026/11/20/old.md": GOOD}, name=".agents/adr/2026/11/25/new.md")
    check("Supersedes is a path from the project root, across date folders", rc == 0, out)
    rc, out = run("﻿" + GOOD)
    check("a UTF-8 BOM is read", rc == 0, out)
    rc, out = run(GOOD.replace("- A genuine trade-off: a service gives search; files give offline review.\n", ""))
    check("fewer than three lines under Why record this fails", rc == 1 and "three" in out, out)
    rc, out = run(GOOD.replace("- Costly to undo:", "1. Costly to undo:").replace("- Not obvious", "2) Not obvious").replace("- A genuine", "3. A genuine"))
    check("F2 numbered reason lines count", rc == 0, out)
    rc, out = run(GOOD.replace("- A genuine trade-off: a service gives search; files give offline review.", "- Gate override: not a trade-off, recorded at the user's request"))
    check("F2 the override written as a list line passes", rc == 0, out)
    rc, out = run(GOOD.replace("Plans must survive", "We note Supersedes: adr/a/old.md here. Plans must survive"))
    check("F3 prose in Context is not read as a header field", rc == 0, out)
    rc, out = run(GOOD.replace("Status: PROPOSED", "Status: Accepted"))
    check("QA-1 status is compared without case, like set-status", rc == 0, out)
    rc, out = run(GOOD.replace("Ticket:", "Supersedes: adr.md · Ticket:"))
    check("QA-2 an ADR cannot supersede itself", rc == 1 and "itself" in out, out)
    acc = GOOD.replace("Status: PROPOSED", "Status: ACCEPTED")
    rc, out = run(acc.replace("Ticket:", "Supersedes: old.md · Ticket:"), files={"old.md": acc.replace("APP-ADR-002", "APP-ADR-001")})
    check("QA-3 an accepted ADR may not supersede one that is still ACCEPTED", rc == 1 and "still" in out and "SUPERSEDED" in out, out)
    old_ok = acc.replace("APP-ADR-002", "APP-ADR-001").replace("Status: ACCEPTED", "Status: SUPERSEDED").replace("Ticket:", "Superseded by: adr.md · Ticket:")
    rc, out = run(acc.replace("Ticket:", "Supersedes: old.md · Ticket:"), files={"old.md": old_ok})
    check("QA-3 a closed chain passes", rc == 0, out)
    old_bad = old_ok.replace("Superseded by: adr.md", "Superseded by: other.md")
    rc, out = run(acc.replace("Ticket:", "Supersedes: old.md · Ticket:"), files={"old.md": old_bad, "other.md": GOOD})
    check("QA-3 the old ADR must point back at this one", rc == 1 and "point" in out, out)
    rc, out = run(GOOD.replace("Ticket:", "Supersedes: old.md · Ticket:"), files={"old.md": acc.replace("APP-ADR-002", "APP-ADR-001")})
    check("QA-3 a PROPOSED ADR may name an ACCEPTED one (chain closes later)", rc == 0, out)
    rc, out = run("# Plan: not an ADR\nStatus: PROPOSED · Ticket: none\n")
    check("not an ADR title fails", rc == 1 and "ADR" in out, out)
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), "--help"], capture_output=True, text=True)
    check("--help exits 0", r.returncode == 0, r.stderr)
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), "/nonexistent/adr.md"], capture_output=True, text=True)
    check("missing file exits 2", r.returncode == 2, str(r.returncode))
    if FAILS:
        print("\n".join(FAILS))
        print(f"{len(FAILS)} failure(s)")
        sys.exit(1)
    print("OK all check-adr tests passed")


if __name__ == "__main__":
    main()
