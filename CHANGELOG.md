# Changelog

## Unreleased

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
