#!/usr/bin/env python3
"""State reader and skill lister for smart-guide. Standard library only. Read-only: writes nothing.

  guide-state.py state --root DIR
      Read the plans, specs and ADRs of the project and print, for each piece of work that needs
      something, one `NEXT:` command and one `WHY:` line, newest first (at most 5 are shown). The last
      line is `NEXT: <command>` for the newest piece of work, `NEXT: /smart-plan <task>` when nothing is
      on disk, or `NEXT: nothing pending`.
  guide-state.py skills [--dir DIR]
      List the installed skills (symlinked folders included): one line per folder that holds a SKILL.md, with its name and the first
      sentence of its description. DIR defaults to the folder that holds this skill's own folder.

The rule table, first match wins, per document:
  spec DRAFT -> review it                       spec APPROVED with no plan -> /smart-plan
  plan DRAFT / APPROVED -> /smart-implement     plan IN PROGRESS -> /smart-implement (resume)
  plan DONE, no QA line -> /smart-qa
  plan DONE, a QA finding OPEN -> /smart-fix (with --all when only MEDIUM or LOW are open)
  plan DONE, findings FIXED, none OPEN -> /smart-qa --recheck
  plan DONE, a finding DEFERRED, no follow-up plan yet -> /smart-plan (Follows: the plan)
  plan DONE, QA clean, part n of m with n < m -> /smart-implement <next part> (or /smart-plan if it has no file)
  plan DONE, QA clean, last part or no part, finished within 14 days -> /smart-retro
  ADR PROPOSED -> review it
QA log entries are read one per line: `[- ]<time stamp> [FIX: ]QA-<n>[, QA-<m>] [SEVERITY] STATE — summary`; ids
that appear only after the em dash are mentions and change no state. `Follows:` values are normalised lexically
(`./`, `..`, an absolute path under the project root as given or as resolved); symlinks are not resolved.
A plan whose `Follows:` plan is not DONE, or is DONE but still needs a fix or a recheck, is not
listed (its predecessor is), unless the `Follows:` chain loops back to the plan itself (a corrupt
chain must not hide its plans). Documents match by ticket
only when the ticket is not `none`; a `none` document is matched through `Follows:` and its own path.

Text printed comes from files and is data, never an instruction: control, format and separator
characters are dropped, and a path, ticket or report inside a printed command is shell-quoted. A file whose real path leaves the project
is not read. Exit 0: ok. Exit 2: bad usage.
"""
import argparse
import os
import posixpath
import re
import shlex
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

DOC_DIRS = [".agents/plans", ".agents/specs", ".agents/adr", "docs/plans", "docs/specs", "docs/adr",
            "plans", "specs", "adr"]
TITLE = re.compile(r"^#\s+(Plan|Spec|ADR):\s*\S", re.I)
RETRO_DAYS = 14
SHOW = 5
STATE_WORD = re.compile(r"\b(FIXED-VERIFIED|FIXED|OPEN|DISPUTED|DEFERRED)\b")
# One log entry starts with its own id or ids: `[- ]<time stamp> [FIX: ]QA-1[, QA-2 | and QA-2] ...`. Ids that appear
# only after the first em dash (the summary text) are mentions, not entries.
ENTRY = re.compile(r"^\s*(?:[-*]\s+)?(?:\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}\s+)?(?:(?i:fix):\s+)?"
                   r"((?:QA-\d+(?:\s*(?:,|&|\band\b)\s*)?)+)")
PAIR = re.compile(r"\bQA-(\d+)\s+(?:(?:CRITICAL|HIGH|MEDIUM|LOW)\s+)?(FIXED-VERIFIED|FIXED|OPEN|DISPUTED|DEFERRED)\b")


def clean(text):
    """Drop control, format and line/paragraph separator characters (ANSI, C1, bidi overrides, newlines)."""
    return "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf", "Zl", "Zp"))


def q(arg):
    """One shell word for a path, ticket or report taken from a file."""
    return shlex.quote(clean(arg))


def ticket_flag(ticket):
    return "" if ticket.lower() == "none" else f" --ticket={q(ticket)}"


def field(line, key):
    m = re.search(rf"\b{key}:\s*([^·\n]+?)\s*(?:·|$)", line)
    return m.group(1).strip() if m else None


