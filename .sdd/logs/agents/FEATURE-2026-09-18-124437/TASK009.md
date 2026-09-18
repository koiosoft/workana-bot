# Task 9

## Task
Create the Stage 2B prompt template estimate-discovery.j2 in app/intelligence/prompts/s2-estimation/ that produces a discovery-mode technical estimate for ambiguous requirements. [ASSET: ./assets/TASK009_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.

## Status
Completed

## Justification
The estimate-discovery.j2 Jinja2 template was created at `app/intelligence/prompts/s2-estimation/`. It consumes `analysis_json` (Stage 1 RequirementAnalysis output where maturity_score < threshold) and produces a purely technical JSON structure containing `scope_matrix` (in_scope/out_of_scope), `phase0_hours`, `post_discovery_hourly_rate`, and `open_questions`. No commercial or persuasive text is generated — the output is structured data for Stage 3 consumption. The template uses helper macros to extract in-scope/out-of-scope requirements by disposition, compute phase0 hours from base estimates with complexity/unknown-risk factors, compute post-discovery hourly rate from base rate and risk markup, and derive open questions from unclear requirements.