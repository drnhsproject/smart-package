#!/usr/bin/env python3
"""Mechanical self-check for a smart-plan plan file. Standard library only.

  check-plan.py PLAN.md [--root DIR] [--plans-dir DIR]

Checks what a script can prove, so the model does not have to claim it:
  - header: title, Status, Revision, Ticket; Part/Series come as a pair
  - required sections (short plan vs full plan)
  - tasks: id format, ids unique, ids carry the header's ticket, not pre-checked while the plan is a DRAFT,
    each has Accept and Verify, BLOCKED_BY exists and points backwards
  - every `file:line` citation: the file exists under --root and the line is in range
  - paths named under "Reused code" exist
  - the premortem line ("This plan fails if"), full plans only (a short plan has no Risks section)
  - split plans: across all parts of the Series, ids are unique, parts are numbered 1..m
    without gaps, and BLOCKED_BY never points at a later part

It does NOT judge whether the plan is good, and it does not check that a cited symbol exists.
Lines that carry the word UNVERIFIED are skipped for citation checks (the plan already says so).

Exit 0: no problems. Exit 1: at least one FAIL line. Exit 2: bad usage.
"""
import argparse
import re
import sys
from pathlib import Path

STATUSES = {"DRAFT", "APPROVED", "IN PROGRESS", "DONE", "FINAL"}
SHORT = ["Context", "Findings", "Tasks", "Verification", "Execution log"]
FULL = ["Context", "Findings", "Recommended approach", "Key decisions",
        "Affected layers & contract impact", "Tasks", "Reused code", "Rules applied",
        "Risks & trade-offs", "Verification", "Execution log"]
# The id is the whole first token: a ticket such as PRTFL-191126-T0856 itself ends in -T<digits>, so the
# id cannot be split by a pattern alone. It is validated against the header ticket instead.
TASK = re.compile(r"^\s*- \[(?P<box>[ xX])\]\s+(?P<id>\S+)(?P<rest>.*)$")


def dep_pattern(ticket):
    if ticket and ticket.lower() != "none":
        return re.compile(rf"(?:{re.escape(ticket)}-)?T\d+")
    return re.compile(r"T\d+")
CITE = re.compile(r"`([A-Za-z0-9_./@\-\[\]()]+\.[A-Za-z0-9]{1,6}):(\d+)(?:-(\d+))?`")
NOT_FILES = {"com", "io", "dev", "org", "net", "app", "co", "id"}
FAILS = []


def fail(check, msg):
    FAILS.append(f"FAIL {check}: {msg}")


def sections(text):
    out, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*(?:—.*)?$", line)
        if m and not line.startswith("###"):
            cur = m.group(1).strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def header(text):
    h = {}
    for line in text.splitlines()[:12]:
        for key in ("Status", "Revision", "Ticket", "Part", "Series", "Follows"):
            m = re.search(rf"\b{key}:\s*([^·\n]+?)\s*(?:·|$)", line)
            if m and key not in h:
                h[key] = m.group(1).strip()
    return h


def parse_tasks(lines):
    tasks = []
    for ln in lines:
        m = TASK.match(ln)
        if m:
            tasks.append({"box": m["box"], "id": m["id"], "rest": m["rest"], "raw": ln})
    return tasks


def inside(root, rel):
    """True when `rel` (text taken from a plan) stays under `root` after resolving `..` and symlinks."""
    try:
        return (root / rel).resolve().is_relative_to(root.resolve())
    except (OSError, ValueError):
        return False


def check_citations(text, root, only_lines=None):
    cache = {}
    for i, line in enumerate(text.splitlines(), 1):
        if "UNVERIFIED" in line:
            continue
        for m in CITE.finditer(line):
            path, a, b = m.group(1), int(m.group(2)), m.group(3)
            if path.rsplit(".", 1)[-1].lower() in NOT_FILES:
                continue
            if not inside(root, path):
                fail("citation", f"plan line {i}: `{path}` escapes the project root {root}")
                continue
            p = (root / path)
            if not p.is_file():
                fail("citation", f"plan line {i}: `{path}` does not exist under {root}")
                continue
            if path not in cache:
                cache[path] = len(p.read_text(errors="ignore").splitlines())
            hi = int(b) if b else a
            if a < 1 or hi > cache[path] or (b and int(b) < a):
                fail("citation", f"plan line {i}: `{path}:{m.group(2)}{'-' + b if b else ''}` is out of range "
                                 f"(file has {cache[path]} lines)")


