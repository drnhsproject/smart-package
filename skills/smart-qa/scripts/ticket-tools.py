#!/usr/bin/env python3
"""Ticket helpers shared by smart-plan, smart-spec and smart-adr. Standard library only.

  ticket-tools.py suggest TYPE --root DIR
      Print the next ticket for this project: <APP>-<TYPE>-<NNN>.
      APP is the manifest name (package.json, pyproject.toml, composer.json, go.mod),
      else the folder name, uppercased, letters and digits only. NNN is the highest number
      already used for that APP-TYPE in the `Ticket:` lines of the plans, specs and ADR
      folders, plus one, three digits.
  ticket-tools.py find TICKET --root DIR
      List every plan, spec and ADR that carries that ticket: kind, status, path (tab separated).
      The ticket `none` matches nothing, so the command prints nothing for it.
  ticket-tools.py set-status PATH STATUS [--superseded-by PATH]
      Change only the `Status:` header line of a plan, spec or ADR. Refuses a move the
      lifecycle does not allow. An ADR becomes SUPERSEDED only with --superseded-by.

TYPE is one of FEAT FIX REFACTOR CHORE DOCS PERF TEST ADR (any case).
Lifecycles: plan DRAFT > APPROVED > IN PROGRESS > DONE; spec DRAFT > APPROVED > DONE;
ADR PROPOSED > ACCEPTED > SUPERSEDED. A plan or spec may return to DRAFT unless it is DONE.

This file is copied identically into smart-plan, smart-spec, smart-adr and smart-qa: change all four
copies together.
Exit 0: ok. Exit 1: a status move was refused. Exit 2: bad usage or unreadable file.
"""
import argparse
import json
import re
import sys
from pathlib import Path

TYPES = ["FEAT", "FIX", "REFACTOR", "CHORE", "DOCS", "PERF", "TEST", "ADR"]
DOC_DIRS = [".agents/plans", ".agents/specs", ".agents/adr", "docs/plans", "docs/specs", "docs/adr",
            "plans", "specs", "adr"]
LIFECYCLE = {
    "plan": ["DRAFT", "APPROVED", "IN PROGRESS", "DONE"],
    "spec": ["DRAFT", "APPROVED", "DONE"],
    "adr": ["PROPOSED", "ACCEPTED", "SUPERSEDED"],
}
TITLE = re.compile(r"^#\s+(Plan|Spec|ADR):\s*\S", re.I)