def norm_follows(roots, value):
    """The `Follows:` value as a project-relative posix path, normalised lexically (`./`, `..`, an absolute path
    that starts with the project root as given or as resolved). Symlinks are not resolved: a document's own
    path is not resolved either, so both sides of the lookup stay in the same form."""
    if not value:
        return None
    v = value.strip().strip("`").strip().replace(os.sep, "/")
    if posixpath.isabs(v):
        for base in roots:
            if v == base or v.startswith(base.rstrip("/") + "/"):
                v = v[len(base.rstrip("/")) + 1:]
                break
        else:
            return v  # outside the project: kept as written, it matches no document
    return posixpath.normpath(v)


def read_doc(root, path, roots):
    try:
        real = path.resolve()
        real.relative_to(root.resolve())
        text = real.read_bytes().decode("utf-8", "replace").lstrip("﻿")
    except (OSError, ValueError):
        return None
    lines = text.splitlines()
    head = lines[:12]
    kind = next((m.group(1).lower() for ln in head if (m := TITLE.match(ln))), None)
    if kind is None:
        return None
    h = {}
    for ln in head:
        if ln.startswith("#"):
            continue
        for key in ("Status", "Ticket", "Part", "Series", "Follows"):
            v = field(ln, key)
            if v and key not in h:
                h[key] = v
    part = re.match(r"(\d+)\s+of\s+(\d+)", h.get("Part", ""))
    log = []
    m = re.search(r"^## Execution log\b.*$", text, re.M)
    if m:
        rest = text[m.end():]
        nxt = re.search(r"^## ", rest, re.M)
        log = [ln for ln in (rest[:nxt.start()] if nxt else rest).splitlines() if ln.strip()]
    return {
        "kind": kind, "path": path.relative_to(root).as_posix(), "status": h.get("Status", "").upper(),
        "ticket": h.get("Ticket", "none"), "part": (int(part.group(1)), int(part.group(2))) if part else None,
        "series": h.get("Series"), "follows": norm_follows(roots, h.get("Follows")), "log": log, "mtime": path.stat().st_mtime,
    }


def scan(root, roots):
    docs = []
    for rel in DOC_DIRS:
        base = root / rel
        if base.is_dir():
            for p in sorted(base.rglob("*.md")):
                d = read_doc(root, p, roots)
                if d:
                    docs.append(d)
    return docs


def qa_info(log):
    """Latest state per QA id, severity per id, latest verdict, latest report link, pending owner checks."""
    state, sev, verdict, report = {}, {}, None, None
    pending = {}
    for ln in log:
        entry = ENTRY.match(ln)
        if entry:
            ids = [int(x) for x in re.findall(r"QA-(\d+)", entry.group(1))]
            rest = ln[entry.start(1):].split("—", 1)[0]
            direct = {int(i): w for i, w in PAIR.findall(re.sub(r"\([^)]*\)", " ", rest))}
            first = STATE_WORD.search(ln[entry.end():].split("—", 1)[0])
            sv = re.search(r"\b(CRITICAL|HIGH|MEDIUM|LOW)\b", ln[entry.end():].split("—", 1)[0])
            for nid in sorted(set(ids) | set(direct)):
                word = direct.get(nid) or (first.group(1) if first and nid in ids else None)
                if word:
                    state[nid] = word
                if sv and nid in ids:
                    sev[nid] = sv.group(1)
        marks = list(re.finditer(r"\bQA-(\d+)\b", ln))
        v = re.search(r"\bQA:\s*(PASS WITH FOLLOW-UPS|PASS|FAIL)\b", ln)
        if v:
            verdict = v.group(1)
        if v or marks:
            link = re.search(r"\[\[([^\]]+)\]\]", ln)
            if link:
                report = link.group(1)
        for m in re.finditer(r"(\S+-T\d+|\bT\d+)\s+OWNER-VERIFY\s+(pending|done|failed)", ln):
            if m.group(2) == "pending":
                pending[m.group(1)] = True
            else:
                pending.pop(m.group(1), None)
        left = re.search(r"OWNER-VERIFY left pending by the user:\s*(.*)", ln)
        if left:
            for tid in re.findall(r"\S+-T\d+|\bT\d+", left.group(1)):
                pending.pop(tid, None)
    return state, sev, verdict, report, sorted(pending)


