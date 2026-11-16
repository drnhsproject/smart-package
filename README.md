# smart-plan

A set of Agent Skills for one loop: plan, build, test, repair.

- **`smart-plan`** plans before anything is coded. It explores the real codebase with
  the smallest token spend, then delivers **one** recommended plan (or one analysis)
  grounded in `file:line` evidence, saved as a Markdown file in your project.
- **`smart-implement`** executes a saved plan task by task, proves each task, and keeps
  the plan file true (ticked tasks, a dated log, the status).

- **`smart-qa`** tries to break what was built and writes an evidence-backed report.
- **`smart-fix`** repairs the findings of that report, one at a time, with a regression test each.

Each is instructed to stay inside its role (`smart-plan` never edits code,
`smart-implement` never goes beyond the plan, `smart-qa` never edits product code,
`smart-fix` never judges its own fix). This is enforced by the skills' rules,
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

## smart-qa

```
/smart-qa ABC-123                       test what that plan built
/smart-qa                               the plan just implemented, or the latest DONE one
/smart-qa <plan> --live https://site    also probe the deployed site
/smart-qa --diff                        no plan: test the current uncommitted diff
```

Flow: Locate → Scope → Baseline → Test → Security → Regression → Live (optional) → Report → Stop.

- **Tries to break the change**, per Accept criterion: edge inputs, error paths, repeated or
  concurrent calls, callers of what changed, then a security pass (injection, auth and
  object-level access, uploads, secrets, new dependencies). Each finding carries a
  reproduction or `file:line`; no evidence, no finding.
- **Never edits product code.** Fixes go back through `smart-plan` → `smart-implement`.
- **Logins are not skipped silently.** It uses a local test setup, or a session you pass in the
  `QA_SESSION_COOKIE` environment variable (never pasted in chat). Without either, those checks
  are `not run` and the verdict cannot be a plain `PASS`.
- **`--live <url>`** checks that the fix is actually deployed: read-only requests and anonymous
  probes that cannot write data even if the gate is missing, one origin, about 50 requests.
- **Verdict**: PASS / PASS WITH FOLLOW-UPS / FAIL, saved to `.agents/qa/`. Nothing is committed
  or pushed.

## smart-fix

```
/smart-fix ABC-123                      fix the open CRITICAL and HIGH findings of that QA report
/smart-fix                              the QA report just written
/smart-fix <report> --id=QA-3,QA-5      only those findings
/smart-fix <report> --all               MEDIUM and LOW too
```

Flow: Locate → Confirm → Fix → Prove → Record → Stop.

- **Re-proves each finding first.** If it cannot be reproduced, nothing is edited and the
  finding is recorded `DISPUTED` with evidence. A fix for a non-bug is a new bug.
- **Smallest root-cause change, one finding at a time**, most severe first. A fix that grows
  past 3 files, or needs a schema change or a decision from you, is `DEFERRED` and sent to
  `smart-plan`.
- **A regression test per fix** that fails before and passes after, plus the project's lint,
  typecheck and the tests of everything touched.
- **Never grades its own work.** It records the outcome in the same QA report; only a new
  `/smart-qa` run can turn the verdict. Nothing is committed or pushed.

## Stays local

Plans, analyses, and review reports under `.agents/` are working notes. On first write the
skills add `.agents/` (and their own installed copies, when untracked) to the repository's
`.git/info/exclude`: local to your clone, so nothing reaches the remote and your
`.gitignore` is untouched. Paths your project already tracks are left alone, and
`smart-implement` never stages `.agents/` or uses `git add -A`.

## Install

Install the skills you want. `smart-implement` needs the plans that `smart-plan` writes, and `smart-fix` needs the reports that `smart-qa` writes.

With the community `skills` CLI
([vercel-labs/skills](https://github.com/vercel-labs/skills)):

```bash
# see what the repository offers, without installing
npx skills add drnhsproject/smart-plan --list

# install into the current project
npx skills add drnhsproject/smart-plan --skill smart-plan --skill smart-implement --skill smart-qa --skill smart-fix

# install for one agent, or for every project of yours
npx skills add drnhsproject/smart-plan --skill smart-plan --skill smart-implement --skill smart-qa --skill smart-fix -a claude-code
npx skills add drnhsproject/smart-plan --skill smart-plan --skill smart-implement --skill smart-qa --skill smart-fix -g
```

Checked earlier, when the repository held `smart-plan` and `smart-implement`: `--list` found both, and
`-a claude-code` copied each `SKILL.md` to `.claude/skills/<name>/`, identical to this repository.
Not re-checked since `smart-qa` and `smart-fix` were added, nor the interactive agent prompt, nor
agents other than Claude Code.

The CLI collects anonymous usage data; set `DISABLE_TELEMETRY=1` to opt out.
It is a third-party tool. Skills run with your agent's permissions, so read
`SKILL.md` before installing any skill, this one included.

Without the CLI, copy the skill folder yourself:

```bash
# all projects (personal)
cp -R skills/smart-plan skills/smart-implement skills/smart-qa skills/smart-fix ~/.claude/skills/

# one project
cp -R skills/smart-plan skills/smart-implement skills/smart-qa skills/smart-fix <project>/.claude/skills/
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
