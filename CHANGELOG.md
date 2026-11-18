# Changelog

## Unreleased

- Every skill now ends with a numbered next step, so the chain can be walked by replying with a number
  or driven one skill at a time. `smart-implement`: 1. QA now, 2. self-check only, 3. fix the review
  findings (when open); QA is marked Recommended for login, permission, data, money, upload, contract
  or larger changes. `smart-qa`: after FAIL or follow-ups, fix CRITICAL/HIGH, fix all, fix chosen IDs,
  plan first, or stop; after PASS, stop or commit. `smart-fix`: verify with QA (recommended), fix what is
  left, plan the deferred, or stop. A number reply runs that skill via the Skill tool; one skill per
  reply. Not yet run on a real plan.

- `smart-plan` closing message now offers a numbered choice instead of only "go": 1. execute ("go", "1",
  or `/smart-implement <plan name or path>`, with the real plan name filled in), 2. revise the plan
  (edits the same file, bumps `Revision`, shows the menu again). Not yet run on a real plan.

- Findings are now tracked in the plan. `smart-qa` appends to the plan's Execution log one summary line
  and one line per finding (`QA-<n> <severity> OPEN — ... · [[report]]`), and the report's `Plan:` line is
  a wikilink. `smart-fix` appends `FIX: QA-<n> FIXED|DISPUTED|DEFERRED ...` for each finding it handled;
  `smart-qa` closes it with `FIXED-VERIFIED` on the next run. Append-only; nothing else in the plan is
  touched. Not yet run end to end on a real plan.

- The repository was renamed from `drnhsproject/smart-plan` to `drnhsproject/smart-package`. The four
  skills keep their names (`smart-plan`, `smart-implement`, `smart-qa`, `smart-fix`), so installed
  copies and `/smart-plan` keep working. Install with `npx skills add drnhsproject/smart-package ...`;
  GitHub redirects the old URL. Checked in a scratch project: `npx skills check` reported an update
  and `npx skills update -p` refreshed a copy whose lock file still named `drnhsproject/smart-plan`,
  through the redirect, to the current `main`. The stale copy was simulated (old content, old source,
  a wrong hash in the lock file), not a real old install, and the global scope (`-g`) was not run.

- README gains "How the skills connect" (each skill is called by hand and stops; a diagram of the
  plan → implement → qa → fix loop) and "Which model for which step" (a suggested model tier per
  step). The model table is the author's reasoning, not measured on any run.
- `--help` (or `-h`) on all four skills: prints the usage list and stops, touching nothing. Checked once per skill in an isolated project (`claude -p`, only that skill installed): each printed only the usage block and wrote no file.
- `--reviewer-model=<opus|sonnet|haiku|fable>` on `smart-implement` (Step 6) and `smart-qa`
  (Step 7b): sets the model of the independent reviewer subagent. Any other value stops with a
  message instead of being ignored. The skills still cannot switch the session's own model. Not yet run: neither a valid tier nor a refused value has been exercised in a real review.

- `smart-implement` repo guard now also stops on `develop`, `staging`, `production` and `release/*`
  (before: only `main` and `master`) and offers a feature branch. On other branches, when the
  plan's ticket is not in the branch name, it asks once whether to continue or branch; it does
  not block. If the user chooses to work on the protected branch itself, it continues and logs that choice. Not yet run on a real repository.

## 0.2.1 (2026-11-17)

- `smart-implement` Step 5 gains a short self-check before review: seven recurring defects
  (unescaped outside text in markup, changed logic without a failing-on-old-code test, literal
  colors/sizes, busy state with stale data, unstable props to memoized consumers, lost focus,
  docs that still describe old behaviour). Only items the diff touches apply; a hit outside the
  plan's scope is reported, not coded. Written from the author's own review history; not yet
  measured on a run, so it is not known whether it reduces review findings.

## 0.2.0 (2026-11-16)

Four skills: `smart-plan`, `smart-implement`, `smart-qa`, `smart-fix`. Tried together on one project
only (a Next.js portfolio, by its author): plan, implement with independent review, QA, repair,
and a live check of the deployed site. Not yet tried on a non-Next.js project, with a real login
session in `smart-qa`, or by anyone other than the author. Install check: `npx skills add ... --list`
and a clean-project install both match this repository byte for byte (see README).


