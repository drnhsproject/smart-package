#!/usr/bin/env python3
"""Scope trace for smart-implement. Standard library plus the `git` command.

  scope-trace.py snapshot --root DIR --out DIR
      Before the first edit: record the files that are already modified or untracked, and
      keep a copy of each, so later your changes can be told from what was already there.

  scope-trace.py trace PLAN.md --root DIR --snapshot DIR [--allow PATH ...]
      After the last task: walk every hunk of the change, map it to the plan, and print
        scope trace · <n> hunks · <n> mapped · <n> pre-run · <n> format-only · <n> unmapped
      followed by every unmapped hunk and every ticked task that has no hunk.

  scope-trace.py closeout PLAN
      Before setting a plan DONE: check that the Execution log carries every line the run owes
      (approved, pre-run state, rules, baseline, scope trace, final check, self-check, review), that
      every ticked task has its `done` line, that no box is left unticked, and that every
      OWNER-VERIFY pending was answered. Prints MISSING lines, exits 1 when any is missing. Works
      for a plan with no code change too: such a plan still logs `scope trace · 0 hunks ...`.

What it proves: which hunks fall in files a task names, which were already there, which are
whitespace-only. What it cannot judge: whether a hunk in a file no task names is direct support
for a task (an import, a test for it) or a user decision. The model decides that and passes
`--allow PATH` for each such file; allowed files are listed, never silently dropped.

`.agents/`, `.claude/skills/` and the snapshot folder itself (when it lies inside the project) are
bookkeeping and are left out; a snapshot outside the project, such as the OS temp directory, is best. Gitignored files have no
diff and are not seen. Without git the script stops (exit 2): compare by hand.

Exit 0: nothing unmapped and no ticked task without a hunk. Exit 1: otherwise. Exit 2: usage.
"""
import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKIP = (".agents/", ".claude/skills/")
# The id is the whole first token (a ticket may itself end in -T<digits>, e.g. PRTFL-191126-T0856).
TASK = re.compile(r"^\s*- \[(?P<box>[ xX])\]\s+(?P<id>\S+)(?P<rest>.*)$")
PATHISH = re.compile(r"`([^`\s]+)`|(?<![\w`/])([\w@\-\[\]()]+(?:/[\w@.\-\[\]()]+)+|[\w@\-\[\]()]+\.[A-Za-z0-9]{1,6})(?![\w`])")


def die(msg, code=2):
    print(f"ERROR [scope-trace.py]: {msg}", file=sys.stderr)
    print("NEXT: do not repeat the same command unchanged. Fix the cause named above "
          "(or tell the user if it is outside your control), then run it again.", file=sys.stderr)
    sys.exit(code)


