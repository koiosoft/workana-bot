# Task 15

## Task
Update app/intelligence/factory.py template selection helpers for the new subfolder paths and add a maturity-aware estimation template selector. [ASSET: ./assets/TASK015_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.

## Status
Completed

## Justification
Updated select_initial_proposal_template (already had correct s3-commercial/ subfolder paths matching spec) and added select_estimation_template(maturity_score, threshold) returning s2-estimation/estimate-full.j2 when maturity_score >= threshold, else s2-estimation/estimate-discovery.j2. Added comprehensive test class TestSelectEstimationTemplate with 5 test cases covering all boundary conditions.
