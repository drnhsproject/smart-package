#!/usr/bin/env python3
"""Tests for skills/smart-guide/scripts/guide-state.py. Standard library only.

  python3 -I evals/test-guide-state.py

Exit 0: all pass. Exit 1: at least one failure.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "smart-guide" / "scripts" / "guide-state.py"
FAILS = []


def run(*args):
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def check(name, cond, detail=""):
    if not cond:
        FAILS.append(f"FAIL {name} {detail}")


def write(root, rel, text, age=0):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    if age:
        t = time.time() - age
        os.utime(p, (t, t))
    return rel


def plan(root, name, status, ticket="APP-FEAT-001", log=(), part=None, series=None, follows=None, age=0, title="Plan"):
    head = f"# {title}: demo {name}\nStatus: {status} · Revision: 1 · Ticket: {ticket} · Run reference: demo + 2026-11-25\n"
    extra = []
    if follows:
        extra.append(f"Follows: {follows}")
    if part:
        extra.append(f"Part: {part} · Series: {series}")
    head += (" · ".join(extra) + "\n") if extra else ""
    body = head + "\n## Execution log\n" + "".join(f"{ln}\n" for ln in log)
    return write(root, f".agents/plans/2026/11/25/{name}.md", body, age)


def spec(root, name, status, ticket="APP-FEAT-001", age=0):
    return write(root, f".agents/specs/{name}.md", f"# Spec: demo\nStatus: {status} · Revision: 1 · Ticket: {ticket}\n\n## Why\nx\n", age)


def adr(root, name, status, age=0):
    return write(root, f".agents/adr/{name}.md", f"# ADR: demo\nStatus: {status} · Ticket: APP-ADR-001\n\n## Context\nx\n", age)


def nexts(out):
    return [ln for ln in out.splitlines() if ln.startswith("NEXT:")]


def guide(root):
    rc, out = run("state", "--root", str(root))
    return rc, out, nexts(out)


QA_REPORT = ".agents/qa/2026/11/25/r-qa.md"
QA_LINE = f"2026-11-25 10:00 QA: FAIL · 2 findings · [[{QA_REPORT}]]"


def test_state_rows():
    rows = []
    with tempfile.TemporaryDirectory() as d:
        s = spec(d, "s1", "DRAFT")
        rc, out, n = guide(d)
        check("row spec DRAFT", rc == 0 and n and "review" in n[-1] and s in n[-1] and "/smart-plan" in n[-1], out)
    with tempfile.TemporaryDirectory() as d:
        s = spec(d, "s1", "APPROVED")
        rc, out, n = guide(d)
        check("row spec APPROVED with no plan", n and "/smart-plan" in n[-1] and s in n[-1], out)
    for status, word in (("DRAFT", "approve"), ("APPROVED", ""), ("IN PROGRESS", "resume")):
        with tempfile.TemporaryDirectory() as d:
            p = plan(d, "p1", status)
            rc, out, n = guide(d)
            check(f"row plan {status}", n and n[-1] == f"NEXT: /smart-implement {p}" and word in out.lower(), out)
    with tempfile.TemporaryDirectory() as d:
        p = plan(d, "p1", "DONE")
        rc, out, n = guide(d)
        check("row plan DONE with no QA", n and n[-1] == f"NEXT: /smart-qa {p}", out)
    with tempfile.TemporaryDirectory() as d:
        p = plan(d, "p1", "DONE", log=[QA_LINE, f"2026-11-25 10:00 QA-1 HIGH OPEN — x · a.py:1 · [[{QA_REPORT}]]",
                                         f"2026-11-25 10:00 QA-2 LOW OPEN — y · a.py:2 · [[{QA_REPORT}]]"])
        rc, out, n = guide(d)
        check("row QA with an open HIGH finding", n and n[-1] == f"NEXT: /smart-fix {QA_REPORT}", out)
    with tempfile.TemporaryDirectory() as d:
        p = plan(d, "p1", "DONE", log=[QA_LINE.replace("FAIL", "PASS WITH FOLLOW-UPS"),
                                         f"2026-11-25 10:00 QA-1 LOW OPEN — y · a.py:2 · [[{QA_REPORT}]]"])
        rc, out, n = guide(d)
        check("row QA with only a LOW finding open", n and n[-1] == f"NEXT: /smart-fix {QA_REPORT} --all", out)
    with tempfile.TemporaryDirectory() as d:
        p = plan(d, "p1", "DONE", log=[QA_LINE, f"2026-11-25 10:00 QA-1 HIGH OPEN — x · a.py:1 · [[{QA_REPORT}]]",
                                         f"2026-11-25 11:00 FIX: QA-1 FIXED — a.py · [[{QA_REPORT}]]"])
        rc, out, n = guide(d)
        check("row findings FIXED but not verified", n and n[-1] == f"NEXT: /smart-qa {p} --recheck", out)
    with tempfile.TemporaryDirectory() as d:
        clean = [QA_LINE.replace("FAIL", "PASS"), f"2026-11-25 10:00 QA-1 LOW OPEN — x · a.py:1 · [[{QA_REPORT}]]",
                 f"2026-11-25 11:00 QA-1 FIXED-VERIFIED — recheck · [[{QA_REPORT}]]"]
        p1 = plan(d, "p1", "DONE", part="1 of 2", series="s", log=clean)
        p2 = plan(d, "p2", "DRAFT", part="2 of 2", series="s", follows=p1)
        rc, out, n = guide(d)
        check("row QA clean with a later part", n and n[-1] == f"NEXT: /smart-implement {p2}", out)
        check("the next part is listed once", sum(1 for x in n if p2 in x) == 1, out)
    with tempfile.TemporaryDirectory() as d:
        p = plan(d, "p1", "DONE", log=[QA_LINE.replace("FAIL", "PASS") + ""])
        rc, out, n = guide(d)
        check("row QA clean, nothing follows", n and n[-1].startswith("NEXT: /smart-retro"), out)
    with tempfile.TemporaryDirectory() as d:
        a = adr(d, "a1", "PROPOSED")
        rc, out, n = guide(d)
        check("row ADR PROPOSED", n and "review" in n[-1] and a in n[-1], out)
    with tempfile.TemporaryDirectory() as d:
        adr(d, "a1", "ACCEPTED")
        rc, out, n = guide(d)
        check("an ACCEPTED ADR leaves nothing pending", n == ["NEXT: nothing pending"], out)
    with tempfile.TemporaryDirectory() as d:
        rc, out, n = guide(d)
        check("empty project", rc == 0 and n == ["NEXT: /smart-plan <task>"], out)
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init", "-q"], cwd=d)
        Path(d, "x.py").write_text("x = 1\n")
        rc, out, n = guide(d)
        check("uncommitted changes and no plan", n == ["NEXT: /smart-plan <task>"] and "uncommitted" in out, out)


def test_ordering_and_blocking():
    with tempfile.TemporaryDirectory() as d:
        p1 = plan(d, "p1", "IN PROGRESS", part="1 of 2", series="s")
        p2 = plan(d, "p2", "DRAFT", part="2 of 2", series="s", follows=p1)
        rc, out, n = guide(d)
        check("a part blocked by an unfinished predecessor is not recommended", n == [f"NEXT: /smart-implement {p1}"] and p2 not in "".join(n), out)
    with tempfile.TemporaryDirectory() as d:
        old = plan(d, "old", "DRAFT", ticket="APP-FEAT-001", age=5000)
        new = plan(d, "new", "DRAFT", ticket="APP-FEAT-002", age=10)
        rc, out, n = guide(d)
        check("the newest work item gets the final NEXT", n and n[-1] == f"NEXT: /smart-implement {new}", out)
        check("both items are listed", old in out and new in out, out)
    with tempfile.TemporaryDirectory() as d:
        for i in range(7):
            plan(d, f"p{i}", "DRAFT", ticket=f"APP-FEAT-00{i}", age=100 * i)
        rc, out, n = guide(d)
        check("at most 5 items are listed", out.count("NEXT: /smart-implement") <= 6 and "more" in out, out)
    with tempfile.TemporaryDirectory() as d:
        p = plan(d, "p1", "DONE", part="1 of 2", series="s", log=[QA_LINE, f"2026-11-25 10:00 QA-1 HIGH OPEN — x · a.py:1 · [[{QA_REPORT}]]",
                                                             f"2026-11-25 11:00 FIX: QA-1 FIXED — a.py · [[{QA_REPORT}]]"])
        p2 = plan(d, "p2", "DRAFT", part="2 of 2", series="s", follows=p)
        rc, out, n = guide(d)
        check("FIXED findings come before the next part", n and n[-1] == f"NEXT: /smart-qa {p} --recheck", out)


def test_none_bom_symlink_owner():
    with tempfile.TemporaryDirectory() as d:
        s = spec(d, "s1", "APPROVED", ticket="none")
        plan(d, "p1", "DONE", ticket="none", log=[QA_LINE.replace("FAIL", "PASS")])
        rc, out, n = guide(d)
        check("a ticket none Spec is not attached to an unrelated none plan", any("/smart-plan" in x and s in x for x in n) or s in out and "/smart-plan" in out, out)
    with tempfile.TemporaryDirectory() as d:
        s = spec(d, "s1", "APPROVED", ticket="none")
        plan(d, "p1", "DONE", ticket="none", follows=s, log=[QA_LINE.replace("FAIL", "PASS")])
        rc, out, n = guide(d)
        check("a Spec named in Follows is attached even with ticket none", s not in "".join(n), out)
    with tempfile.TemporaryDirectory() as d:
        p = f".agents/plans/p.md"
        Path(d, ".agents/plans").mkdir(parents=True)
        Path(d, p).write_bytes(b"\xef\xbb\xbf" + "# Plan: x\r\nStatus: DRAFT · Ticket: APP-FEAT-001\r\n\r\n## Execution log\r\n".encode())
        rc, out, n = guide(d)
        check("a BOM and CRLF plan is read", n == [f"NEXT: /smart-implement {p}"], out)
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
        leak = Path(outside) / "leak.md"
        leak.write_text("# Plan: leak\nStatus: DRAFT · Ticket: APP-FEAT-009\n\n## Execution log\n")
        Path(d, ".agents/plans").mkdir(parents=True)
        (Path(d) / ".agents/plans/leak.md").symlink_to(leak)
        rc, out, n = guide(d)
        check("a symlink that leaves the project is not read", rc == 0 and "APP-FEAT-009" not in out, out)
    with tempfile.TemporaryDirectory() as d:
        plan(d, "p1", "DONE", log=[QA_LINE.replace("FAIL", "PASS"),
                                   "2026-11-25 10:00 APP-FEAT-001-T3 OWNER-VERIFY pending — run the paid trigger test",
                                   "2026-11-25 10:00 APP-FEAT-001-T4 OWNER-VERIFY pending — look at the screen",
                                   "2026-11-25 11:00 APP-FEAT-001-T4 OWNER-VERIFY done — reported by the user, not run by the agent"])
        rc, out, n = guide(d)
        check("a pending OWNER-VERIFY is a note", "NOTE:" in out and "APP-FEAT-001-T3" in out and "APP-FEAT-001-T4" not in out.split("NOTE:")[1], out)
    with tempfile.TemporaryDirectory() as d:
        rc, out = run("state", "--root", str(Path(d) / "nowhere"))
        check("a missing root is exit 2", rc == 2 and "not a directory" in out, out)


def test_follows_cycle():
    with tempfile.TemporaryDirectory() as d:
        pa = ".agents/plans/a.md"
        pb = ".agents/plans/b.md"
        write(d, pa, f"# Plan: a\nStatus: DRAFT · Ticket: T-1\nFollows: {pb}\n")
        write(d, pb, f"# Plan: b\nStatus: DRAFT · Ticket: T-2\nFollows: {pa}\n")
        rc, out, n = guide(d)
        check("plans that follow each other are still listed", rc == 0 and n and n != ["NEXT: nothing pending"] and "/smart-implement" in n[-1], out)
    with tempfile.TemporaryDirectory() as d:
        pa = ".agents/plans/a.md"
        write(d, pa, f"# Plan: a\nStatus: DRAFT · Ticket: T-1\nFollows: {pa}\n")
        rc, out, n = guide(d)
        check("a plan that follows itself is still listed", rc == 0 and n and "/smart-implement" in n[-1], out)


def test_review_fixes():
    import shlex
    clean_log = [QA_LINE.replace("FAIL", "PASS")]
    # G-1 no --ticket=none
    with tempfile.TemporaryDirectory() as d:
        plan(d, "p2", "DONE", ticket="none", part="2 of 3", series="s", log=clean_log)
        rc, out, n = guide(d)
        check("G-1 no --ticket=none is printed", rc == 0 and "--ticket=none" not in out and n and n[-1].startswith("NEXT: /smart-plan"), out)
    # G-2 plans with no Series do not match each other
    with tempfile.TemporaryDirectory() as d:
        a = write(d, ".agents/plans/a.md", "# Plan: a\nStatus: DONE · Ticket: A-1 · Part: 1 of 2\n\n## Execution log\n" + clean_log[0] + "\n")
        write(d, ".agents/plans/b.md", "# Plan: b\nStatus: DONE · Ticket: B-2 · Part: 2 of 3\n\n## Execution log\n" + clean_log[0] + "\n", age=100)
        rc, out, n = guide(d)
        check("G-2 a plan with no Series is not matched to an unrelated part", "--ticket=A-1" in out, out)
    # G-3 CRLF and G-4 a heading with extra text
    with tempfile.TemporaryDirectory() as d:
        text = "# Plan: x\r\nStatus: DONE · Ticket: T-1\r\n\r\n## Execution log\r\n" + clean_log[0] + "\r\n"
        write(d, ".agents/plans/c.md", "")
        Path(d, ".agents/plans/c.md").write_bytes(text.encode())
        rc, out, n = guide(d)
        check("G-3 a CRLF plan's QA line is found", n and n[-1].startswith("NEXT: /smart-retro"), out)
    with tempfile.TemporaryDirectory() as d:
        write(d, ".agents/plans/h.md", "# Plan: x\nStatus: DONE · Ticket: T-1\n\n## Execution log (rev 2)\n" + clean_log[0] + "\n")
        rc, out, n = guide(d)
        check("G-4 a heading with extra text after Execution log is found", n and n[-1].startswith("NEXT: /smart-retro"), out)
    # G-5 quoting and control characters
    with tempfile.TemporaryDirectory() as d:
        write(d, ".agents/plans/my plan.md", "# Plan: x\nStatus: DRAFT · Ticket: T-1\n")
        rc, out, n = guide(d)
        parts = shlex.split(n[-1][len("NEXT: "):]) if n else []
        check("G-5 a path with a space is one argument", parts == ["/smart-implement", ".agents/plans/my plan.md"], out)
    with tempfile.TemporaryDirectory() as d:
        report = "a b; $(id)/r.md"
        write(d, ".agents/plans/q.md", "# Plan: x\nStatus: DONE · Ticket: T-1\n\n## Execution log\n"
              f"2026-11-25 10:00 QA: FAIL · 1 findings · [[{report}]]\n2026-11-25 10:00 QA-1 HIGH OPEN — x · a.py:1 · [[{report}]]\n")
        rc, out, n = guide(d)
        parts = shlex.split(n[-1][len("NEXT: "):]) if n else []
        check("G-5 a report link with shell characters stays one argument", parts == ["/smart-fix", report], out)
    with tempfile.TemporaryDirectory() as d:
        write(d, ".agents/specs/s.md", "# Spec: x\nStatus: DRAFT · Ticket: X; rm -rf ~\n")
        rc, out, n = guide(d)
        check("G-5 a ticket with shell characters is quoted", n and "--ticket='X; rm -rf ~'" in n[-1], out)
    with tempfile.TemporaryDirectory() as d:
        write(d, ".agents/plans/e.md", "# Plan: x\nStatus: DRAFT · Ticket: T\x9b2J\u202e1\n")
        rc, out, n = guide(d)
        check("G-5 C1 and bidirectional control characters are removed", "\x9b" not in out and "\u202e" not in out, repr(out))
    # G-6 git is run without optional locks and without the repository's fsmonitor helper
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as shim:
        log = Path(shim) / "git.log"
        fake = Path(shim) / "git"
        fake.write_text("#!/bin/sh\necho \"$@ LOCKS=$GIT_OPTIONAL_LOCKS\" >> " + str(log) + "\nexit 0\n")
        fake.chmod(0o755)
        env = dict(os.environ, PATH=f"{shim}{os.pathsep}{os.environ['PATH']}")
        subprocess.run([sys.executable, "-I", str(SCRIPT), "state", "--root", d], capture_output=True, text=True, env=env)
        seen = log.read_text() if log.exists() else ""
        check("G-6 git runs with core.fsmonitor off and optional locks off", "core.fsmonitor=false" in seen and "LOCKS=0" in seen, seen)


def skill(root, folder, text):
    p = Path(root) / folder
    p.mkdir(parents=True)
    (p / "SKILL.md").write_text(text)


def test_skills():
    with tempfile.TemporaryDirectory() as d:
        skill(d, "smart-a", "---\nname: smart-a\ndescription: Does A well. Use when asked for A.\nlicense: MIT\n---\nbody\n")
        skill(d, "smart-b", "---\nname: smart-b\ndescription: Does B\x1b[31m red\x1b[0m without a full stop\n---\n")
        skill(d, "broken", "no frontmatter here\n")
        (Path(d) / "not-a-skill").mkdir()
        rc, out = run("skills", "--dir", d)
        check("skills exits 0", rc == 0, out)
        check("a good skill shows name and first sentence", "smart-a · Does A well." in out and "Use when" not in out, out)
        check("a skill without a full stop shows its whole description", "smart-b · Does B" in out and "without a full stop" in out, out)
        check("control characters are stripped", "\x1b" not in out, repr(out))
        check("a damaged skill is reported, not skipped", "broken · unreadable" in out, out)
        check("a folder without SKILL.md is ignored", "not-a-skill" not in out, out)
        rc, out = run("skills", "--dir", str(Path(d) / "nowhere"))
        check("a missing skills folder is exit 2", rc == 2, out)


def test_qa_report_fixes():
    # QA-1: a symlinked skill folder is read; a SKILL.md that leaves its own folder is not
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as elsewhere:
        skill(elsewhere, "smart-x", "---\nname: smart-x\ndescription: Does X. More.\n---\n")
        (Path(d) / "smart-x").symlink_to(Path(elsewhere) / "smart-x")
        secret = Path(elsewhere) / "secret.md"
        secret.write_text("---\nname: leaked\ndescription: Leaked text.\n---\n")
        (Path(d) / "bad").mkdir()
        (Path(d) / "bad" / "SKILL.md").symlink_to(secret)
        rc, out = run("skills", "--dir", d)
        check("QA-1 a symlinked skill folder shows its name and sentence", "smart-x · Does X." in out, out)
        check("QA-1 a SKILL.md that leaves its folder is unreadable and not read", "bad · unreadable" in out and "Leaked" not in out, out)
    # QA-2: a DEFERRED finding is unfinished work, not a clean plan
    deferred = [QA_LINE, f"2026-11-25 10:00 QA-1 HIGH OPEN — big · a.py:1 · [[{QA_REPORT}]]",
                f"2026-11-25 11:00 FIX: QA-1 DEFERRED — needs a contract change · [[{QA_REPORT}]]"]
    with tempfile.TemporaryDirectory() as d:
        p = plan(d, "p1", "DONE", log=deferred)
        rc, out, n = guide(d)
        check("QA-2 a DEFERRED finding gets /smart-plan, not /smart-retro", n and n[-1].startswith("NEXT: /smart-plan") and p in n[-1], out)
    with tempfile.TemporaryDirectory() as d:
        p = plan(d, "p1", "DONE", log=deferred)
        plan(d, "p2", "DRAFT", ticket="APP-FEAT-002", follows=p)
        rc, out, n = guide(d)
        check("QA-2 once a follow-up plan exists the DEFERRED item is not repeated", "/smart-plan" not in "".join(n), out)
    # QA-3: only the id that starts an entry takes that entry's state
    with tempfile.TemporaryDirectory() as d:
        plan(d, "p1", "DONE", log=[QA_LINE.replace("FAIL", "PASS WITH FOLLOW-UPS"),
             f"2026-11-25 10:00 QA-3 LOW OPEN — a · a.py:1 · [[{QA_REPORT}]]",
             f"2026-11-25 11:00 QA-3 FIXED-VERIFIED — recheck · [[{QA_REPORT}]]",
             f"2026-11-25 12:00 QA-5 LOW OPEN — same root as QA-3 (OPEN until deployed) · b.py:2 · [[{QA_REPORT}]]",
             f"2026-11-25 12:30 QA-5 FIXED-VERIFIED — recheck · [[{QA_REPORT}]]"])
        rc, out, n = guide(d)
        check("QA-3 a mention of QA-3 inside QA-5's text does not reopen QA-3", n and n[-1].startswith("NEXT: /smart-retro"), out)
    with tempfile.TemporaryDirectory() as d:
        plan(d, "p1", "DONE", log=[QA_LINE, f"2026-11-25 10:00 QA-1 HIGH OPEN — fix FIXED soon · a.py:1 · [[{QA_REPORT}]]"])
        rc, out, n = guide(d)
        check("QA-3 a state word inside the summary is not the state", n and n[-1] == f"NEXT: /smart-fix {QA_REPORT}", out)
    # QA-4: Follows written as ./path, ../ or an absolute path still blocks the successor
    for form in ("./.agents/plans/2026/11/25/a.md", ".agents/plans/2026/11/25/../25/a.md", "ABS"):
        with tempfile.TemporaryDirectory() as d:
            a = plan(d, "a", "IN PROGRESS")
            value = str((Path(d).resolve() / a)) if form == "ABS" else form
            plan(d, "b", "DRAFT", ticket="APP-FEAT-002", follows=value)
            rc, out, n = guide(d)
            check(f"QA-4 Follows written as {'an absolute path' if form == 'ABS' else form} blocks the successor", n == [f"NEXT: /smart-implement {a}"], out)


def test_round2_fixes():
    # QA-5: Follows is normalised lexically, so a symlinked plans folder still blocks the successor
    with tempfile.TemporaryDirectory() as d:
        Path(d, "shared").mkdir()
        Path(d, ".agents").mkdir()
        (Path(d) / ".agents" / "plans").symlink_to(Path(d) / "shared")
        (Path(d) / "shared" / "a.md").write_text("# Plan: a\nStatus: IN PROGRESS · Ticket: T-1\n")
        (Path(d) / "shared" / "b.md").write_text("# Plan: b\nStatus: DRAFT · Ticket: T-2\nFollows: .agents/plans/a.md\n")
        rc, out, n = guide(d)
        check("QA-5 a symlinked plans folder still blocks the successor", n == ["NEXT: /smart-implement .agents/plans/a.md"], out)
    for form in ("resolved", "given"):
        with tempfile.TemporaryDirectory() as d:
            a = plan(d, "a", "IN PROGRESS")
            base = str(Path(d).resolve()) if form == "resolved" else str(d)
            plan(d, "b", "DRAFT", ticket="APP-FEAT-002", follows=f"{base}/{a}")
            rc, out, n = guide(d)
            check(f"QA-5 an absolute Follows written with the {form} root blocks the successor", n == [f"NEXT: /smart-implement {a}"], out)
    with tempfile.TemporaryDirectory() as d:
        a = plan(d, "a", "IN PROGRESS")
        plan(d, "b", "DRAFT", ticket="APP-FEAT-002", follows="/somewhere/else/a.md")
        rc, out, n = guide(d)
        check("QA-5 a Follows outside the project does not block and does not crash", rc == 0 and ".agents/plans/2026/11/25/b.md" in out, out)
    # QA-6: several ids on one line, a bullet prefix, a lowercase fix:
    two_open = [QA_LINE, f"2026-11-25 10:00 QA-1 HIGH OPEN — x · a.py:1 · [[{QA_REPORT}]]",
                f"2026-11-25 10:00 QA-2 HIGH OPEN — y · a.py:2 · [[{QA_REPORT}]]"]
    cases = {
        "a leading list of ids": "2026-11-25 11:00 FIX: QA-1, QA-2 FIXED — x",
        "an id list joined by and": "2026-11-25 11:00 FIX: QA-1 and QA-2 FIXED — x",
        "an id each with its state": "2026-11-25 11:00 FIX: QA-1 FIXED, QA-2 FIXED — x",
        "a lowercase fix:": "2026-11-25 11:00 fix: QA-1, QA-2 FIXED — x",
        "a bullet prefix": "- 2026-11-25 11:00 FIX: QA-1, QA-2 FIXED — x",
    }
    for name, line in cases.items():
        with tempfile.TemporaryDirectory() as d:
            p = plan(d, "p1", "DONE", log=two_open + [line])
            rc, out, n = guide(d)
            check(f"QA-6 {name} updates both ids", n == [f"NEXT: /smart-qa {p} --recheck"], out)
    with tempfile.TemporaryDirectory() as d:
        plan(d, "p1", "DONE", log=two_open + ["2026-11-25 12:00 QA-1,QA-2 FIXED-VERIFIED — recheck"])
        rc, out, n = guide(d)
        check("QA-6 ids joined by a comma with no space are both verified", n and n[-1].startswith("NEXT: /smart-retro"), out)
    with tempfile.TemporaryDirectory() as d:
        plan(d, "p1", "DONE", log=two_open + ["2026-11-25 11:00 FIX: QA-1 FIXED — also touches QA-2 (OPEN)"])
        rc, out, n = guide(d)
        check("QA-6 an id named after the dash is still only a mention", n == [f"NEXT: /smart-fix {QA_REPORT}"], out)
    with tempfile.TemporaryDirectory() as d:
        plan(d, "p1", "DONE", log=[QA_LINE.replace("FAIL", "PASS"), f"2026-11-25 10:00 QA-1 LOW OPEN — a · a.py:1 · [[{QA_REPORT}]]",
                                   "2026-11-25 11:00 FIX: QA-1 FIXED (was QA-2 OPEN) — x"])
        rc, out, n = guide(d)
        check("QA-6 an id named in brackets before the dash is not an assignment", n == [f"NEXT: /smart-qa .agents/plans/2026/11/25/p1.md --recheck"], out)


def main():
    test_state_rows()
    test_ordering_and_blocking()
    test_none_bom_symlink_owner()
    test_follows_cycle()
    test_review_fixes()
    test_skills()
    test_qa_report_fixes()
    test_round2_fixes()
    if FAILS:
        print("\n".join(FAILS))
        return 1
    print("OK all guide-state tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