def git(root, *args, check=True):
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if check and p.returncode != 0:
        die(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout


def need_git(root):
    p = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        die("not a git repository: compare against the pre-run copies and modification times by hand")


def inside(root, other):
    """Path of `other` relative to root as a prefix, or None when it lies outside the project."""
    try:
        return str(Path(other).resolve().relative_to(Path(root).resolve())) + "/"
    except ValueError:
        return None


def changed_paths(root, exclude=None):
    out = git(root, "status", "--porcelain", "-uall", "--no-renames", "-z")
    paths = []
    for entry in out.split("\0"):
        if len(entry) > 3:
            path = entry[3:]
            if not path.startswith(SKIP) and not (exclude and path.startswith(exclude)):
                paths.append((entry[:2], path))
    return paths


def read(path):
    try:
        raw = Path(path).read_bytes()
    except FileNotFoundError:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw  # binary: kept as bytes so a changed file is still seen


def head_text(root, path):
    p = subprocess.run(["git", "-C", str(root), "show", f"HEAD:{path}"], capture_output=True)
    if p.returncode != 0:
        return ""
    try:
        return p.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return p.stdout


def hunks(base, cur):
    """List of (start_line_in_current, removed_lines, added_lines)."""
    if isinstance(base, bytes) or isinstance(cur, bytes):
        return [(1, ["<binary>"], ["<binary changed>"])] if base != cur else []
    a, b = base.splitlines(), cur.splitlines()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != "equal":
            out.append((j1 + 1, a[i1:i2], b[j1:j2]))
    return out


def squash(lines):
    return "".join("".join(lines).split())


def looks_like_file(token, root):
    """A token is a file or directory when it has a letter-led extension, ends with a slash, or exists
    in the project. A branch name such as `feat/banner-cms-crud` has none of these."""
    if re.search(r"\.[A-Za-z][A-Za-z0-9]{0,5}$", token) or token.endswith("/"):
        return True
    return root is not None and "/" in token and (Path(root) / token).exists()


def task_files(plan, root=None):
    tasks = []
    for ln in Path(plan).read_text(errors="ignore").splitlines():
        m = TASK.match(ln)
        if not m:
            continue
        before = m["rest"].split("Accept:")[0]
        toks = set()
        for a, b in PATHISH.findall(before):
            t = (a or b).strip("`,;:()").rstrip(".")  # keep a leading dot: `.agents/...` is a real path
            if ("/" in t or re.search(r"\.[A-Za-z0-9]{1,6}$", t)) and looks_like_file(t, root):
                toks.add(t)
        tid = m["id"]
        tasks.append({"id": tid, "ticked": m["box"] != " ", "files": toks})
    return tasks


def owners_of(path, tasks):
    """Every task that names this file. The script maps by file, so when several tasks name the
    same file it cannot tell which task a hunk belongs to: all of them are credited."""
    out = []
    for t in tasks:
        for f in t["files"]:
            if path == f or path.endswith("/" + f) or (f.endswith("/") and path.startswith(f)):
                out.append(t["id"])
                break
    return out


def bookkeeping_only(task):
    """A task whose files all lie under the bookkeeping prefixes has no hunk by design."""
    return bool(task["files"]) and all(f.startswith(SKIP) for f in task["files"])


def cmd_snapshot(a):
    root, out = Path(a.root), Path(a.out)
    need_git(root)
    if out.exists() and any(out.iterdir()):
        die(f"{out} is not empty; use a new directory")
    (out / "files").mkdir(parents=True, exist_ok=True)
    state = {"head": git(root, "rev-parse", "HEAD", check=False).strip(), "prerun": {}}
    for status, path in changed_paths(root, inside(root, out)):
        src = root / path
        if src.is_file():
            dst = out / "files" / path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            state["prerun"][path] = {"status": status.strip(),
                                     "sha256": hashlib.sha256(src.read_bytes()).hexdigest()}
        else:
            state["prerun"][path] = {"status": status.strip(), "sha256": None}
    (out / "state.json").write_text(json.dumps(state, indent=2))
    print(f"pre-run state · {', '.join(sorted(state['prerun'])) or 'none'}")
    print(f"snapshot saved in {out}")


def cmd_trace(a):
    root, snap = Path(a.root), Path(a.snapshot)
    need_git(root)
    try:
        state = json.loads((snap / "state.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        die(f"no valid snapshot in {snap}; run `snapshot` before the first edit")
    if not Path(a.plan).is_file():
        die(f"{a.plan} is not a file")
    tasks = task_files(a.plan, root)
    allow = set(a.allow or [])
    total = mapped = prerun = fmt = 0
    unmapped, allowed, touched_by_task = [], [], {}
    for status, path in changed_paths(root, inside(root, snap)):
        cur = read(root / path)
        pre = state["prerun"].get(path)
        if pre is not None:
            base = read(snap / "files" / path) if pre["sha256"] else head_text(root, path)
            prerun += 1 if not pre["sha256"] else len(hunks(head_text(root, path), base)) or 0
        else:
            base = head_text(root, path)
        hs = hunks(base, cur)
        if pre is not None and pre["sha256"] and not hs:
            continue  # pre-run file left exactly as it was found
        owners = owners_of(path, tasks)
        for start, rem, add in hs:
            total += 1
            where = f"{path}:{start}"
            if squash(rem) == squash(add):
                fmt += 1
            elif owners:
                mapped += 1
                for o in owners:
                    touched_by_task.setdefault(o, []).append(where)
            elif path in allow:
                mapped += 1
                allowed.append(where)
            else:
                unmapped.append(where)
    total += prerun
    print(f"scope trace · {total} hunks · {mapped} mapped · {prerun} pre-run · {fmt} format-only · {len(unmapped)} unmapped")
    for w in unmapped:
        print(f"UNMAPPED {w}  (no task names this file; if it is direct support or a user decision, "
              f"pass --allow <path> and log why)")
    for w in allowed:
        print(f"ALLOWED  {w}  (by --allow; the log must say whether it is support or a user decision)")
    ghosts = []
    for t in tasks:
        if not t["ticked"] or t["id"] in touched_by_task:
            continue
        if not t["files"]:
            print(f"NOTE {t['id']} names no file (a git or other non-file task): no hunk expected, "
                  f"its Verify is the proof")
        elif bookkeeping_only(t):
            print(f"NOTE {t['id']} names only bookkeeping paths (.agents/ ...): no hunk expected")
        else:
            ghosts.append(t["id"])
    for tid in ghosts:
        print(f"TICKED-NO-HUNK {tid}  (false check, unless its Verify only writes the log: untick it and do the task)")
    if not tasks:
        print("NOTE: the plan has no task lines; nothing could be mapped", file=sys.stderr)
    sys.exit(1 if unmapped or ghosts else 0)


LOG_LINES = [
    ("approved", r"\bapproved\b"),
    ("pre-run state", r"pre-run state"),
    ("rules", r"\brules\s*·"),
    ("baseline", r"\bbaseline\b"),
    ("scope trace", r"scope trace\s*·\s*\d+\s+hunks"),
    ("final check", r"final check"),
    ("self-check", r"self-check\s*·"),
    ("review (a `Review:` line, `Review skipped` or `Review ran inline`)", r"\bReview( skipped|:| ran inline)"),
]


def cmd_closeout(a):
    plan = Path(a.plan)
    if not plan.is_file():
        die(f"{a.plan} is not a file")
    text = plan.read_text(errors="ignore")
    m = re.search(r"^## Execution log\s*$", text, re.M)
    if not m:
        die("the plan has no `## Execution log` section")
    log = text[m.end():]
    missing = []
    for name, pat in LOG_LINES:
        if not re.search(pat, log):
            missing.append(f"the log has no `{name}` line")
    tasks = task_files(a.plan)
    for t in tasks:
        if t["ticked"] and not re.search(rf"{re.escape(t['id'])}\s+done\b", log):
            missing.append(f"{t['id']} is ticked but has no `{t['id']} done` line")
        if not t["ticked"]:
            missing.append(f"{t['id']} is not ticked")
    for pend in re.findall(r"(\S+)\s+OWNER-VERIFY pending", log):
        answered = re.search(rf"{re.escape(pend)}\s+OWNER-VERIFY (done|failed)", log) or \
            re.search(r"OWNER-VERIFY left pending by the user[^\n]*" + re.escape(pend), log)
        if not answered:
            missing.append(f"{pend} OWNER-VERIFY is still pending (done, failed, or left pending by the user is needed)")
    if not tasks:
        missing.append("the plan has no task lines")
    for line in missing:
        print(f"MISSING {line}")
    if missing:
        print(f"{len(missing)} item(s) missing: do not set Status DONE yet")
        sys.exit(1)
    print("OK closeout: every line the run owes is in the log, every task is ticked, every owner check is answered")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot"); s.add_argument("--root", default="."); s.add_argument("--out", required=True)
    s.set_defaults(f=cmd_snapshot)
    t = sub.add_parser("trace"); t.add_argument("plan"); t.add_argument("--root", default=".")
    t.add_argument("--snapshot", required=True); t.add_argument("--allow", action="append")
    t.set_defaults(f=cmd_trace)
    c = sub.add_parser("closeout"); c.add_argument("plan"); c.set_defaults(f=cmd_closeout)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
