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

With the community `skills` CLI
([vercel-labs/skills](https://github.com/vercel-labs/skills)):

```bash
# see what the repository offers, without installing
npx skills add drnhsproject/smart-plan --list

# install into the current project
npx skills add drnhsproject/smart-plan --skill smart-plan

# install for one agent, or for every project of yours
npx skills add drnhsproject/smart-plan --skill smart-plan -a claude-code
npx skills add drnhsproject/smart-plan --skill smart-plan -g
```

Checked on this repository: `--list` finds the skill, and
`--skill smart-plan -a claude-code` copies `SKILL.md` to
`.claude/skills/smart-plan/`, identical to this repository. Not checked: the
interactive agent prompt, and agents other than Claude Code.

The CLI collects anonymous usage data; set `DISABLE_TELEMETRY=1` to opt out.
It is a third-party tool. Skills run with your agent's permissions, so read
`SKILL.md` before installing any skill, this one included.

Without the CLI, copy the skill folder yourself:

```bash
# all projects (personal)
cp -R skills/smart-plan ~/.claude/skills/

# one project
cp -R skills/smart-plan <project>/.claude/skills/
```

A project skill with the same name overrides the personal one.

### Updating

Updates are manual; installed copies do not change on their own:
`npx skills check`, then `npx skills update`. Changes are listed in `CHANGELOG.md`.

## Optional companions

None required. If the project has `graphify-out/graph.json`, the skill uses it.
If the project has a rule index (`AGENTS.md`, `.agents/rules/`), it reads only the
rules the plan depends on.

## License

MIT
