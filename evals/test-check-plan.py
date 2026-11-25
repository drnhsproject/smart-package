#!/usr/bin/env python3
"""Tests for skills/smart-plan/scripts/check-plan.py (the --spec trace and the analysis detection).

  python3 -I evals/test-check-plan.py

Standard library only. Exit 0: all pass. Exit 1: at least one failure.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "smart-plan" / "scripts" / "check-plan.py"
FAILS = []


def run(plan, *extra):
    p = subprocess.run([sys.executable, "-I", str(SCRIPT), str(plan), *map(str, extra)], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def check(name, cond, detail=""):
    if not cond:
        FAILS.append(f"FAIL {name} {detail}")


def task(n, accept, extra=""):
    return f"- [ ] T{n} change a thing — a.py · Accept: {accept} · Verify: `echo ok` · Test: none — docs{extra}\n"


def plan(tasks, head="", body="", series=""):
    return (f"# Plan: sample\nStatus: DRAFT · Revision: 1 · Ticket: none · Run reference: x\n{head}{series}\n"
            f"## Context\nwhy\n{body}\n## Findings\nnone\n\n## Tasks\n{tasks}\n## Verification\n- none\n\n## Execution log\n")


def spec(ids):
    items = "".join(f"- AC-{i}: criterion {i}\n" for i in ids)
    return f"# Spec: sample\nStatus: DRAFT · Revision: 1 · Ticket: none\n\n## Why\nw\n\n## Acceptance criteria\n{items}\n## Not covered\nn\n"


def write(d, name, text):
    p = Path(d) / name
    p.write_text(text)
    return p


def test_analysis_detection():
    with tempfile.TemporaryDirectory() as d:
        bad = plan("- [ ] T1 change a thing — a.py · Verify: `echo ok` · Test: none — docs\n",
                   body="The old script treats a text that quotes `# Analysis:` as an analysis.\n")
        rc, out = run(write(d, "q.md", bad), "--root", d)
        check("plan quoting the analysis title still gets task checks", rc == 1 and "Accept" in out, out)
        ana = "# Analysis: why\nStatus: FINAL · Run reference: x\n\n## Question\nq\n"
        rc, out = run(write(d, "a.md", ana), "--root", d)
        check("real analysis still passes", rc == 0 and "analysis" in out.lower(), out)


def test_spec_trace():
    with tempfile.TemporaryDirectory() as d:
        s = write(d, "spec.md", spec([1, 2, 3]))
        ok = write(d, "ok.md", plan(task(1, "AC-1 holds") + task(2, "AC-2 and AC-3 hold")))
        rc, out = run(ok, "--root", d, "--spec", s)
        check("all criteria cited and covered", rc == 0, out)
        unknown = write(d, "unk.md", plan(task(1, "AC-9 holds") + task(2, "AC-1 AC-2 AC-3")))
        rc, out = run(unknown, "--root", d, "--spec", s)
        check("unknown AC-9 fails", rc == 1 and "AC-9" in out, out)
        gap = write(d, "gap.md", plan(task(1, "AC-1 holds") + task(2, "AC-2 holds")))
        rc, out = run(gap, "--root", d, "--spec", s)
        check("uncovered AC-3 fails", rc == 1 and "AC-3" in out, out)
        none = write(d, "none.md", plan(task(1, "AC-1 AC-2 AC-3") + task(2, "works fine")))
        rc, out = run(none, "--root", d, "--spec", s)
        check("task without AC is a note, not a failure", rc == 0 and "NOTE" in out and "T2" in out, out)
        rc, out = run(ok, "--root", d)
        check("no --spec behaves as before", rc == 0 and "AC-" not in out, out)
        rc, out = run(ok, "--root", d, "--spec", Path(d) / "missing.md")
        check("missing spec file exits 2", rc == 2, out)


def test_series_coverage():
    with tempfile.TemporaryDirectory() as d:
        s = write(d, "spec.md", spec([1, 2]))
        p1 = write(d, "p1.md", plan(task(1, "AC-1 holds"), head="Part: 1 of 2 · Series: demo\n"))
        p2 = write(d, "p2.md", plan(task(2, "AC-2 holds"), head="Follows: p1.md · Part: 2 of 2 · Series: demo\n"))
        rc, out = run(p1, "--root", d, "--plans-dir", d, "--spec", s)
        check("a sibling part covers the other criterion", rc == 0, out)
        p2.unlink()
        rc, out = run(p1, "--root", d, "--plans-dir", d, "--spec", s)
        check("without the sibling AC-2 is uncovered", "AC-2" in out, out)


def main():
    test_analysis_detection()
    test_spec_trace()
    test_series_coverage()
    if FAILS:
        print("\n".join(FAILS))
        print(f"{len(FAILS)} failure(s)")
        sys.exit(1)
    print("OK all check-plan tests passed")


if __name__ == "__main__":
    main()
