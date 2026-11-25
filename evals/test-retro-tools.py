#!/usr/bin/env python3
"""Tests for skills/smart-retro/scripts/retro-tools.py. Standard library only.

  python3 -I evals/test-retro-tools.py

Exit 0: all pass. Exit 1: at least one failure.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "smart-retro" / "scripts" / "retro-tools.py"
FAILS = []

PLAN = """# Plan: Demo
Status: IN PROGRESS · Revision: 1 · Ticket: APP-FIX-001 · Run reference: demo + 2026-11-25

## Execution log
2026-11-25 10:00 approved
2026-11-25 10:10 APP-FIX-001-T1 done — a.py
2026-11-25 11:00 QA: FAIL · 2 findings · [[x]]
2026-11-25 11:00 QA-1 HIGH OPEN — bad thing · a.py:1 · [[x]]
2026-11-25 11:00 QA-2 LOW OPEN — small thing · a.py:2 · [[x]]
2026-11-25 12:00 FIX: QA-1 FIXED — a.py
2026-11-25 13:00 QA-1 FIXED-VERIFIED — recheck
"""

CHANGELOG = """# Changelog fixes

### Fix #3 — Third
| x | y |

### Fix #2 — Second

### Fix #1 — First
"""


def run(*args):
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def check(name, cond, detail=""):
    if not cond:
        FAILS.append(f"FAIL {name} {detail}")


def make_project(root):
    plans = root / ".agents" / "plans" / "2026" / "11" / "25"
    plans.mkdir(parents=True)
    (plans / "2026-11-25-APP-FIX-001-demo.md").write_text(PLAN)
    (root / "CHANGELOG_FIXES.md").write_text(CHANGELOG)
    (root / "handoffs").mkdir()
    (root / "handoffs" / "api-demo.md").write_text("# Demo work\nStatus: DITUNDA · Service: api\n\n## Next\n- x\n")


def test_digest():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        make_project(root)
        rc, out = run("digest", "--root", str(root), "--since", "2020-01-01")
        check("digest exits 0", rc == 0, out)
        check("digest lists the plan with its status", "2026-11-25-APP-FIX-001-demo.md" in out and "IN PROGRESS" in out, out)
        check("digest shows the last log lines", "QA-1 FIXED-VERIFIED" in out, out)
        check("digest gives the latest state of QA-1", "QA-1 FIXED-VERIFIED" in out and "QA-2 OPEN" in out, out)
        check("digest names the next fix number", "next: #4" in out, out)
        check("digest lists top fix headings", "### Fix #3" in out and "### Fix #1" in out, out)
        check("digest lists the handoff with status and size", "handoffs/api-demo.md" in out and "DITUNDA" in out and "5 lines" in out, out)
        check("digest says not a git repository", "not a git repository" in out, out)
    with tempfile.TemporaryDirectory() as d:
        rc, out = run("digest", "--root", d)
        check("empty project exits 0", rc == 0, out)
        check("empty project prints none sections", out.count("none") >= 4, out)
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        make_project(root)
        rc, out = run("digest", "--root", str(root), "--since", "2999-01-01")
        check("a future date hides the plan", rc == 0 and "APP-FIX-001-demo.md" not in out, out)
        rc, out = run("digest", "--root", str(root), "--since", "soon")
        check("a bad --since is exit 2", rc == 2, out)


def test_check_changelog():
    ok = "### Fix #3 — C\n\n### Fix #2 — B\n\n### Fix #1 — A\n"
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "CHANGELOG_FIXES.md"
        f.write_text(ok)
        rc, out = run("check-changelog", str(f))
        check("ordered changelog is OK", rc == 0 and out.startswith("OK"), out)
        f.write_text("### Fix #2 — B\n\n### Fix #3 — C\n")
        rc, out = run("check-changelog", str(f))
        check("first entry not the highest fails", rc == 1 and "#3" in out, out)
        f.write_text("### Fix #3 — C\n\n### Fix #2 — B\n\n### Fix #2 — B again\n")
        rc, out = run("check-changelog", str(f))
        check("a repeated number fails", rc == 1 and "#2" in out and "repeat" in out.lower(), out)
        f.write_text("### Fix #38b — late\n\n### Fix #38 — first\n\n### Fix #37 — old\n")
        rc, out = run("check-changelog", str(f))
        check("a letter suffix is allowed once", rc == 0, out)
        f.write_text("### Fix #38b — late\n\n### Fix #38b — twice\n")
        rc, out = run("check-changelog", str(f))
        check("a repeated suffix fails", rc == 1, out)
        f.write_text("no entries here\n")
        rc, out = run("check-changelog", str(f))
        check("no entries is OK with a note", rc == 0 and "no entries" in out.lower(), out)
        rc, out = run("check-changelog", str(Path(d) / "missing.md"))
        check("a missing file is exit 2", rc == 2, out)


def test_check_handoff():
    good = "# Work\nStatus: DITUNDA\n\n## Next\n- x\n"
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "h.md"
        f.write_text(good)
        rc, out = run("check-handoff", str(f))
        check("good handoff is OK", rc == 0 and out.startswith("OK"), out)
        f.write_text("# Work\nStatus: X\n" + "line\n" * 148)
        rc, out = run("check-handoff", str(f))
        check("150 lines is OK", rc == 0, out)
        f.write_text("# Work\nStatus: X\n" + "line\n" * 149)
        rc, out = run("check-handoff", str(f))
        check("151 lines fails", rc == 1 and "151" in out, out)
        f.write_text("Status: X\n\n## Next\n")
        rc, out = run("check-handoff", str(f))
        check("no title fails", rc == 1 and "title" in out.lower(), out)
        f.write_text("# Work\n\n## Next\n")
        rc, out = run("check-handoff", str(f))
        check("no Status line fails", rc == 1 and "Status" in out, out)
        f.write_bytes(b"\xef\xbb\xbf" + good.encode())
        rc, out = run("check-handoff", str(f))
        check("a byte order mark is read through", rc == 0, out)


def test_review_fixes():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        plans = root / ".agents" / "plans"
        plans.mkdir(parents=True)
        (plans / "two.md").write_text(
            "# Plan: x\nStatus: DONE · Ticket: none\n\n## Execution log\n"
            "2026-11-25 10:00 QA-1 OPEN, QA-2 FIXED-VERIFIED\n"
            "2026-11-25 10:05 QA-3 FIXED then reopened OPEN\n"
            "\n## Notes\nQA-9 FIXED-VERIFIED in a note\nlast note line\n")
        rc, out = run("digest", "--root", str(root), "--since", "2020-01-01")
        check("R1 two ids on one line keep their own state", "QA-1 OPEN" in out and "QA-2 FIXED-VERIFIED" in out, out)
        check("R1 the first state word after the id wins", "QA-3 FIXED" in out and "QA-3 OPEN" not in out, out)
        check("R3 a later section is not part of the log", "QA-9" not in out and "last note line" not in out, out)
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        plans = root / ".agents" / "plans"
        plans.mkdir(parents=True)
        (plans / "broken.md").symlink_to(root / "nowhere")
        (plans / "dir.md").mkdir()
        (plans / "ok.md").write_text("# Plan: ok\nStatus: DRAFT\n")
        (root / "handoffs").mkdir()
        (root / "handoffs" / "dir.md").mkdir()
        rc, out = run("digest", "--root", str(root), "--since", "2020-01-01")
        check("R2 broken symlink and directories do not crash digest", rc == 0 and "Traceback" not in out, out)
        check("R2 the good plan is still listed", "ok.md" in out, out)
        check("R2 the rest of the digest still prints", "== handoffs ==" in out, out)


def test_qa_report_fixes():
    # QA-1: a huge or unrepresentable --since is a usage error, never a traceback
    with tempfile.TemporaryDirectory() as d:
        for value in ("99999999d", "0001-01-01", "36501d"):
            rc, out = run("digest", "--root", d, "--since", value)
            check(f"QA-1 --since {value} exits 2 without a traceback", rc == 2 and "Traceback" not in out, out)
        for value in ("36500d", "2000-01-01"):
            rc, out = run("digest", "--root", d, "--since", value)
            check(f"QA-1 --since {value} still works", rc == 0, out)
    # QA-2: a symlink that leaves the project is never read
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
        root = Path(d)
        (root / ".agents" / "plans").mkdir(parents=True)
        (root / "handoffs").mkdir()
        leak_h = Path(outside) / "h.md"
        leak_h.write_text("Status: LEAKED-STATUS\n")
        leak_p = Path(outside) / "p.md"
        leak_p.write_text("# Plan\nStatus: DONE\n## Execution log\nLEAKED-LOG\n")
        leak_c = Path(outside) / "c.md"
        leak_c.write_text("### Fix #99 — LEAKED-FIX\n")
        (root / "handoffs" / "x.md").symlink_to(leak_h)
        (root / ".agents" / "plans" / "y.md").symlink_to(leak_p)
        (root / "CHANGELOG_FIXES.md").symlink_to(leak_c)
        (root / "handoffs" / "in.md").write_text("# In\nStatus: RUNNING\n")
        (root / "handoffs" / "link-in.md").symlink_to(root / "handoffs" / "in.md")
        rc, out = run("digest", "--root", str(root), "--since", "2020-01-01")
        check("QA-2 digest exits 0", rc == 0, out)
        check("QA-2 nothing from outside the project is printed", "LEAKED" not in out and "#99" not in out, out)
        check("QA-2 a skipped file is named", out.count("outside the project") >= 2, out)
        check("QA-2 a symlink that stays inside is still read", "link-in.md" in out and out.count("RUNNING") >= 2, out)
    # QA-3: a root that is not a directory is a usage error
    with tempfile.TemporaryDirectory() as d:
        rc, out = run("digest", "--root", str(Path(d) / "nowhere"))
        check("QA-3 a missing root exits 2", rc == 2 and "not a directory" in out, out)
        f = Path(d) / "file.txt"
        f.write_text("x")
        rc, out = run("digest", "--root", str(f))
        check("QA-3 a file as root exits 2", rc == 2 and "not a directory" in out, out)


def main():
    test_digest()
    test_check_changelog()
    test_check_handoff()
    test_review_fixes()
    test_qa_report_fixes()
    if FAILS:
        print("\n".join(FAILS))
        return 1
    print("OK all retro-tools tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
