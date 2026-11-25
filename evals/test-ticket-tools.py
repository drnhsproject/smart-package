#!/usr/bin/env python3
"""Tests for skills/smart-plan/scripts/ticket-tools.py. Standard library only.

  python3 -I evals/test-ticket-tools.py

Builds throwaway projects in a temp directory and runs the script as a user would.
Exit 0: all pass. Exit 1: at least one failure.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "smart-plan" / "scripts" / "ticket-tools.py"
FAILS = []


def run(*args):
    p = subprocess.run([sys.executable, "-I", str(SCRIPT), *map(str, args)], capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def check(name, cond, detail=""):
    if not cond:
        FAILS.append(f"FAIL {name} {detail}")


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_suggest():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "smart-plan"
        write(root, ".agents/plans/2026/11/25/a.md", "# Plan: a\nStatus: DRAFT · Revision: 1 · Ticket: SMARTPLAN-FEAT-002 · Run reference: a\n")
        write(root, ".agents/specs/2026/11/25/b.md", "# Spec: b\nStatus: DRAFT · Revision: 1 · Ticket: SMARTPLAN-FEAT-001\n")
        write(root, ".agents/adr/2026/11/25/c.md", "# ADR: c\nStatus: PROPOSED · Ticket: SMARTPLAN-ADR-007\n")
        rc, out, _ = run("suggest", "feat", "--root", root)
        check("suggest next feat", (rc, out) == (0, "SMARTPLAN-FEAT-003"), f"{rc} {out!r}")
        rc, out, _ = run("suggest", "FIX", "--root", root)
        check("suggest first fix", (rc, out) == (0, "SMARTPLAN-FIX-001"), f"{rc} {out!r}")
        rc, out, _ = run("suggest", "adr", "--root", root)
        check("suggest adr counts adr folder", (rc, out) == (0, "SMARTPLAN-ADR-008"), f"{rc} {out!r}")
        rc, _, _ = run("suggest", "bogus", "--root", root)
        check("suggest unknown type exits 2", rc == 2, str(rc))
    with tempfile.TemporaryDirectory() as d:
        write(d, "package.json", json.dumps({"name": "@acme/web-app"}))
        rc, out, _ = run("suggest", "chore", "--root", d)
        check("suggest app from package.json scope", (rc, out) == (0, "WEBAPP-CHORE-001"), f"{rc} {out!r}")
    with tempfile.TemporaryDirectory() as d:
        write(d, "pyproject.toml", '[project]\nname = "my_tool"\n')
        rc, out, _ = run("suggest", "docs", "--root", d)
        check("suggest app from pyproject", (rc, out) == (0, "MYTOOL-DOCS-001"), f"{rc} {out!r}")
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "Billing Service"
        root.mkdir()
        rc, out, _ = run("suggest", "perf", "--root", root)
        check("suggest app from folder", (rc, out) == (0, "BILLINGSERVICE-PERF-001"), f"{rc} {out!r}")


def test_find():
    with tempfile.TemporaryDirectory() as d:
        write(d, ".agents/plans/2026/11/25/p.md", "# Plan: p\nStatus: IN PROGRESS · Revision: 1 · Ticket: APP-FEAT-001\n")
        write(d, ".agents/specs/2026/11/25/s.md", "# Spec: s\nStatus: APPROVED · Revision: 1 · Ticket: APP-FEAT-001\n")
        write(d, ".agents/plans/2026/11/25/o.md", "# Plan: o\nStatus: DRAFT · Revision: 1 · Ticket: APP-FEAT-002\n")
        rc, out, _ = run("find", "APP-FEAT-001", "--root", d)
        lines = out.splitlines()
        check("find lists two docs", rc == 0 and len(lines) == 2, out)
        check("find shows kind and status", any(l.startswith("plan\tIN PROGRESS\t") for l in lines) and any(l.startswith("spec\tAPPROVED\t") for l in lines), out)
        rc, out, _ = run("find", "APP-FEAT-099", "--root", d)
        check("find nothing prints nothing", rc == 0 and out == "", out)


def test_set_status():
    with tempfile.TemporaryDirectory() as d:
        spec = write(d, "s.md", "# Spec: s\nStatus: DRAFT · Revision: 1 · Ticket: APP-FEAT-001\n\n## Why\nStatus: not a header line\n")
        before = spec.read_text()
        rc, _, _ = run("set-status", spec, "APPROVED")
        after = spec.read_text()
        check("spec draft to approved", rc == 0 and "Status: APPROVED · Revision: 1" in after, after)
        check("only the status line changed", after.replace("APPROVED", "DRAFT", 1) == before, after)
        rc, _, _ = run("set-status", spec, "DONE")
        check("spec approved to done", rc == 0)
        rc, _, err = run("set-status", spec, "DRAFT")
        check("done to draft refused", rc == 1 and "Status: DONE" in spec.read_text(), f"{rc} {err}")
        rc, _, _ = run("set-status", spec, "BOGUS")
        check("unknown status refused", rc == 1)
        plan = write(d, "p.md", "# Plan: p\nStatus: DONE · Completed: 2026-11-25 · Ticket: none\n")
        rc, _, _ = run("set-status", plan, "APPROVED")
        check("plan done reopen refused", rc == 1)
        new = write(d, "new.md", "# ADR: new\nStatus: PROPOSED · Ticket: APP-ADR-002\n")
        old = write(d, "old.md", "# ADR: old\nStatus: ACCEPTED · Ticket: APP-ADR-001\n")
        rc, _, _ = run("set-status", old, "SUPERSEDED")
        check("supersede without target refused", rc == 1 and "Status: ACCEPTED" in old.read_text())
        rc, _, _ = run("set-status", old, "SUPERSEDED", "--superseded-by", new)
        txt = old.read_text()
        check("supersede with target", rc == 0 and "Status: SUPERSEDED" in txt and "Superseded by: " in txt, txt)
        rc, _, _ = run("set-status", d + "/missing.md", "DONE")
        check("missing file exits 2", rc == 2)


def test_review_findings():
    with tempfile.TemporaryDirectory() as d:
        crlf = Path(d) / "crlf.md"
        crlf.write_bytes(b"# Spec: s\r\nStatus: DRAFT \xc2\xb7 Revision: 1 \xc2\xb7 Ticket: APP-FEAT-001\r\n\r\n## Why\r\nw\r\n")
        rc, _, _ = run("set-status", crlf, "APPROVED")
        check("F1 CRLF endings kept", rc == 0 and crlf.read_bytes() == b"# Spec: s\r\nStatus: APPROVED \xc2\xb7 Revision: 1 \xc2\xb7 Ticket: APP-FEAT-001\r\n\r\n## Why\r\nw\r\n", crlf.read_bytes())
        sp = write(d, "sp.md", "# Spec: s\nStatus:  DRAFT · Ticket: APP-FEAT-001\n")
        rc, _, _ = run("set-status", sp, "APPROVED")
        check("F2 extra spaces still written", rc == 0 and "APPROVED" in sp.read_text(), sp.read_text())
        bad = Path(d) / "bad.md"
        bad.write_bytes(b"# Spec: s\nStatus: DRAFT \xc2\xb7 Ticket: APP-FEAT-001\n\n## Why\n\xff\n")
        rc, _, err = run("set-status", bad, "APPROVED")
        check("F3 non-UTF-8 body does not crash and is kept", rc == 0 and bad.read_bytes().endswith(b"## Why\n\xff\n") and b"APPROVED" in bad.read_bytes(), f"{rc} {err}")
        adr = write(d, "adr.md", "# ADR: a\nStatus: Accepted · Ticket: x-adr-009\n")
        rc, _, _ = run("set-status", adr, "SUPERSEDED", "--superseded-by", "n.md")
        check("F4 status compared without case", rc == 0 and "SUPERSEDED" in adr.read_text(), adr.read_text())
        root = Path(d) / "proj"
        write(root, ".agents/adr/a.md", "# ADR: a\nStatus: PROPOSED · Ticket: proj-adr-009\n")
        rc, out, _ = run("suggest", "adr", "--root", root)
        check("F4 lowercase ticket still counted", (rc, out) == (0, "PROJ-ADR-010"), f"{rc} {out!r}")
        rc, out, _ = run("find", "PROJ-ADR-009", "--root", root)
        check("F4 find without case", rc == 0 and "adr" in out, out)
        write(root, ".agents/plans/t.md", "# Plan: Fix Ticket: handling\nStatus: DRAFT · Ticket: none\n")
        rc, out, _ = run("find", "handling", "--root", root)
        check("F5 title line is not a header field", out == "", out)


def test_symlink_outside_root():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "proj"
        outside = write(d, "outside/o.md", "# Plan: o\nStatus: DRAFT · Ticket: PROJ-FEAT-009\n")
        (root / ".agents/plans").mkdir(parents=True)
        (root / ".agents/plans/link.md").symlink_to(outside)
        write(root, ".agents/plans/in.md", "# Plan: i\nStatus: DRAFT · Ticket: PROJ-FEAT-005\n")
        rc, out, _ = run("find", "PROJ-FEAT-009", "--root", root)
        check("QA-1 symlink leaving the project is skipped", rc == 0 and out == "", out)
        rc, out, _ = run("find", "PROJ-FEAT-005", "--root", root)
        check("QA-1 a normal file in the project is still found", rc == 0 and "in.md" in out, out)
        rc, out, _ = run("suggest", "feat", "--root", root)
        check("QA-1 suggest ignores the outside file too", (rc, out) == (0, "PROJ-FEAT-006"), out)


def test_find_none():
    with tempfile.TemporaryDirectory() as d:
        write(d, ".agents/plans/p.md", "# Plan: p\nStatus: DONE · Revision: 1 · Ticket: none\n")
        write(d, ".agents/specs/s-spec.md", "# Spec: unrelated\nStatus: APPROVED · Revision: 1 · Ticket: none\n")
        write(d, ".agents/specs/t-spec.md", "# Spec: real\nStatus: APPROVED · Revision: 1 · Ticket: APP-FEAT-001\n")
        for word in ("none", "None", "NONE"):
            rc, out, _ = run("find", word, "--root", d)
            check(f"find {word} lists nothing", rc == 0 and out == "", f"{rc} {out!r}")
        rc, out, _ = run("find", "APP-FEAT-001", "--root", d)
        check("find a real ticket still lists its document", rc == 0 and out.count("\n") == 0 and "t-spec.md" in out, out)


def test_bom():
    with tempfile.TemporaryDirectory() as d:
        spec = Path(d) / "bom-spec.md"
        raw = (b"\xef\xbb\xbf# Spec: s\r\nStatus: DRAFT \xc2\xb7 Revision: 1 \xc2\xb7 Ticket: APP-FEAT-001\r\n\r\n## Why\r\nw\r\n")
        spec.write_bytes(raw)
        (Path(d) / ".agents/specs").mkdir(parents=True)
        (Path(d) / ".agents/specs/bom-spec.md").write_bytes(raw)
        rc, out, _ = run("find", "APP-FEAT-001", "--root", d)
        check("BOM find lists the document", rc == 0 and "bom-spec.md" in out, f"{rc} {out!r}")
        rc, _, err = run("set-status", spec, "APPROVED")
        want = raw.replace(b"Status: DRAFT", b"Status: APPROVED", 1)
        check("BOM set-status succeeds", rc == 0, f"{rc} {err}")
        check("BOM and CRLF kept, only the Status line changed", spec.read_bytes() == want, repr(spec.read_bytes()))
        tricky = Path(d) / "tricky-spec.md"
        raw2 = (b"\xef\xbb\xbf# Spec: Status: DRAFT x\r\nStatus: DRAFT \xc2\xb7 Revision: 1 \xc2\xb7 Ticket: APP-FEAT-002\r\n\r\n## Why\r\nw\r\n")
        tricky.write_bytes(raw2)
        rc, _, err = run("set-status", tricky, "APPROVED")
        want2 = raw2.replace(b"\r\nStatus: DRAFT", b"\r\nStatus: APPROVED", 1)
        check("F1 a BOM title that contains Status: is not rewritten, the header line is", rc == 0 and tricky.read_bytes() == want2, f"{rc} {err} {tricky.read_bytes()!r}")


def main():
    test_suggest()
    test_find()
    test_set_status()
    test_review_findings()
    test_symlink_outside_root()
    test_find_none()
    test_bom()
    if FAILS:
        print("\n".join(FAILS))
        print(f"{len(FAILS)} failure(s)")
        sys.exit(1)
    print("OK all ticket-tools tests passed")


if __name__ == "__main__":
    main()
