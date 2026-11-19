# Changelog

## Unreleased

- Security audit (Snyk, 2026-11-18/19): `smart-plan` failed E004 (CRITICAL, "prompt injection in skill
  instructions": a read-only planning skill appended to `.git/info/exclude`); `smart-qa` and
  `smart-interview` warned W011 (third-party content: `--live` pages, git history). Fix: no skill edits
  git config any more; "Keep local" became a one-time `NOTICE keep-local` line with the command for the
  user to run (smart-plan, smart-implement, smart-qa, smart-fix, README). `smart-qa` and
  `smart-interview` now state that fetched pages and git history are untrusted data and must be reported,
  not obeyed. Script errors (`interview.py`, `scope-trace.py`, `check-plan.py`) now print
  `ERROR [script]: <cause>` plus a `NEXT:` line telling the model what to do. Not yet re-audited by Snyk.

## 0.4.1 (2026-11-19)

- The owner reports a run of these changes on a second model as OK (2026-11-19); the details were not
  recorded here, so whether the scripts help another model stays unproven by this file (see the second-model
  run below).

- Run on a second model (`adacode-3.0-flash`, 2026-11-19, a git-only plan on the same portfolio project:
  create a `development` branch and merge three feature branches into it). What it showed: the plan
  passed `check-plan.py` (`OK`), had the full structure (decisions labelled `user` and `assumed`, tasks with
  `Accept` and `Verify`, a premortem, a log that honestly recorded that the real commit count was 8, not
  the 5 it predicted), and every claim in its log matched the git state (counts, tips, the remote branch,
  `main` untouched). What it did not show: whether the scripts were used (no state file, snapshot or
  transcript was found, and the run may have used another harness), and its execution log was thinner than
  `smart-implement` asks (no `approved`, `pre-run state`, `rules`, `baseline`, `scope trace`, `final check`
  or `self-check` line; tasks logged as `T1 ...` instead of `<TICKET>-T1 done`). So this is evidence that the
  plan format holds on another model, not proof that the scripts help it.
  Changes made from it: (1) `smart-implement/scripts/scope-trace.py closeout <plan>` checks those log lines,
  the `done` line of every ticked task, unticked boxes and unanswered owner checks before a plan is set
  `DONE`, and `smart-implement` Step 7 runs it; run on the portfolio plans it passes the complete log and
  reports 15 missing items on the thin one. (2) A task that names no file (a git operation) is a `NOTE` in
  the scope trace instead of a false `TICKED-NO-HUNK`, and a branch name such as `feat/some-branch` is no
  longer read as a path unless it exists in the project. (3) `smart-plan` Step 1 asks once when the ticket it
  took from the branch name already has a `DONE` plan or covers another topic: the run above reused the
  login ticket for the branch work, so two plans now share the ids `T1` to `T4`.

## 0.4.0 (2026-11-19)

- First real run of the whole chain on a Next.js portfolio (2026-11-19: `/smart-plan` with `smart-interview`
  → `/smart-implement` → `/smart-qa` on a login-form restyle; 4 tasks, scope trace 13 of 13 hunks mapped,
  QA verdict PASS WITH FOLLOW-UPS with 0 findings). It found four mistakes in the new scripts, all fixed:
  (1) a ticket that itself ends in `-T<digits>` (the project's `PRTFL-191126-T0856`) was read as ticket
  plus task, so every task collapsed into one id: `check-plan.py` and `scope-trace.py` now take the whole
  first token as the id and `check-plan.py` validates it against the header ticket, and the branch regex
  in `smart-plan` Step 1 keeps such a ticket whole; (2) `scope-trace.py` credited every hunk to the first
  task naming a file, so with several tasks on one file the others were reported as ticked without a hunk:
  all tasks naming the file are credited now; (3) a leading dot was stripped from `.agents/...` paths, and a
  task that names only bookkeeping paths is now a `NOTE` instead of a false check; (4) `check-plan.py`
  refused any plan with a ticked task, so it failed on an executed plan: the rule now applies to a `DRAFT`
  only. Each was reproduced first, then re-tested against the earlier cases (`ABC-12`, `none`, split
  series, dirty pre-run file, binary file, snapshot inside the project). Still not proven: a model other
  than the one that wrote the scripts, one project only, and a real sign-in with valid credentials.

- Checked on 2026-11-19: `npx skills@latest add <local path> --skill smart-plan --skill smart-interview
  -a claude-code -y` into an empty git project copies the whole skill folder, including `scripts/`
  (4 files `cmp`-identical to this repository, executable bits kept), and both scripts ran from the
  installed location. Source was a local path, not the GitHub repository.
- New: `smart-implement/scripts/scope-trace.py` (Python 3 and `git`). `snapshot` keeps the pre-run
  state and copies before the first edit; `trace` walks every hunk (against `HEAD`, or against the
  pre-run copy for a file that was already dirty), maps it to the files the plan's tasks name, and
  prints the exact `scope trace · n hunks · n mapped · n pre-run · n format-only · n unmapped` line plus
  every unmapped hunk and every ticked task with no hunk. Judgement stays with the model: a hunk in a
  file no task names is only accepted through an explicit `--allow <path>`, which the log must explain.
  Tested on a repo with a dirty pre-run file, a mapped edit, a whitespace-only edit, a new file under a
  directory token, an unnamed file, a deleted file, a changed binary, a ticked task with no change, and
  a snapshot kept inside the project; the tests found and fixed two mistakes in the script (the
  snapshot folder counted as a change, and a changed binary file not seen). Not yet run inside a live
  `/smart-implement` session.
- New: `smart-plan/scripts/check-plan.py`, the mechanical half of Step 5 as a script (Python 3, standard
  library). It checks the header, required sections, task ids (unique, header ticket, never pre-checked),
  `Accept` and `Verify` on every task, `BLOCKED_BY` that exists and points backwards, every `file:line`
  and Reused-code path against the real files, the premortem line of a full plan, and across the parts of
  a split plan (unique ids, parts numbered without gaps, no dependency on a later part). Tested on a
  correct plan, a plan with 16 seeded defects, and a 3-part series; the tests found and fixed two
  mistakes in the script itself (a premortem demanded of short plans, and a valid dependency on an
  earlier part rejected). It does not judge the plan or check that a cited symbol exists.

- New: `smart-interview`, a standalone skill that interviews you about an idea or decision until no
  hidden guess is left. It answers from evidence first (code, rules, history), asks only the real
  choices in rounds (every decision whose prerequisites are settled is asked together, then the rest is
  recomputed), gives each question a recommended option, challenges answers that clash, records "you
  decide" as `assumed`, caps at 8 questions (`--rounds=<n>`), and returns a decision record. It writes
  nothing unless you agree to add agreed terms to a glossary the project already has.
  The exact parts run in `skills/smart-interview/scripts/interview.py` (Python 3, standard library):
  which decisions are ready, the question cap, and the final record, kept in one JSON state file in the
  temp directory so a trimmed context cannot lose them. Tested on a dependency chain, a cycle, an
  unknown dependency, the cap, and bad input; the skill falls back to doing the same by hand when Python
  is missing. `smart-plan`'s
  Step 3b now uses it when it is installed and otherwise runs the same interview inline, so the plan
  never depends on the other skill being present. Trigger eval (`evals/triggers-smart-interview.json`,
  16 queries, 1 run, only this skill installed): 15/16 pass, 8/8 negatives silent (plan, fix, commit,
  QA and plain questions); the miss is the literal `/smart-interview` query, the same pattern as
  `smart-fix` (probably how the runner passes a slash command, not measured otherwise). Not yet tested
  on a real topic in a live session.

## 0.3.0 (2026-11-19)

- Tested end to end on 2026-11-19, and the results written into the
  README ("Status and known limits"): one real feature in a Next.js and Prisma web project (3 parts, 19
  tasks: the planning followed this version of `smart-plan`, but implement, QA and fix ran on the older
  installed copies, so the changes of this release to those three were exercised only on the scratch
  project) and a scratch project, with this version installed, that ran `/smart-plan` → `/smart-implement` → `/smart-qa` → `/smart-fix` → `/smart-qa --recheck`
  twice. What the scratch run showed: the interview asked 3 questions in Indonesian with short options;
  the `Owner-verify` of a task was logged `pending` and later `done — reported by the user`; the owner
  check and the review decisions were asked in one message; 4 LOW review findings were fixed in one batch
  with no second reviewer call; and the first `--recheck` caught a fix that only covered part of its
  finding (an empty or NaN id still gave a bad path), which the second round closed.
- New: a task has `Verify` (what the agent can run) and an optional `Owner-verify` (a login, a screen, a
  real device, the owner's data). `smart-implement` ticks on `Verify`, logs `OWNER-VERIFY pending`, asks
  for all pending owner checks in one message, records the answer as "reported by the user, not run by the
  agent", and closes the plan only when each is done or knowingly left pending. `smart-qa` lists them
  under "Checks not run" and never counts a user report as a check it ran. `smart-plan` self-checks that
  a login-bound check is written as `Owner-verify`.
- New: `smart-qa --recheck`, the light second pass after `smart-fix` (finding reproduction, one nearby
  edge, the project's checks, callers of the touched files; no new exploration, no subagent; refused for
  CRITICAL or HIGH fixes, more than 3 files, or a contract, schema or dependency change). `smart-fix` now
  proposes it as the verify step when it fits. `smart-qa` also asks for `QA_SESSION_COOKIE` before testing
  starts, and its menu drops the "fix CRITICAL and HIGH" option when none is open.

- Large plans split into ordered parts, with the rules aligned so they cannot contradict each other.
  `smart-plan`: one interview for the whole work before the split; all parts written up front with
  `Part: n of m · Series: <name>` and the same ticket; each task in exactly one part, ids continue
  across parts, `BLOCKED_BY` only backwards; a shared decision or rule lives once in the earliest part
  and later parts cite it; a new cross-part self-check; de-duplication no longer treats sibling parts
  as duplicates, and the "never a second plan for a topic" rule has the split as its exception.
  `smart-implement`: parts of one series are one work item (lowest open part first), a part started
  after its predecessor re-checks its cited `file:line` and the predecessor's Found/Deviation lines,
  and the closing menu offers "Next part". `smart-qa` offers "Next part" after PASS. Run on a real
  3-part split on 2026-11-19 (first entry).

- Feedback round on the four skills. (1) New "Talking to the user" block in each skill: when the
  user writes Indonesian, every question, option, summary and the "Next step" menu is Indonesian;
  option labels are at most 6 words with one short line; summaries keep only the result, the top
  risk and the next step, in complete short sentences. (2) Fewer wait cycles: `smart-implement`
  allows 1 review fix round (was 2), fixes all findings in one batch and re-checks only touched
  hunks; `smart-qa` re-checks all CRITICAL/HIGH in one subagent call and skips findings it already
  proved; `smart-fix` trusts fresh report evidence and runs lint/typecheck/full suite once after
  the last finding. (3) `smart-plan` gains Step 3b, a grill-me style interview: after exploring, it
  answers what the code settles, then asks the rest one question at a time with a recommended
  option, challenges conflicting answers, caps at 8 questions, and records each answer in Key
  decisions. Skipped for Small plans, `--quick`, and `--analysis`. Run on a real plan on 2026-11-19 (first entry).

- Every skill now ends with a numbered next step, so the chain can be walked by replying with a number
  or driven one skill at a time. `smart-implement`: 1. QA now, 2. self-check only, 3. fix the review
  findings (when open); QA is marked Recommended for login, permission, data, money, upload, contract
  or larger changes. `smart-qa`: after FAIL or follow-ups, fix CRITICAL/HIGH, fix all, fix chosen IDs,
  plan first, or stop; after PASS, stop or commit. `smart-fix`: verify with QA (recommended), fix what is
  left, plan the deferred, or stop. A number reply runs that skill via the Skill tool; one skill per
  reply. Run on a real plan on 2026-11-19 (first entry).

- `smart-plan` closing message now offers a numbered choice instead of only "go": 1. execute ("go", "1",
  or `/smart-implement <plan name or path>`, with the real plan name filled in), 2. revise the plan
  (edits the same file, bumps `Revision`, shows the menu again). Run on a real plan on 2026-11-19 (first entry).

- Findings are now tracked in the plan. `smart-qa` appends to the plan's Execution log one summary line
  and one line per finding (`QA-<n> <severity> OPEN — ... · [[report]]`), and the report's `Plan:` line is
  a wikilink. `smart-fix` appends `FIX: QA-<n> FIXED|DISPUTED|DEFERRED ...` for each finding it handled;
  `smart-qa` closes it with `FIXED-VERIFIED` on the next run. Append-only; nothing else in the plan is
  touched. Run end to end on 2026-11-19 (first entry).

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
  carries on: never a blocker. Run on a real plan on 2026-11-19 (first entry).

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