def check_reused(secs, root):
    for ln in secs.get("Reused code", []):
        if "UNVERIFIED" in ln:
            continue
        for tok in re.findall(r"`([^`\s]+)`", ln):
            if "/" in tok and "." in tok.rsplit("/", 1)[-1] and not tok.startswith("http") and ":" not in tok:
                if not inside(root, tok):
                    fail("reused-code", f"`{tok}` escapes the project root {root}")
                elif not (root / tok).exists():
                    fail("reused-code", f"`{tok}` does not exist under {root}")


def check_tasks(secs, h):
    split = "Series" in h
    tasks = parse_tasks(secs.get("Tasks", []))
    if not tasks:
        fail("tasks", "no task lines found (`- [ ] <TICKET>-T<n> ...`)")
        return tasks
    ticket = h.get("Ticket", "none")
    none = ticket.lower() == "none"
    seen = {}
    for t in tasks:
        tid = t["id"]
        if tid in seen:
            fail("tasks", f"duplicate task id {tid}")
        seen[tid] = t
        if none and not re.fullmatch(r"T\d+", tid):
            fail("tasks", f"{tid}: header says Ticket: none, so the id should be `T<n>`")
        if not none and not re.fullmatch(rf"{re.escape(ticket)}-T\d+", tid):
            fail("tasks", f"{tid}: id should be `{ticket}-T<n>` (the header ticket, then -T and a number)")
        if t["box"] != " " and h.get("Status") == "DRAFT":  # ticks are normal once smart-implement has run
            fail("tasks", f"{tid}: task is pre-checked in a plan that is still a DRAFT")
        r = t["rest"]
        if "Accept:" not in r:
            fail("tasks", f"{tid}: no `Accept:` criterion")
        if not re.search(r"(?<!Owner-)Verify:\s*\S", r):
            fail("tasks", f"{tid}: no `Verify:` the agent can run (an Owner-verify alone is not enough)")
        if not re.search(r"`[^`]+`|\b[\w./-]+\.\w{1,6}\b", r.split("Accept:")[0]):
            fail("tasks", f"{tid}: names no file before `Accept:`")
    order = [t["id"] for t in tasks]
    for t in tasks:
        m = re.search(r"BLOCKED_BY:\s*(.+)$", t["rest"])
        if not m:
            continue
        for dep in dep_pattern(ticket).findall(m.group(1)):
            if dep not in seen:
                if not split:  # in a split plan the dependency may live in an earlier part
                    fail("tasks", f"{t['id']}: BLOCKED_BY {dep} is not a task in this plan")
            elif order.index(dep) >= order.index(t["id"]):
                fail("tasks", f"{t['id']}: BLOCKED_BY {dep} points forward (or at itself)")
    return tasks


def siblings(plan, series, plans_dir):
    base = Path(plans_dir) if plans_dir else None
    if base is None:
        for anc in plan.resolve().parents:
            if anc.name in ("plans",):
                base = anc
                break
        base = base or plan.parent
    out = []
    base_real = base.resolve()
    for f in sorted(base.rglob("*.md")):
        if not f.resolve().is_relative_to(base_real):
            continue  # a symlink that leads outside the plans folder is not read
        try:
            head = "\n".join(f.read_text(errors="ignore").splitlines()[:12])
        except OSError:
            continue
        if re.search(rf"Series:\s*{re.escape(series)}\s*(?:·|$)", head, re.M):
            out.append(f)
    return out


