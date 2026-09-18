# Task 16

## Task
Update app/bots/telegram/handlers.py to route by contract_type and persist the three collections, keeping the telemetry message format unchanged. [ASSET: ./assets/TASK016_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.

## Status
Completed

## Justification
Implemented contract_type routing in `process_projects()` in app/bots/telegram/handlers.py:

1. **contract_type routing**: read `contract_type` from the project document (via `full_detail` after enrichment). If `'project_fixed'`, uses the staged pipeline (`generate_project_fixed_proposal`). If `'staff_augmentation'`, keeps the existing `generate_proposal` path unchanged, per spec Decision #3.

2. **Three-collection persistence for project_fixed**: after `generate_project_fixed_proposal` returns the accumulated JSON `{analysis, estimate, proposal}`:
   - **requirement_analyses**: inserts the Stage 1 analysis via `RequirementAnalysesRepository.insert()` with `project_id`, `link_hash`, `analysis`, `maturity_threshold_used`, `model_used`.
   - **technical_estimates**: inserts the Stage 2 estimate via `TechnicalEstimatesRepository.insert()` with `project_id`, `link_hash`, `estimate_type`, `analysis`, `model_used` plus branch-specific fields (milestones+summary for 'full', or scope_matrix/phase0_hours/post_discovery_hourly_rate/open_questions for 'discovery').
   - **proposal_versions**: inserts a flat MilestoneProposal (`proposal_header`, `milestones`, `summary`, `technical_pitch`, `questions_for_client`) via `insert_version()` with `source_of_changes='IA'`. Milestones and summary are carried verbatim from the Stage 2 estimate as required by spec.

3. **Telemetry unchanged**: all `/analizar` (fetch_projects), `/procesar` (process_projects), `/refinar` paths keep their existing message format. No format changes were made to any telemetry output.

4. **Imports added**: `RequirementAnalysesRepository`, `TechnicalEstimatesRepository`, and `datetime` (now with timezone) imported; duplicate `create_intelligence_service` import removed.