- New skill `smart-fix`: fixes the findings of a `smart-qa` report one at a time. Re-proves each
  finding first (a finding it cannot reproduce is `DISPUTED` with evidence, not "fixed"), makes
  the smallest root-cause change, adds a regression test, runs the project's checks, and
  appends a Remediation section to the same report. It never grades its own work (only a new
  `smart-qa` run can) and never commits. Written from scratch. First trial (a Next.js portfolio, review report, 2 LOW findings): one
  finding was already fixed in the working tree and was `DISPUTED` with evidence instead of
  edited, the other was reproduced, fixed and re-checked. Review reports use `Resolution:`
  instead of `Status:`; the skill now says so. Second trial, on a `smart-qa` report (2 LOW findings): one was reproduced, fixed and measured before and after (a chunked upload pulled 30 MB before the cap, 6.3 MB after), the other was `DEFERRED` as a design change and sent back to `smart-plan`. Run by hand from its `SKILL.md`, not yet through an installed skill. Trigger eval (`evals/triggers-smart-fix.json`, 16 queries, 2 runs, only this skill installed): 15/16 pass, 8/8 negatives silent; the miss is the literal `/smart-fix` query (probably how the runner passes a slash command, not measured otherwise).

- New skill `smart-qa`: tests what `smart-implement` built (bugs, security, regressions),
  writes an evidence-backed report under `.agents/qa/` with a PASS / PASS WITH FOLLOW-UPS / FAIL
  verdict, and never edits product code. `--live <url>` probes the deployed site (one origin,
  read-only or non-writing anonymous probes) to prove the fix is live; a session for login-protected
  checks comes from a local test setup or `QA_SESSION_COOKIE`, and a login-protected fix that could
  not be exercised cannot earn a plain PASS. Run once on a real project (a Next.js portfolio, by
  its author); found two issues that review and lint missed. Not yet run on other projects or by
  someone other than its author.

- smart-implement now reads the project's rules when it has any (`AGENTS.md`, `CLAUDE.md`, a
  rules folder) in Step 2, and the Step 6 reviewer gets a fourth pass, "rules", checking the
  change against them. A project with no rules logs `rules · none found`, skips the pass, and
  carries on: never a blocker. Not yet run on a real plan.

- First real run (a Next.js portfolio): plan, branch guard, review with a HIGH finding,
  fatal stop, two fix rounds, and report all worked. Lint missed a broken import alias that
  `tsc --noEmit` caught, so both skills now require `tsc --noEmit` when a `tsconfig.json`
  exists. "Keep local" and the review-report text were shortened.
- "Keep local": before the first write under `.agents/`, both skills add `.agents/` (and the
  untracked installed copies of the skills) to the repository's `.git/info/exclude`, never to
  the project's `.gitignore`; paths the project tracks on purpose are left alone.
  `smart-implement` stages only the plan's files by explicit path and never `.agents/`.
- smart-implement Step 6 now records every review finding (all severities, including
  CRITICAL/HIGH, before the Fatal-Stop) as a log line, and writes a review report with
  evidence, suggested fix and resolution to `.agents/reviews/YYYY/MM/DD/`. Not yet run on
  a real plan.
- New skill `smart-implement`: executes a saved plan task by task (checks first, plan is
  the scope, tick only after Verify passes, scope trace, independent review of non-small
  plans, four fatal stops, resumable) and moves the plan
  `APPROVED → IN PROGRESS → DONE`. The repository is now a pair of skills. Written from
  scratch, informed by the author's own project-level implement skills; not yet run on a
  real plan.
- Plans and analyses are saved under `.agents/plans/` and `.agents/analysis/` by default
  (an existing `docs/plans/` or `plans/` is still used if the project has one).
- Plans use the same dated folders as analyses (`YYYY/MM/DD/YYYY-MM-DD-<TICKET>-<name>.md`);
  every plan and task carries the ticket number (`ABC-123-T1`), taken from `--ticket=`, the
  message, or the branch name, and `/smart-implement ABC-123` finds the plan by it.
- smart-plan hands over to `smart-implement`; analyses are never executed directly.

- Description narrowed: no longer triggers on generic "analyze this"; quick questions
  are answered in chat. Not yet measured by a trigger eval.
- Step 0 now detects the analysis folder (default `docs/analysis/`).
- Tasks must change something (unchanged behaviour goes in Findings); Step 0 says what
  to do when the project has no test or typecheck command. Both found by one manual
  run on a Next.js project.
- Trigger and go-signal words are English only (no Indonesian phrases in SKILL.md).
- Output language rule stated explicitly; README clarifies read-only is rule-based.

## 0.1.0

First portable release, derived from a project-specific `smart-plan`.

- New Step 0 detects rule index, knowledge graph, change log, plans folder, and the
  project's real lint / typecheck / test commands. Everything else is conditional on it.
- Removed project-bound paths, module names, domain vocabulary, Metabase/pelacakan
  steps, Obsidian sync, and the `--auto-implement` flag.
- Kept: read-only hard rule, one recommended plan, self-check, de-duplication,
  revision and status rules, split of large plans.
