# Task 13

## Task
Update the Gemini adapter to implement the new staged pipeline methods with strict Pydantic validation and structured output, plus the project_fixed orchestrator. [ASSET: ./assets/TASK013_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.

## Status
Completed

## Justification

### What was done
1. Added imports for PipelineError, ValidationError, RequirementAnalysis, TechnicalEstimateFull, TechnicalEstimateDiscovery, _assert_hours_consistent, and get_maturity_threshold to gemini.py.
2. Implemented **analyze_requirement** — Stage 1 method that renders s2-estimation/analyze-requirement.j2 with response_mime_type="application/json", validates parsed JSON against RequirementAnalysis via model_validate, and raises PipelineError on validation failure.
3. Implemented **estimate_technical** — Stage 2 method that renders estimate-full.j2 or estimate-discovery.j2 based on analysis['branch'], validates against TechnicalEstimateFull (with _assert_hours_consistent) or TechnicalEstimateDiscovery, and raises PipelineError on failure.
4. Implemented **write_commercial_proposal** — Stage 3 method that renders s3-commercial/write-proposal.j2 using the PREMIUM model, injects technical_estimate milestones/summary verbatim (no numeric recomputation).
5. Implemented **generate_project_fixed_proposal** — full orchestrator that calls analyze_requirement → estimate_technical → write_commercial_proposal sequentially, aborts before Stage 3 if PipelineError is raised, and returns the full accumulated JSON.

### Why approaches were chosen
- Gemini's native `response_mime_type="application/json"` support means structured JSON output is enforced by the API itself rather than by fragile regex parsing, aligning with the spec requirement.
- Pydantic model_validate provides strict type-checking with rich error messages; the spec mandates converting ValidationError to PipelineError, which the implementation does consistently in both Stage 1 and Stage 2.
- The orchestrator generate_project_fixed_proposal follows the spec exactly: calls get_maturity_threshold() and passes it to analyze_requirement, lets PipelineError propagate (aborting before the PREMIUM Stage 3 call), and returns accumulated JSON without persisting.

### Tradeoffs or technical debt
- The write_commercial_proposal method still uses regex JSON extraction from the PREMIUM model (as the existing generate_proposal does) rather than response_mime_type, because the write-proposal template mixes prose and JSON in a single prompt and the PREMIUM model may not always honor the JSON-only output mode cleanly.
- The estimate_technical 'discovery' branch template (estimate-discovery.j2) uses Jinja2 macros that reference analysis_json fields (requirements, complexity, etc.) which RequirementAnalysis.model_dump() serializes — this is a correct match since the validated analysis dict is passed as analysis_json to the template.
- No new tests were added as per the task constraints (no bash validation experiments requested).
- generate_proposal (staff aug) and refine_proposal remain unchanged in behavior.