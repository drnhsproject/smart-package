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
/smart-plan <task> --quick                        skip the interview (small, clear tasks)
```

Flow: Clarify → Explore → Rules → Grill → Design → Self-check → Output → Save → Stop.

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
  a `Verify` command the agent can run, an optional `Owner-verify` (a check only you can do: a login,
  a screen, your own data), and dependencies, so an implementer needs no second document.
- **An interview before the plan (Step 3b).** After exploring, it answers what the code already settles
  and asks you the rest one question at a time, each with a recommended option, challenges answers that
  clash with a rule or an earlier answer, and stops after 8 questions (the rest become recorded
  assumptions). Skipped for small plans, with `--quick`, and with `--analysis`.
- **Large work is split into ordered parts.** More than one independent outcome, more than 8 tasks or more
  than 12 files proposes a split. All parts are written up front (`Part: n of m · Series: <name>`), every
  task lives in exactly one part, a shared decision is written once and cited, and `smart-implement`
  re-checks a part's `file:line` references when it starts after the part before it is `DONE`, then
  recommends the next part when one is finished.
- **Your language.** Questions, options, summaries and every "Next step" menu follow the language you write
  in; the plan file itself stays in English.

## smart-implement

```
/smart-implement ABC-123                              execute the open plan of that ticket
/smart-implement .agents/plans/2026/11/16/<plan>.md   execute that plan file
/smart-implement                                      the plan just delivered, or the only open one
/smart-implement <plan> --task=T3                     one task (and what it depends on)
```

Flow: Locate → Check → Approve → Execute → Scope trace → Review → Close → Stop.

- **Checks first.** Open questions answered, earlier parts done, not on a protected branch
  (`main`, `master`, `develop`, `staging`, `production`, `release/*`; it offers a feature branch,
  and asks once if the branch name lacks the plan's ticket), the cited `file:line` evidence still true, and a lint / test baseline taken before the
  first edit. `--dry-run` stops here.
- **The plan is the scope.** Anything else it finds is logged as `Found:` or `Deviation:`,
  not coded. A task that cannot be done as written stops the run instead of being improvised.
- **Proof per task.** A task is ticked only after its own `Verify` ran and passed. An `Owner-verify`
  (a check only you can do) never blocks the tick: it stays `OWNER-VERIFY pending` in the log, is asked
  for together in one message, and is recorded as "reported by the user, not run by the agent", never as
  a check the agent passed.
- **Scope trace.** At the end every changed hunk must trace to a task or a decision of
  yours, and every ticked box must have a hunk. Unmapped changes stop the run.
- **Independent review** for anything bigger than a small change (more than 2 files, a
  contract change, or a new module): a separate subagent checks bugs, security, and
  performance, read-only. If no subagent can be started it stops and asks; it never
  reviews its own work in silence. `--skip-review` is recorded in the log. Every finding,
  of every severity, is logged first and written to a review report under
  `.agents/reviews/` (evidence, suggested fix, resolution) before any stop. Approved fixes are made in
  one batch and one round; a reviewer re-check is only called when a CRITICAL or HIGH finding was fixed.
- **Four fatal stops** (secrets or destructive scope, critical review finding, red gate,
  unmapped scope), and **resumable** from the plan file in a new session.
- **No surprises.** No push, deploy, or destructive command; no commit without your say-so.

## smart-qa

```
/smart-qa ABC-123                       test what that plan built
/smart-qa                               the plan just implemented, or the latest DONE one
/smart-qa <plan> --live https://site    also probe the deployed site
/smart-qa <plan> --recheck              only re-test what smart-fix repaired, plus a quick regression
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
- **`--recheck`** is the light second pass after `smart-fix` for MEDIUM and LOW findings in at most 3 files:
  the finding's own reproduction plus a nearby edge, the project's checks, and the callers of the touched
  files. No new exploration and no reviewer subagent. It can write `FIXED-VERIFIED`; if the nearby edge still
  fails, the finding stays `OPEN`.
- **Verdict**: PASS / PASS WITH FOLLOW-UPS / FAIL, saved to `.agents/qa/`. Nothing is committed
  or pushed.
- **Tracked in the plan.** Every finding gets an ID (`QA-1`, `QA-2`, ...) and one line in the plan's
  Execution log with a `[[wikilink]]` to the report; `smart-fix` appends its result the same way
  (`FIXED` = not yet re-tested; `smart-qa` writes `FIXED-VERIFIED` when the fix holds). The latest line
  for an ID is its state: `grep -n 'QA-3 ' <plan>`.

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

## Status and known limits

Version 0.x, usable, not yet a stable release. Tested on 2026-11-19 on one real
feature (a Next.js and Prisma web project: a new public page and a content section with their own CMS,
split into 3 parts and 19 tasks, each part planned, implemented, reviewed, QA'd and repaired; implement, QA and fix ran on the
earlier installed copies there) and on a small scratch project that exercised this version's plan,
implement, QA, fix and `--recheck` loop end to end. Read these before relying on it:

- **There is no test runner for UI or login flows.** Anything behind a login or on a screen is an
  `Owner-verify` you do; the agent cannot do it and a login-bound change cannot earn a plain `PASS`
  unless you pass a session in `QA_SESSION_COOKIE`.
- **The agent never writes to a real database.** If your only database is the real one, database checks
  stay `not run`; applying a migration needs your explicit yes each time.
- **Review and QA rely on a subagent.** Without one they stop and ask rather than review their own work.
- **Reviews of your own model share its blind spots.** Use `--reviewer-model` to pick a different tier.
- **Rules are instructions, not a sandbox.** Keep your normal permission prompts on.
- **Not tried:** a non-Claude agent, the `-g` install, the interactive installer prompt, and projects with
  a very large codebase (the token-saving exploration was only exercised on small and mid-size ones).

## How the skills connect

Each skill stops when it is done and ends with a numbered next step (for example
`1. QA now · 2. Self-check only`). Reply with the number to run that step, or ignore the menu and
call any skill yourself later: `/smart-qa <plan>` and `/smart-fix <report>` work with or without
the menu. A skill never starts the next one on its own, so you read each result first.

```
/smart-plan → (you approve) → /smart-implement → /smart-qa
                                                     │
                       small findings ──→ /smart-fix → /smart-qa --recheck
                       design changes ──→ /smart-plan → /smart-implement → /smart-qa
```

## Which model for which step

A suggestion, not a requirement, and not measured: it is the author's reasoning about where
a mistake costs the most. Tiers are given first because model names change. Examples are
the Claude 5 family as of this writing.

| Step | Suggested tier | Why |
|---|---|---|
| `/smart-plan` | Strongest (e.g. Opus 5.5) | A wrong plan is carried through every later step. Worth the cost; it runs once per change. |
| `/smart-implement` | Mid (e.g. Sonnet 5.5) | A good plan leaves little to decide. Use the strongest tier if the plan is thin or the change is risky. |
| Review subagent (inside `smart-implement`) | Strongest, ideally not the model that wrote the code | A reviewer from the same model tends to share the author's blind spots. |
| `/smart-qa` | Strongest | Finding bugs and security gaps takes reasoning; a missed one is never reported. |
| `/smart-fix` | Mid | One small finding at a time, each proved by a regression test. Strongest for security findings. |

Two things the skills can and cannot do about models. They run on whatever model your session
uses and cannot switch it: change it with `/model` between steps. The one thing they control
is the reviewer subagent: `/smart-implement <plan> --reviewer-model=opus` and
`/smart-qa <plan> --reviewer-model=opus` (`opus`, `sonnet`, `haiku` or `fable`). Any other
value, such as another vendor's model, is refused with a message rather than ignored. To run
a step on a non-Claude model, run that step from an agent that uses it; the `.agents/` files carry the
state, but this has not been tried. Every skill also answers `--help` with its usage and stops.

Rules of thumb: spend on the steps that **decide** (plan, QA, review), save on the steps that
**follow instructions** (implement, fix). If a mid-tier run drifts from the plan or fails
its checks twice, switch up a tier instead of retrying. Switch models between steps with
`/model` in Claude Code; the files under `.agents/` carry the state, so nothing is lost.

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
npx skills add drnhsproject/smart-package --list

# install into the current project
npx skills add drnhsproject/smart-package --skill smart-plan --skill smart-implement --skill smart-qa --skill smart-fix

# install for one agent, or for every project of yours
npx skills add drnhsproject/smart-package --skill smart-plan --skill smart-implement --skill smart-qa --skill smart-fix -a claude-code
npx skills add drnhsproject/smart-package --skill smart-plan --skill smart-implement --skill smart-qa --skill smart-fix -g
```

Checked on 2026-11-16, with all four skills in the repository: `--list` found `smart-plan`,
`smart-implement`, `smart-qa` and `smart-fix`, and `--skill <name> ... -a claude-code -y` into an empty
git project copied each `SKILL.md` to `.claude/skills/<name>/`, byte-identical to this repository
(`cmp`). Not checked: the interactive agent prompt, `-g`, and agents other than Claude Code.

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
