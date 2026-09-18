# Task 7

## Task
Create the Stage 1 prompt template analyze-requirement.j2 in app/intelligence/prompts/s2-estimation/ that extracts entities, gaps, and assigns maturity_score. [ASSET: ./assets/TASK007_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.
## Status
Completed

## Justification
**Justification (by worker):** Created `app/intelligence/prompts/s2-estimation/analyze-requirement.j2` extending `base/base-role.j2`. Template receives `full_description` and `threshold` (default 8). Extracts entities (technologies[], deliverables[], constraints[]), gaps (list[str]), assigns maturity_score (1-10) with maturity_reason, and computes branch via rule: maturity_score >= threshold → 'full', else 'discovery'. Output is strict JSON. Directory `s2-estimation/` was created under `prompts/`.
