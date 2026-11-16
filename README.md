# smart-plan

An Agent Skill that plans before anything is coded. It explores the real
codebase with the smallest token spend, then delivers **one** recommended plan
(or one analysis) grounded in `file:line` evidence, saved as a Markdown file.
It is instructed never to edit code; this is enforced by the skill's rules, not by
a sandbox, so keep your normal permission prompts on.

## What it does

```
/smart-plan add CSV export to the report page     plan, saved to the plans folder
/smart-plan why is the list slow --analysis       analysis only, no implementation plan
/smart-plan <task> --no-save                      chat only, writes nothing
/smart-plan <task> --scope=src/billing            restrict exploration to a path
```

Flow: Clarify → Explore → Rules → Design → Self-check → Output → Save → Stop.

## How it differs from asking for "a plan"

- **Read-only.** No code, config, or git writes until you say go. A tweak request
  revises the plan; it is not a go signal.
- **One recommendation**, not a menu. One rejected alternative, one line.
- **Grounded.** Every `file:line` and symbol is re-checked before output; anything
  unconfirmed is labelled `UNVERIFIED`.
- **Cheap exploration.** Uses a knowledge graph (graphify) when the project has one,
  greps history instead of reading it, never reads whole large files.
- **Adapts to the project.** Step 0 detects rule indexes, change logs, plans
  folders, and the real lint / typecheck / test commands. Nothing is hard-coded.
- **Executable plan.** Tasks are a checklist with file, acceptance criterion,
  verification command, and dependencies, so an implementer needs no second document.

## Install

Copy the skill folder to your skills directory:

```bash
# all projects (personal)
cp -R skills/smart-plan ~/.claude/skills/

# one project
cp -R skills/smart-plan <project>/.claude/skills/
```

A project skill with the same name overrides the personal one.

## Optional companions

None required. If the project has `graphify-out/graph.json`, the skill uses it.
If the project has a rule index (`AGENTS.md`, `.agents/rules/`), it reads only the
rules the plan depends on.

## License

MIT
