#!/usr/bin/env python3
"""Measure whether an agent picks this skill from its description alone.

For each query in a triggers file, a fresh Claude Code session (`claude -p`) runs
in an empty temporary project that holds only this skill under
`.claude/skills/<name>`. The query counts as triggered when the session calls the
Skill tool with this skill's name. Tools that change files or run commands are
disallowed, so a run cannot touch anything.

Usage:
  python3 evals/run-triggers.py evals/triggers.json [--skill NAME] [--runs N] [--jobs N] [--model M]

Triggers file: [{"query": "...", "trigger": true|false}, ...]
Needs the `claude` CLI, logged in. Each run is a real, billed agent session.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DISALLOWED = ["Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch", "Agent"]
TIMEOUT_S = 180


def find_skill_dir(repo: Path, name: str | None = None) -> Path:
    hits = sorted(repo.glob("skills/*/SKILL.md"))
    if name:
        hits = [h for h in hits if h.parent.name == name]
    if len(hits) != 1:
        sys.exit(f"expected exactly one matching skills/*/SKILL.md under {repo}, found {len(hits)}"
                 + ("" if name else " (several skills here: pass --skill <name>)"))
    return hits[0].parent


def run_once(skill_dir: Path, query: str, model: str | None) -> tuple[bool, str]:
    name = skill_dir.name
    with tempfile.TemporaryDirectory(prefix="trig-") as tmp:
        dest = Path(tmp) / ".claude" / "skills" / name
        shutil.copytree(skill_dir, dest, ignore=shutil.ignore_patterns("__pycache__"))
        cmd = ["claude", "-p", query, "--output-format", "stream-json", "--verbose",
               "--disallowedTools", *DISALLOWED]
        if model:
            cmd += ["--model", model]
        proc = subprocess.Popen(cmd, cwd=tmp, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True)
        first_tool = "-"
        deadline = time.time() + TIMEOUT_S
        try:
            for line in proc.stdout:
                if time.time() > deadline:
                    return False, "timeout"
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") == "result":
                    break
                if ev.get("type") != "assistant":
                    continue
                for block in ev.get("message", {}).get("content", []):
                    if block.get("type") != "tool_use":
                        continue
                    tool = block.get("name", "")
                    if first_tool == "-":
                        first_tool = tool
                    if tool == "Skill":
                        called = str(block.get("input", {}).get("skill", ""))
                        if called.split(":")[-1] == name:
                            return True, "Skill"
                        first_tool = f"Skill({called})"
        finally:
            proc.kill()
            proc.wait()
        return False, first_tool


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("triggers")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--model")
    ap.add_argument("--skill", help="skill folder name, when the repository holds several")
    args = ap.parse_args()

    triggers_path = Path(args.triggers).resolve()
    repo = triggers_path.parent.parent
    skill_dir = find_skill_dir(repo, args.skill)
    cases = json.loads(triggers_path.read_text())

    jobs = [(i, c) for i, c in enumerate(cases) for _ in range(args.runs)]
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        results = list(ex.map(lambda j: (j[0], run_once(skill_dir, j[1]["query"], args.model)), jobs))

    per_case: dict[int, list[tuple[bool, str]]] = {}
    for i, r in results:
        per_case.setdefault(i, []).append(r)

    passed = 0
    print(f"skill: {skill_dir.name}   runs per query: {args.runs}\n")
    for i, case in enumerate(cases):
        rs = per_case[i]
        hits = sum(1 for t, _ in rs if t)
        rate = hits / len(rs)
        ok = rate >= 0.5 if case["trigger"] else rate < 0.5
        passed += ok
        other = ",".join(sorted({d for t, d in rs if not t})) or ""
        print(f"{'PASS' if ok else 'FAIL'}  expect={'yes' if case['trigger'] else 'no ':3}  "
              f"triggered {hits}/{len(rs)}  {case['query'][:70]}"
              + (f"   [other: {other}]" if other and case["trigger"] else ""))
    print(f"\n{passed}/{len(cases)} queries pass")
    sys.exit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()
