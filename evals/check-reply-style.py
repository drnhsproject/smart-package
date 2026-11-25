#!/usr/bin/env python3
"""Check that all published SKILL.md files carry one identical reply-style block."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS = [
    "smart-plan/skills/smart-plan",
    "smart-plan/skills/smart-implement",
    "smart-plan/skills/smart-qa",
    "smart-plan/skills/smart-fix",
    "smart-plan/skills/smart-interview",
    "smart-plan/skills/smart-spec",
    "smart-plan/skills/smart-adr",
    "smart-plan/skills/smart-retro",
    "smart-plan/skills/smart-research",
    "smart-plan/skills/smart-guide",
    "kuy-init/skills/kuy-init",
    "reka-rupa/skills/reka-rupa",
    "sastrakara/skills/sastrakara",
    "satpam-commit/skills/satpam-commit",
]
BLOCK = re.compile(r"<!-- reply-style:start -->(.*?)<!-- reply-style:end -->", re.S)
BACKUP = ROOT / ".agents" / "backup" / "reply-style"


def main() -> int:
    problems, bodies = [], {}
    for rel in SKILLS:
        path = ROOT / rel / "SKILL.md"
        if not path.is_file():
            problems.append(f"{rel}: SKILL.md missing")
            continue
        text = path.read_text(encoding="utf-8")
        fm = re.match(r"---\n(.*?)\n---\n", text, re.S)
        head = fm.group(1) if fm else ""
        if not (re.search(r"^name:", head, re.M) and re.search(r"^description:", head, re.M)):
            problems.append(f"{rel}: frontmatter damaged or not closed")
        old = BACKUP / f"{Path(rel).name}.SKILL.md"
        if fm and old.is_file():
            ofm = re.match(r"---\n(.*?)\n---\n", old.read_text(encoding="utf-8"), re.S)
            if ofm and ofm.group(1) != head:
                problems.append(f"{rel}: frontmatter differs from the backup")
        starts, ends = text.count("<!-- reply-style:start -->"), text.count("<!-- reply-style:end -->")
        found = BLOCK.findall(text)
        if starts != 1 or ends != 1 or len(found) != 1:
            problems.append(f"{rel}: expected 1 start and 1 end marker, found {starts} and {ends}")
        else:
            bodies[rel] = found[0].strip()
    if len(set(bodies.values())) > 1:
        ref = next(iter(bodies.values()))
        for rel, body in bodies.items():
            if body != ref:
                problems.append(f"{rel}: block differs from the others")
    for p in problems:
        print("FAIL", p)
    if problems:
        return 1
    print(f"OK {len(SKILLS)} skills carry one identical reply-style block")
    return 0


if __name__ == "__main__":
    sys.exit(main())