def die(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def field(line, key):
    m = re.search(rf"\b{key}:\s*([^·\n]+?)\s*(?:·|$)", line)
    return m.group(1).strip() if m else None


def read_doc(path):
    """Return (kind, header dict, header line numbers) for a plan, spec or ADR file, else None."""
    try:
        lines = path.read_bytes().decode("utf-8", "surrogateescape").lstrip("\ufeff").splitlines()[:12]
    except OSError:
        return None
    kind = None
    for ln in lines:
        m = TITLE.match(ln)
        if m:
            kind = m.group(1).lower()
            break
    if kind is None:
        return None
    h = {}
    for ln in lines:
        if ln.startswith("#"):
            continue  # the title line is not a header field
        for key in ("Status", "Ticket"):
            v = field(ln, key)
            if v and key not in h:
                h[key] = v
    return kind, h


def docs(root):
    root_real = root.resolve()
    for rel in DOC_DIRS:
        base = root / rel
        if base.is_dir():
            for p in sorted(base.rglob("*.md")):
                if not p.resolve().is_relative_to(root_real):
                    continue  # a symlink that leaves the project is not read
                d = read_doc(p)
                if d:
                    yield p, d[0], d[1]


def app_name(root):
    raw = None
    pj = root / "package.json"
    if pj.is_file():
        try:
            raw = json.loads(pj.read_text()).get("name")
        except (OSError, ValueError):
            pass
    if not raw and (root / "pyproject.toml").is_file():
        m = re.search(r'^name\s*=\s*"([^"]+)"', (root / "pyproject.toml").read_text(errors="ignore"), re.M)
        raw = m.group(1) if m else None
    if not raw and (root / "composer.json").is_file():
        try:
            raw = json.loads((root / "composer.json").read_text()).get("name")
        except (OSError, ValueError):
            pass
    if not raw and (root / "go.mod").is_file():
        m = re.search(r"^module\s+(\S+)", (root / "go.mod").read_text(errors="ignore"), re.M)
        raw = m.group(1) if m else None
    if not raw:
        raw = root.resolve().name
    raw = str(raw).split("/")[-1]
    return re.sub(r"[^A-Za-z0-9]", "", raw).upper() or "APP"


def cmd_suggest(a):
    t = a.type.upper()
    if t not in TYPES:
        die(f"unknown TYPE {a.type!r}; use one of {' '.join(TYPES)}")
    root = Path(a.root)
    app = app_name(root)
    pat = re.compile(rf"^{re.escape(app)}-{t}-(\d+)$", re.I)
    top = 0
    for _, _, h in docs(root):
        m = pat.match(h.get("Ticket", ""))
        if m:
            top = max(top, int(m.group(1)))
    print(f"{app}-{t}-{top + 1:03d}")


def cmd_find(a):
    if a.ticket.strip().lower() == "none":
        return  # `none` means "no ticket": it names no piece of work, so nothing can match it
    for p, kind, h in docs(Path(a.root)):
        if h.get("Ticket", "").upper() == a.ticket.upper():
            print(f"{kind}\t{h.get('Status', '?')}\t{p}")


def cmd_set_status(a):
    path = Path(a.path)
    d = read_doc(path)
    if not d:
        die(f"{path}: not a readable plan, spec or ADR file")
    kind, h = d
    new = a.status.upper()
    order = LIFECYCLE[kind]
    cur = h.get("Status", "").upper()
    if new not in order:
        die(f"{new} is not a {kind} status ({', '.join(order)})", 1)
    if cur not in order:
        die(f"current status {cur!r} is not a {kind} status", 1)
    i, j = order.index(cur), order.index(new)
    back_ok = new == "DRAFT" and kind in ("plan", "spec") and cur != "DONE"
    if new != cur and j != i + 1 and not back_ok:
        die(f"{kind} cannot move {cur} -> {new}", 1)
    if new == "SUPERSEDED" and not a.superseded_by:
        die("SUPERSEDED needs --superseded-by PATH", 1)
    if a.superseded_by and re.search(r"[\r\n]", a.superseded_by):
        die("--superseded-by must be a single line", 2)
    lines = path.read_bytes().decode("utf-8", "surrogateescape").splitlines(keepends=True)
    for n, ln in enumerate(lines[:12]):
        if ln.lstrip("\ufeff").startswith("#"):
            continue  # the title line, which may start with a byte order mark
        changed = re.sub(r"(\bStatus:\s*)" + re.escape(cur), lambda m: m.group(1) + new, ln, count=1, flags=re.I)
        if changed != ln:
            if new == "SUPERSEDED":
                eol = ln[len(ln.rstrip("\r\n")):]
                changed = changed.rstrip("\r\n") + f" · Superseded by: {a.superseded_by}" + eol
            lines[n] = changed
            break
    else:
        die(f"{path}: no Status line in the header", 2)
    path.write_bytes("".join(lines).encode("utf-8", "surrogateescape"))
    print(f"{path}: {cur} -> {new}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("suggest")
    s.add_argument("type")
    s.add_argument("--root", default=".")
    f = sub.add_parser("find")
    f.add_argument("ticket")
    f.add_argument("--root", default=".")
    t = sub.add_parser("set-status")
    t.add_argument("path")
    t.add_argument("status")
    t.add_argument("--superseded-by")
    a = ap.parse_args()
    {"suggest": cmd_suggest, "find": cmd_find, "set-status": cmd_set_status}[a.cmd](a)


if __name__ == "__main__":
    main()