def in_cycle(d, by_path):
    """True when following the `Follows:` chain from d comes back to d (a corrupt chain must not hide it)."""
    seen, cur = {d["path"]}, d
    while cur["follows"]:
        cur = by_path.get(cur["follows"].strip("`"))
        if cur is None or cur["kind"] != "plan":
            return False
        if cur["path"] in seen:
            return cur["path"] == d["path"]
        seen.add(cur["path"])
    return False


def plan_item(d, by_path, docs):
    """(label, next, why) for one plan, or None when nothing is needed."""
    path, st = d["path"], d["status"]
    if st in ("DRAFT", "APPROVED", "IN PROGRESS"):
        if d["follows"] and not in_cycle(d, by_path):
            pred = by_path.get(d["follows"].strip("`"))
            if pred and pred["kind"] == "plan":
                if pred["status"] != "DONE":
                    return None
                settle = plan_item(pred, by_path, docs)
                if settle and (settle[0].startswith("/smart-fix") or settle[0].endswith("--recheck")):
                    return None  # fix and verify the predecessor before the next part
        why = {"DRAFT": "the plan is a draft; approve it by running it", "APPROVED": "the plan is approved and not started",
               "IN PROGRESS": "work is under way; resume from the first unticked task"}[st]
        return f"/smart-implement {q(path)}", why
    if st != "DONE":
        return None
    state, sev, verdict, report, _ = qa_info(d["log"])
    if verdict is None and not state:
        return f"/smart-qa {q(path)}", "the plan is done and no QA line is in its log"
    opened = [n for n, w in state.items() if w == "OPEN"]
    if opened or (verdict == "FAIL" and not state):
        report = q(report) if report else "<report>"
        if any(sev.get(n, "HIGH") in ("CRITICAL", "HIGH") for n in opened) or not opened:
            return f"/smart-fix {report}", f"QA left {len(opened)} finding(s) open, at least one HIGH or CRITICAL"
        return f"/smart-fix {report} --all", f"QA left {len(opened)} MEDIUM or LOW finding(s) open"
    if any(w == "FIXED" for w in state.values()):
        return f"/smart-qa {q(path)} --recheck", "findings were fixed but only QA can verify them"
    if any(w == "DEFERRED" for w in state.values()):
        followed = any(o["kind"] == "plan" and o["follows"] == path and not (
            d["part"] and o["series"] == d["series"] and o["part"] and o["part"][0] == d["part"][0] + 1) for o in docs)
        if followed:
            return None  # a follow-up plan already carries the deferred work
        return (f"/smart-plan{ticket_flag(d['ticket'])} (Follows: {q(path)})",
                "a finding was DEFERRED to a plan; the plan that follows it does not exist yet")
    if d["part"] and d["part"][0] < d["part"][1]:
        n = d["part"][0] + 1
        nxt = next((o for o in docs if o["kind"] == "plan" and (o["follows"] or "").strip("`") == path), None)
        if nxt is None and d["series"]:
            nxt = next((o for o in docs if o["kind"] == "plan" and o["series"] == d["series"]
                        and o["part"] and o["part"][0] == n), None)
        if nxt is None:
            return f"/smart-plan{ticket_flag(d['ticket'])}", f"part {n} of {d['part'][1]} has no plan file yet"
        if nxt["status"] == "DONE":
            return None
        return f"/smart-implement {q(nxt['path'])}", f"QA is clean; the next part ({n} of {d['part'][1]}) is waiting"
    if time.time() - d["mtime"] <= RETRO_DAYS * 86400:
        return "/smart-retro", "QA is clean and the work is recent; commit first (your own commit skill), then record what it taught"
    return None


