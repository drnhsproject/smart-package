#!/usr/bin/env python3
"""Bookkeeping for a smart-interview session. Standard library only.

The model decides WHAT to ask and reads the user's answers. This script keeps the
state in one JSON file and does the parts that must be exact: which decisions are
ready, the question cap, and the final record.

  interview.py init   FILE [--cap N]
  interview.py add    FILE ID "question" [--needs ID,ID] [--rec "recommended answer"]
  interview.py ready  FILE
  interview.py settle FILE ID --answer TEXT --source user|evidence|assumed [--ref FILE:LINE]
  interview.py term   FILE "term" "one-line meaning"
  interview.py status FILE
  interview.py record FILE

Exit codes: 0 ok, 2 bad input, 3 open decisions but none ready (blocked or cyclic),
4 question cap reached (run `ready` output says what is left).
"""
import argparse
import json
import os
import sys
import tempfile

SOURCES = ("user", "evidence", "assumed")


def die(msg, code=2):
    print(f"ERROR [interview.py]: {msg}", file=sys.stderr)
    print("NEXT: do not repeat the same command unchanged. Fix the cause named above "
          "(or tell the user if it is outside your control), then run it again.", file=sys.stderr)
    sys.exit(code)


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        die(f"no state file at {path}; run init first")
    except json.JSONDecodeError as e:
        die(f"state file is not valid JSON: {e}")


def save(path, state):
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".interview-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def find(state, did):
    for d in state["decisions"]:
        if d["id"] == did:
            return d
    return None


def asked(state):
    return sum(1 for d in state["decisions"] if d["status"] == "settled" and d["source"] == "user")


def ready_set(state):
    settled = {d["id"] for d in state["decisions"] if d["status"] == "settled"}
    known = {d["id"] for d in state["decisions"]}
    out = []
    for d in state["decisions"]:
        if d["status"] != "open":
            continue
        missing = [n for n in d["needs"] if n not in known]
        if missing:
            die(f"{d['id']} needs unknown decision(s): {', '.join(missing)}")
        if all(n in settled for n in d["needs"]):
            out.append(d)
    return out


def cmd_init(a):
    if os.path.exists(a.file):
        die(f"{a.file} already exists; refusing to overwrite")
    save(a.file, {"cap": a.cap, "decisions": [], "terms": []})
    print(f"initialised {a.file} (cap {a.cap})")


def cmd_add(a):
    s = load(a.file)
    if find(s, a.id):
        die(f"decision {a.id} already exists")
    needs = [n for n in (a.needs or "").split(",") if n]
    if a.id in needs:
        die(f"{a.id} cannot depend on itself")
    s["decisions"].append({"id": a.id, "question": a.question, "needs": needs,
                           "rec": a.rec or "", "status": "open", "answer": "",
                           "source": "", "ref": ""})
    save(a.file, s)
    print(f"added {a.id}")


def cmd_ready(a):
    s = load(a.file)
    open_ = [d for d in s["decisions"] if d["status"] == "open"]
    if not open_:
        print("DONE: every decision is settled")
        return
    left = s["cap"] - asked(s)
    if left <= 0:
        print(f"CAP: {asked(s)} of {s['cap']} questions asked. Settle the rest as assumed:")
        for d in open_:
            print(f"{d['id']}\t{d['rec'] or '(no recommendation)'}\t{d['question']}")
        sys.exit(4)
    r = ready_set(s)
    if not r:
        print("BLOCKED: open decisions remain but none is ready (cycle or dependency never settled):",
              file=sys.stderr)
        for d in open_:
            print(f"{d['id']} needs {','.join(d['needs'])}", file=sys.stderr)
        sys.exit(3)
    print(f"READY: {len(r)} decision(s); {left} question(s) left under the cap")
    for d in r:
        print(f"{d['id']}\t{d['rec'] or '(no recommendation)'}\t{d['question']}")


def cmd_settle(a):
    s = load(a.file)
    d = find(s, a.id)
    if not d:
        die(f"unknown decision {a.id}")
    if d["status"] == "settled":
        die(f"{a.id} is already settled; settling twice hides a changed answer")
    if a.source == "evidence" and not a.ref:
        die("source evidence needs --ref FILE:LINE (or the earlier message it came from)")
    d.update(status="settled", answer=a.answer, source=a.source, ref=a.ref or "")
    save(a.file, s)
    print(f"settled {a.id} ({a.source})")


def cmd_term(a):
    s = load(a.file)
    if any(t["term"].lower() == a.term.lower() for t in s["terms"]):
        die(f"term '{a.term}' already recorded")
    s["terms"].append({"term": a.term, "meaning": a.meaning})
    save(a.file, s)
    print(f"recorded term {a.term}")


def cmd_status(a):
    s = load(a.file)
    n = len(s["decisions"])
    st = sum(1 for d in s["decisions"] if d["status"] == "settled")
    print(f"decisions {n}, settled {st}, open {n - st}, asked {asked(s)} of cap {s['cap']}")


def cmd_record(a):
    s = load(a.file)
    ds = s["decisions"]
    tag = lambda d: {"user": "user", "assumed": "assumed",
                     "evidence": f"evidence {d['ref']}"}[d["source"]]
    done = [d for d in ds if d["status"] == "settled"]
    print("Decisions")
    for d in done:
        print(f"- {d['question']} -> {d['answer']}   [{tag(d)}]")
    for d in ds:
        if d["status"] == "open":
            print(f"- {d['question']} -> (still open)   [open]")
    ass = [d for d in done if d["source"] == "assumed"]
    if ass:
        print("Open items (assumed, worth a second look)")
        for d in ass:
            print(f"- {d['question']} -> {d['answer']}")
    if s["terms"]:
        print("Terms agreed")
        for t in s["terms"]:
            print(f"- {t['term']}: {t['meaning']}")
    by = {k: sum(1 for d in done if d["source"] == k) for k in SOURCES}
    print(f"Summary: {len(done)} of {len(ds)} settled "
          f"({by['user']} by the user, {by['evidence']} from evidence, {by['assumed']} assumed)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    x = sub.add_parser("init"); x.add_argument("file"); x.add_argument("--cap", type=int, default=8)
    x.set_defaults(f=cmd_init)
    x = sub.add_parser("add"); x.add_argument("file"); x.add_argument("id"); x.add_argument("question")
    x.add_argument("--needs"); x.add_argument("--rec"); x.set_defaults(f=cmd_add)
    x = sub.add_parser("ready"); x.add_argument("file"); x.set_defaults(f=cmd_ready)
    x = sub.add_parser("settle"); x.add_argument("file"); x.add_argument("id")
    x.add_argument("--answer", required=True); x.add_argument("--source", required=True, choices=SOURCES)
    x.add_argument("--ref"); x.set_defaults(f=cmd_settle)
    x = sub.add_parser("term"); x.add_argument("file"); x.add_argument("term"); x.add_argument("meaning")
    x.set_defaults(f=cmd_term)
    x = sub.add_parser("status"); x.add_argument("file"); x.set_defaults(f=cmd_status)
    x = sub.add_parser("record"); x.add_argument("file"); x.set_defaults(f=cmd_record)

    a = p.parse_args()
    if a.cmd == "init" and a.cap < 1:
        die("--cap must be at least 1")
    a.f(a)


if __name__ == "__main__":
    main()
