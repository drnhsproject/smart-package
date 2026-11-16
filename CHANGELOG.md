# Changelog

## Unreleased

- Description narrowed: no longer triggers on generic "analyze this"; quick questions
  are answered in chat. Not yet measured by a trigger eval.
- Step 0 now detects the analysis folder (default `docs/analysis/`).
- Output language rule stated explicitly; README clarifies read-only is rule-based.

## 0.1.0

First portable release, derived from a project-specific `smart-plan`.

- New Step 0 detects rule index, knowledge graph, change log, plans folder, and the
  project's real lint / typecheck / test commands. Everything else is conditional on it.
- Removed project-bound paths, module names, domain vocabulary, Metabase/pelacakan
  steps, Obsidian sync, and the `--auto-implement` flag.
- Kept: read-only hard rule, one recommended plan, self-check, de-duplication,
  revision and status rules, split of large plans.