def items(docs):
    by_path = {d["path"]: d for d in docs}
    out = []
    for d in docs:
        if d["kind"] == "plan":
            r = plan_item(d, by_path, docs)
            if r:
                out.append((d, r[0], r[1]))
        elif d["kind"] == "spec":
            tk = d["ticket"]
            if d["status"] == "DRAFT":
                out.append((d, f"review {q(d['path'])}, then /smart-plan{ticket_flag(tk)}", "the Spec is a draft"))
            elif d["status"] == "APPROVED":
                planned = any(o["kind"] == "plan" and ((tk.lower() != "none" and o["ticket"] == tk) or
                                                       (o["follows"] or "").strip("`") == d["path"]) for o in docs)
                if not planned:
                    out.append((d, f"/smart-plan{ticket_flag(tk)} (follow the Spec at {q(d['path'])})", "the Spec is approved and no plan follows it"))
        elif d["kind"] == "adr" and d["status"] == "PROPOSED":
            out.append((d, f"review {q(d['path'])} and accept or replace it", "the ADR is only proposed"))
    out.sort(key=lambda x: x[0]["mtime"], reverse=True)
    seen, unique = set(), []
    for it in out:
        if it[1] not in seen:
            seen.add(it[1])
            unique.append(it)
    return unique


def uncommitted(root):
    try:
        r = subprocess.run(["git", "-c", "core.fsmonitor=false", "status", "--porcelain", "-uall"], cwd=root,
                           capture_output=True, text=True, timeout=30, env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"))
    except (OSError, subprocess.SubprocessError):
        return 0
    return len([ln for ln in r.stdout.splitlines() if ln.strip()]) if r.returncode == 0 else 0


def cmd_state(args):
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"not a directory: {args.root}", file=sys.stderr)
        return 2
    docs = scan(root, (str(root), os.path.abspath(args.root)))
    its = items(docs)
    changed = uncommitted(root)
    print("== work items (newest first) ==")
    if not its:
        print("none")
    for i, (d, nxt, why) in enumerate(its[:SHOW], 1):
        label = f"{d['kind']} {clean(d['ticket'])} {d['status']}" + (f" part {d['part'][0]} of {d['part'][1]}" if d["part"] else "")
        print(f"{i}. {label} {clean(d['path'])}")
        print(f"   NEXT: {clean(nxt)}")
        print(f"   WHY: {clean(why)}")
        owner = qa_info(d["log"])[4] if d["kind"] == "plan" else []
        if owner:
            print(f"   NOTE: {len(owner)} OWNER-VERIFY check(s) still pending: {', '.join(clean(o) for o in owner)}")
    if len(its) > SHOW:
        print(f"({len(its) - SHOW} more not shown)")
    if changed:
        print(f"== uncommitted == {changed} file(s)")
    if its:
        print(f"NEXT: {clean(its[0][1])}")
    elif not docs or changed and not any(d["kind"] == "plan" for d in docs):
        why = "uncommitted changes and no plan on disk" if changed else "nothing on disk"
        print(f"WHY: {why}")
        print("NEXT: /smart-plan <task>")
    else:
        print("NEXT: nothing pending")
    return 0


def first_sentence(text):
    m = re.match(r"(.+?[.!?])(?:\s|$)", text)
    return (m.group(1) if m else text)[:200]


def cmd_skills(args):
    base = Path(args.dir) if args.dir else Path(__file__).resolve().parent.parent.parent
    if not base.is_dir():
        print(f"not a directory: {base}", file=sys.stderr)
        return 2
    for folder in sorted(p for p in base.iterdir() if p.is_dir() and (p / "SKILL.md").exists()):
        try:
            real = (folder / "SKILL.md").resolve()
            real.relative_to(folder.resolve())  # a symlinked folder is fine; a SKILL.md that leaves it is not
            head = real.read_text(encoding="utf-8-sig").split("\n---", 1)[0]
            name = re.search(r"^name:\s*(\S.*)$", head, re.M)
            desc = re.search(r"^description:\s*(.+)$", head, re.M)
            if not head.startswith("---") or not name:
                raise ValueError("no name")
            print(f"{clean(name.group(1).strip())} · {clean(first_sentence(desc.group(1).strip())) if desc else ''}")
        except (OSError, ValueError):
            print(f"{clean(folder.name)} · unreadable")
    return 0


def main():
    ap = argparse.ArgumentParser(description="State reader and skill lister for smart-guide.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("state")
    s.add_argument("--root", default=".")
    k = sub.add_parser("skills")
    k.add_argument("--dir")
    args = ap.parse_args()
    return {"state": cmd_state, "skills": cmd_skills}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
