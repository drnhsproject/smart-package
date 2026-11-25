#!/usr/bin/env python3
"""Tests for skills/smart-spec/scripts/check-spec.py. Standard library only.

  python3 -I evals/test-check-spec.py

Exit 0: all pass. Exit 1: at least one failure.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "smart-spec" / "scripts" / "check-spec.py"
FAILS = []

GOOD = """# Spec: Export a report as CSV
Status: DRAFT · Revision: 1 · Ticket: APP-FEAT-001 · Run reference: csv-export + 2026-11-25

## Why
People copy the table by hand.

## Outcome
A report can be downloaded as CSV.

## Behaviour
- REQ-1: The export holds the rows the user sees.

## Acceptance criteria
- AC-1: The downloaded file has one line per visible row.
- AC-2: An empty report downloads a file with only the header line.

## Test approach
Test at the download route; assert the body.

## Not covered
Scheduled exports.
"""


def run(text, *extra, name="spec.md"):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / name
        p.write_text(text)
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), str(p), *extra], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr


def check(name, cond, detail=""):
    if not cond:
        FAILS.append(f"FAIL {name} {detail}")


def main():
    rc, out = run(GOOD)
    check("valid spec prints OK", rc == 0 and out.startswith("OK"), out)
    rc, out = run(GOOD.replace("## Test approach\nTest at the download route; assert the body.\n\n", ""))
    check("missing required heading fails", rc == 1 and "Test approach" in out, out)
    rc, out = run(GOOD.replace("- AC-2:", "- AC-1:"))
    check("duplicate AC-1 fails", rc == 1 and "AC-1" in out and "duplicate" in out.lower(), out)
    rc, out = run(GOOD.replace("Status: DRAFT", "Status: OPEN"))
    check("status outside the lifecycle fails", rc == 1 and "Status" in out, out)
    rc, out = run(GOOD.replace(" · Ticket: APP-FEAT-001", ""))
    check("missing Ticket fails", rc == 1 and "Ticket" in out, out)
    rc, out = run(GOOD.replace("Ticket: APP-FEAT-001", "Ticket: none"))
    check("Ticket: none is allowed", rc == 0, out)
    rc, out = run(GOOD.replace("assert the body.", "see `src/export.py:42` for the route."))
    check("cited file:line fails", rc == 1 and "file:line" in out, out)
    rc, out = run(GOOD.replace("assert the body.", "assert the body.\n\n```\nsrc/a.py:3 is only an example in code\n```"))
    check("file:line inside a code fence is allowed", rc == 0, out)
    rc, out = run(GOOD.replace("## Acceptance criteria\n- AC-1: The downloaded file has one line per visible row.\n- AC-2: An empty report downloads a file with only the header line.\n", "## Acceptance criteria\nThe export works.\n"))
    check("no AC-n at all fails", rc == 1 and "AC-" in out, out)
    rc, out = run(GOOD.replace("- AC-2: An empty report downloads a file with only the header line.", "| AC-2 | An empty report downloads only the header |"))
    check("an AC row that is not a `- AC-n:` list line fails", rc == 1 and "AC-n" in out, out)
    rc, out = run(GOOD.replace("- AC-2: An empty report downloads a file with only the header line.", "- AC-2: An empty report downloads a file\n  with only the header line."))
    check("an indented continuation line is allowed", rc == 0, out)
    prose = GOOD.replace("assert the body.", "serve it from example.com:8080, runtime Node.js:18, docs at http://x.io/a.html:4.")
    rc, out = run(prose)
    check("F3 host:port, Node.js:18 and URLs are not file:line", rc == 0, out)
    rc, out = run(GOOD.replace("assert the body.", "see Makefile:3 for the target."))
    check("F3 Makefile:3 is flagged", rc == 1 and "file:line" in out, out)
    rc, out = run(GOOD.replace("assert the body.", "see export.py:42 for the route."))
    check("F3 a bare source file with a line is flagged", rc == 1 and "file:line" in out, out)
    grouped = GOOD.replace("## Acceptance criteria\n", "## Acceptance criteria\nEach criterion is checked at the download route.\n\n### Export\n").replace("- AC-2:", "### Empty\n- AC-2:")
    rc, out = run(grouped)
    check("F4 subheadings and intro prose under Acceptance criteria are allowed", rc == 0, out)
    rc, out = run(GOOD.replace("assert the body.", "assert the body.\n\n~~~\nsrc/a.py:3 only an example\n~~~"))
    check("F5 a tilde fence hides its content", rc == 0, out)
    rc, out = run(GOOD.replace("assert the body.", "assert the body.\n\n  ```\n  src/a.py:3 only an example\n  ```"))
    check("F5 an indented fence hides its content", rc == 0, out)
    rc, out = run(GOOD + "\n## Acceptance criteria\n- AC-1: again\n")
    check("F5 a repeated required heading fails", rc == 1 and "repeated" in out.lower(), out)
    rc, out = run("\ufeff" + GOOD)
    check("QA-1 a spec saved with a UTF-8 BOM is read", rc == 0, out)
    rc, out = run(GOOD.replace("- AC-2:", "- ac-2:"))
    check("QA-2 a lowercase ac id is reported, not ignored", rc == 1 and "ac-2" in out.lower() and "AC-n" in out, out)
    rc, out = run("# Plan: not a spec\nStatus: DRAFT · Ticket: none\n")
    check("not a spec title fails", rc == 1 and "Spec" in out, out)
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), "--help"], capture_output=True, text=True)
    check("--help exits 0", r.returncode == 0, r.stderr)
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), "/nonexistent/spec.md"], capture_output=True, text=True)
    check("missing file exits 2", r.returncode == 2, str(r.returncode))
    if FAILS:
        print("\n".join(FAILS))
        print(f"{len(FAILS)} failure(s)")
        sys.exit(1)
    print("OK all check-spec tests passed")


if __name__ == "__main__":
    main()
