# Task 19

## Task
Document the new staged pipeline in docs/USAGE_EXAMPLES.md, including the MATURITY_THRESHOLD configuration and branch behavior. [ASSET: ./assets/TASK019_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.

## Status
Completed

## Justification

**What was done:**
Added a new section "🏗️ Pipeline por Etapas para Proyectos Fijos (project_fixed)" to docs/USAGE_EXAMPLES.md documenting all required aspects of the 4-stage pipeline.

**Details:**
- **4-stage pipeline table**: Documents all 4 stages (analyze_requirement → estimate_technical (full/discovery) → write_commercial_proposal → refine_proposal) with their template paths: s2-estimation/analyze-requirement.j2, s2-estimation/estimate-full.j2, s2-estimation/estimate-discovery.j2, s3-commercial/write-proposal.j2, s4-refine/refine-proposal.j2.
- **MATURITY_THRESHOLD**: Documents the env var with default 8, the branching rule (>=T → full, <T → discovery), and configuration examples.
- **staff_augmentation unchanged**: Explicitly notes that staff augmentation keeps its direct path (write-proposal-staffing.j2) and does not participate in the staged pipeline.
- **External interfaces unchanged**: Confirms REST API, Telegram commands (/lista, /procesar), and database schema remain unchanged from the user's perspective.

**Sources consulted:**
- TASK019_spec.md (specification requirements)
- app/intelligence/config.py (get_maturity_threshold, default 8)
- app/intelligence/factory.py (select_initial_proposal_template, select_estimation_template, estimate_full vs discovery branching)
- app/intelligence/adapters/gemini.py (analyze_requirement, estimate_technical, write_commercial_proposal, generate_project_fixed_proposal, refine_proposal methods)
- app/intelligence/port.py (IntelligencePort interface)
- Template files under app/intelligence/prompts/
