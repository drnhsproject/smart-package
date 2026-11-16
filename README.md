# smart-plan

A pair of Agent Skills: one plans, the other carries the plan out.

- **`smart-plan`** plans before anything is coded. It explores the real codebase with
  the smallest token spend, then delivers **one** recommended plan (or one analysis)
  grounded in `file:line` evidence, saved as a Markdown file in your project.
- **`smart-implement`** executes a saved plan task by task, proves each task, and keeps
  the plan file true (ticked tasks, a dated log, the status).

Both are instructed to stay inside their role (`smart-plan` never edits code,
`smart-implement` never goes beyond the plan). This is enforced by the skills' rules,
not by a sandbox, so keep your normal permission prompts on.

## The lifecycle

```
/smart-plan <task>          DRAFT ──(you say "go")──► APPROVED ──► IN PROGRESS ──► DONE
                                     /smart-implement <plan>          (smart-implement)
```

Plans and analyses are saved under `.agents/` in the project (created on first use;
an existing `docs/plans/` or `plans/` folder is used instead if the project has one):

```
.agents/plans/YYYY/MM/DD/YYYY-MM-DD-<TICKET>-<name>.md     the plan (DRAFT → DONE)
.agents/analysis/YYYY/MM/DD/YYYY-MM-DD-<name>.md            an analysis (FINAL, never rewritten)
```

Every plan carries its ticket (`Ticket: ABC-123`, taken from `--ticket=`, your message, or
the git branch name; asked once if none is found) and its tasks are numbered with it
(`ABC-123-T1`, `ABC-123-T2`, ...). `/smart-implement ABC-123` finds the plan by ticket.

The plan file is the only work file: its `## Tasks` checklist is what gets executed,
and its `## Execution log` is where `smart-implement` records what happened. Commit
`.agents/` with the work it describes. An analysis is not executed directly; ask for a
plan that `Follows:` it.

## smart-plan

```
/smart-plan add CSV export to the report page     plan, saved to the plans folder
/smart-plan why is the list slow --analysis       analysis only, no implementation plan
/smart-plan <task> --no-save                      chat only, writes nothing
/smart-plan <task> --scope=src/billing            restrict exploration to a path
```

Flow: Clarify → Explore → Rules → Design → Self-check → Output → Save → Stop.

### How it differs from asking for "a plan"

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

## smart-implement

```
/smart-implement ABC-123                              execute the open plan of that ticket
/smart-implement .agents/plans/2026/11/16/<plan>.md   execute that plan file
/smart-implement                                      the plan just delivered, or the only open one
/smart-implement <plan> --task=T3                     one task (and what it depends on)
```

Flow: Locate → Check → Approve → Execute → Scope trace → Review → Close → Stop.

- **Checks first.** Open questions answered, earlier parts done, not on `main`/`master`,
  the cited `file:line` evidence still true, and a lint / test baseline taken before the
  first edit. `--dry-run` stops here.
- **The plan is the scope.** Anything else it finds is logged as `Found:` or `Deviation:`,
  not coded. A task that cannot be done as written stops the run instead of being improvised.
- **Proof per task.** A task is ticked only after its own `Verify` ran and passed.
- **Scope trace.** At the end every changed hunk must trace to a task or a decision of
  yours, and every ticked box must have a hunk. Unmapped changes stop the run.
- **Independent review** for anything bigger than a small change (more than 2 files, a
  contract change, or a new module): a separate subagent checks bugs, security, and
  performance, read-only. If no subagent can be started it stops and asks; it never
  reviews its own work in silence. `--skip-review` is recorded in the log. Every finding,
  of every severity, is logged first and written to a review report under
  `.agents/reviews/` (evidence, suggested fix, resolution) before any stop.
- **Four fatal stops** (secrets or destructive scope, critical review finding, red gate,
  unmapped scope), and **resumable** from the plan file in a new session.
- **No surprises.** No push, deploy, or destructive command; no commit without your say-so.

## Stays local

Plans, analyses, and review reports under `.agents/` are working notes. On first write the
skills add `.agents/` (and their own installed copies, when untracked) to the repository's
`.git/info/exclude`: local to your clone, so nothing reaches the remote and your
`.gitignore` is untouched. Paths your project already tracks are left alone, and
`smart-implement` never stages `.agents/` or uses `git add -A`.

## Install

Install both skills; `smart-implement` needs the plans that `smart-plan` writes.

With the community `skills` CLI
([vercel-labs/skills](https://github.com/vercel-labs/skills)):

```bash
# see what the repository offers, without installing
npx skills add drnhsproject/smart-plan --list

# install into the current project
npx skills add drnhsproject/smart-plan --skill smart-plan --skill smart-implement

# install for one agent, or for every project of yours
npx skills add drnhsproject/smart-plan --skill smart-plan --skill smart-implement -a claude-code
npx skills add drnhsproject/smart-plan --skill smart-plan --skill smart-implement -g
```

Checked on this repository: `--list` finds both skills, and
`--skill smart-plan --skill smart-implement -a claude-code` copies each `SKILL.md`
to `.claude/skills/<name>/`, identical to this repository. Not checked: the
interactive agent prompt, and agents other than Claude Code.

The CLI collects anonymous usage data; set `DISABLE_TELEMETRY=1` to opt out.
It is a third-party tool. Skills run with your agent's permissions, so read
`SKILL.md` before installing any skill, this one included.

Without the CLI, copy the skill folder yourself:

```bash
# all projects (personal)
cp -R skills/smart-plan skills/smart-implement ~/.claude/skills/

# one project
cp -R skills/smart-plan skills/smart-implement <project>/.claude/skills/
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