def check_series(plan, h, tasks, plans_dir):
    part = re.match(r"(\d+)\s+of\s+(\d+)$", h.get("Part", ""))
    if not part:
        fail("series", f"Part should read `n of m`, found `{h.get('Part', '')}`")
        return
    n, m = int(part[1]), int(part[2])
    if not (1 <= n <= m):
        fail("series", f"Part {n} of {m} is not in range")
    files = siblings(plan, h["Series"], plans_dir)
    parts = {}
    for f in files:
        txt = f.read_text(errors="ignore")
        fh = header(txt)
        pm = re.match(r"(\d+)\s+of\s+(\d+)$", fh.get("Part", ""))
        if not pm:
            fail("series", f"{f.name}: in the series but its Part header is missing or malformed")
            continue
        if int(pm[2]) != m:
            fail("series", f"{f.name}: says {pm[0]}, this part says total {m}")
        k = int(pm[1])
        if k in parts:
            fail("series", f"two files claim Part {k}: {parts[k]['file'].name} and {f.name}")
        parts[k] = {"file": f, "tasks": parse_tasks(sections(txt).get("Tasks", []))}
    dep_re = dep_pattern(h.get("Ticket", "none"))
    if len(parts) < m:
        have = ", ".join(str(k) for k in sorted(parts))
        print(f"NOTE series: {len(parts)} of {m} parts found (have {have}); cross-part checks cover those only")
    ids = {}
    for k in sorted(parts):
        for t in parts[k]["tasks"]:
            tid = t["id"]
            if tid in ids:
                fail("series", f"task id {tid} appears in part {ids[tid]} and part {k}")
            ids[tid] = k
    for k in sorted(parts):
        for t in parts[k]["tasks"]:
            tid = t["id"]
            mm = re.search(r"BLOCKED_BY:\s*(.+)$", t["rest"])
            for dep in (dep_re.findall(mm.group(1)) if mm else []):
                if dep not in ids and len(parts) == m:
                    fail("series", f"{tid} (part {k}): BLOCKED_BY {dep} is not a task in any part")
                if dep in ids and ids[dep] > k:
                    fail("series", f"{tid} (part {k}) is blocked by {dep} in a later part {ids[dep]}")
    if n > 1 and "Follows" not in h:
        fail("series", f"part {n} should name the previous part in `Follows:`")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("--root", default=".", help="project root that cited paths are relative to (default: .)")
    ap.add_argument("--plans-dir", help="folder to search for the other parts of a split plan")
    a = ap.parse_args()
    plan = Path(a.plan).resolve()
    if not plan.is_file() or plan.suffix.lower() != ".md":
        print(f"ERROR [check-plan.py]: {plan} is not a Markdown (.md) file", file=sys.stderr)
        print("NEXT: pass the path of the saved plan Markdown file (check it with `ls`), then run again.",
              file=sys.stderr)
        sys.exit(2)
    root = Path(a.root).resolve()
    text = plan.read_text(errors="ignore")
    h = header(text)
    if not re.search(r"^# (Plan|Analysis):\s*\S", text, re.M):
        fail("header", "no `# Plan: <title>` line")
    if "# Analysis:" in text:
        print("NOTE: an analysis has no tasks; only citations are checked")
        check_citations(text, root)
    else:
        if h.get("Status") not in STATUSES:
            fail("header", f"Status `{h.get('Status')}` is not one of {sorted(STATUSES)}")
        if "Revision" not in h:
            fail("header", "no `Revision:`")
        if "Ticket" not in h:
            fail("header", "no `Ticket:` (use `Ticket: none` when there is none)")
        if ("Part" in h) != ("Series" in h):
            fail("header", "`Part:` and `Series:` must come together")
        secs = sections(text)
        need = FULL if "Recommended approach" in secs else SHORT
        for s in need:
            if s not in secs:
                fail("sections", f"missing `## {s}`")
        tasks = check_tasks(secs, h)
        check_citations(text, root)
        check_reused(secs, root)
        if "Recommended approach" in secs and "This plan fails if" not in text:
            fail("risks", 'no premortem line ("This plan fails if ...")')
        if "Series" in h and tasks:
            check_series(plan, h, tasks, a.plans_dir)
    if FAILS:
        print("\n".join(FAILS))
        print(f"{len(FAILS)} problem(s) in {plan.name}")
        sys.exit(1)
    print(f"OK {plan.name}: all mechanical checks passed (this does not judge the plan itself)")


if __name__ == "__main__":
    main()
