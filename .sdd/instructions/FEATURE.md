---
protocol: FEATURE
mode_auto: true
run_integration: true
run_ui: false
code_context_lines: 200
---
## Current Objective
Refactor the proposal generation process for project_fixed by splitting technical estimation (engineering, numbers) from commercial writing (tone, persuasion) via a 4-stage pipeline driven by a new maturity_score, while keeping staff_augmentation unchanged and preserving all external interfaces (REST API and Telegram bot).

## Key Artifacts (to focus on)
- **Files**: app/intelligence/adapters/gemini.py, app/intelligence/adapters/openrouter.py, app/intelligence/factory.py, app/intelligence/port.py, app/models/analysis.py, app/models/estimate.py, app/models/project.py, app/database/requirement_analyses_repository.py, app/database/technical_estimates_repository.py, app/bots/telegram/handlers.py, app/intelligence/prompts/base/base-role.j2, app/intelligence/prompts/s1-analysis/evaluate-project.j2, app/intelligence/prompts/s1-analysis/format-description.j2, app/intelligence/prompts/s2-estimation/analyze-requirement.j2, app/intelligence/prompts/s2-estimation/estimate-full.j2, app/intelligence/prompts/s2-estimation/estimate-discovery.j2, app/intelligence/prompts/s3-commercial/write-proposal.j2, app/intelligence/prompts/s3-commercial/write-proposal-staffing.j2, app/intelligence/prompts/s4-refine/refine-proposal.j2, app/intelligence/prompts/s4-refine/refine-proposal-staffing.j2, tests/unit/intelligence/test_adapters.py, tests/unit/intelligence/test_factory.py, tests/unit/intelligence/test_gemini_adapter.py, tests/integration/api/test_proposals.py, docs/CONTRACT_TYPE_FEATURE.md, docs/USAGE_EXAMPLES.md
- **Classes/Interfaces**: IntelligencePort, RequirementAnalysis, Entities, Gap, TechnicalEstimateFull, TechnicalEstimateDiscovery, Milestone, Task, MilestoneProposalSummary, RequirementAnalysesRepository, TechnicalEstimatesRepository, PipelineError
- **Configuration**: MATURITY_THRESHOLD

## Task List

- TASK001 [ ] Rename and relocate the seven Jinja prompt templates into the new subfolder structure under app/intelligence/prompts/ as a clean cut (no backward-compatible aliases). [ASSET: ./assets/TASK001_spec.md]
- TASK002 [ ] Create Pydantic models for Stage 1 analysis output validation in app/models/analysis.py. [ASSET: ./assets/TASK002_spec.md]
- TASK003 [ ] Create Pydantic models for Stage 2 technical estimation output validation in app/models/estimate.py, reusing existing Milestone, Task, and MilestoneProposalSummary from app/models/project.py. [ASSET: ./assets/TASK003_spec.md]
- TASK004 [ ] Create the RequirementAnalysesRepository in app/database/requirement_analyses_repository.py with insert and get_latest_by_project_id methods (no sequential versioning). [ASSET: ./assets/TASK004_spec.md]
- TASK005 [ ] Create the TechnicalEstimatesRepository in app/database/technical_estimates_repository.py with insert and get_latest_by_project_id methods (no sequential versioning). [ASSET: ./assets/TASK005_spec.md]
- TASK006 [ ] Create the Stage 1 prompt template analyze-requirement.j2 in app/intelligence/prompts/s2-estimation/ that extracts entities, gaps, and assigns maturity_score. [ASSET: ./assets/TASK006_spec.md]
- TASK007 [ ] Create the Stage 2A prompt template estimate-full.j2 in app/intelligence/prompts/s2-estimation/ that produces a structured technical estimate for mature requirements. [ASSET: ./assets/TASK007_spec.md]
- TASK008 [ ] Create the Stage 2B prompt template estimate-discovery.j2 in app/intelligence/prompts/s2-estimation/ that produces a discovery-mode technical estimate for ambiguous requirements. [ASSET: ./assets/TASK008_spec.md]
- TASK009 [ ] Refactor write-proposal.j2 into a 100% commercial-writing prompt that does not recompute technical numbers. [ASSET: ./assets/TASK009_spec.md]
- TASK010 [ ] Add the three new abstract methods to IntelligencePort in app/intelligence/port.py for the staged pipeline. [ASSET: ./assets/TASK010_spec.md]
- TASK011 [ ] Update the Gemini adapter to implement the new staged pipeline methods with strict Pydantic validation and structured output, plus the project_fixed orchestrator. [ASSET: ./assets/TASK011_spec.md]
- TASK012 [ ] Update the OpenRouter adapter to implement the new staged pipeline methods with post-hoc Pydantic validation, plus the project_fixed orchestrator. [ASSET: ./assets/TASK012_spec.md]
- TASK013 [ ] Update app/intelligence/factory.py template selection helpers for the new subfolder paths and add a maturity-aware estimation template selector. [ASSET: ./assets/TASK013_spec.md]
- TASK014 [ ] Update app/bots/telegram/handlers.py to route by contract_type and persist the three collections, keeping the telemetry message format unchanged. [ASSET: ./assets/TASK014_spec.md]
- TASK015 [ ] Update project_fixed proposal generation to read MATURITY_THRESHOLD from the environment and pass it to analyze_requirement, persisting it on the analysis record. [ASSET: ./assets/TASK015_spec.md]
- TASK016 [ ] Remove legacy numeric-estimation logic from write-proposal.j2 and consolidate the 270h minimum, technical floors, and milestone construction into estimate-full.j2. [ASSET: ./assets/TASK016_spec.md]
- TASK017 [ ] Document the new staged pipeline in docs/USAGE_EXAMPLES.md, including the MATURITY_THRESHOLD configuration and branch behavior. [ASSET: ./assets/TASK017_spec.md]

## End Task List

## Unit Test List

- UNIT001 [ ] tests/unit/intelligence/test_factory.py — verify select_initial_proposal_template returns the new subfolder-prefixed paths and select_estimation_template(maturity_score, threshold) routes to estimate-full.j2 or estimate-discovery.j2 correctly.
- UNIT002 [ ] tests/unit/intelligence/test_factory.py — verify select_estimation_template returns 's2-estimation/estimate-full.j2' when maturity_score >= threshold and 's2-estimation/estimate-discovery.j2' when maturity_score < threshold.
- UNIT003 [ ] tests/unit/intelligence/test_adapters.py — verify all adapter template references use the new subfolder-prefixed paths and that the legacy names (evaluation.j2, project_formatter.j2, proposal.j2, etc.) are no longer referenced.
- UNIT004 [ ] tests/unit/intelligence/test_adapters.py — verify the analyze_requirement, estimate_technical, and write_commercial_proposal methods exist on both Gemini and OpenRouter adapters with the documented signatures.
- UNIT005 [ ] tests/unit/intelligence/test_adapters.py — verify Gemini adapter passes response_mime_type='application/json' for Etapa 1 and Etapa 2 calls.
- UNIT006 [ ] tests/unit/intelligence/test_adapters.py — verify the project_fixed orchestrator calls analyze_requirement, then estimate_technical, then write_commercial_proposal in order; if Etapa 1 or 2 raises PipelineError, Etapa 3 is not invoked.
- UNIT007 [ ] tests/unit/intelligence/test_adapters.py — verify validation guard rail: an invalid JSON output for Etapa 1 raises PipelineError and prevents Etapa 3 from being called.
- UNIT008 [ ] tests/unit/intelligence/test_adapters.py — verify validation guard rail: an invalid JSON output for Etapa 2 raises PipelineError and prevents Etapa 3 from being called.
- UNIT009 [ ] tests/unit/intelligence/test_adapters.py — verify that write_commercial_proposal does not modify hours, subtotals, or milestones from the technical estimate input.
- UNIT010 [ ] tests/unit/intelligence/test_adapters.py — verify MATURITY_THRESHOLD env var is read with default 8 and forwarded to analyze_requirement.
- UNIT011 [ ] tests/unit/intelligence/test_gemini_adapter.py — verify the Gemini adapter's three new stage methods render the correct Jinja templates and validate against the Pydantic models.
- UNIT012 [ ] tests/unit/models/test_analysis.py — verify RequirementAnalysis validates maturity_score in 1..10, branch in {'full','discovery'}, and rejects malformed payloads.
- UNIT013 [ ] tests/unit/models/test_estimate.py — verify TechnicalEstimateFull and TechnicalEstimateDiscovery validate against example payloads from §6.2 (milestones+summary for 'full'; scope_matrix+phase0_hours+post_discovery_hourly_rate+open_questions for 'discovery').
- UNIT014 [ ] tests/unit/database/test_requirement_analyses_repository.py — verify insert persists the document and get_latest_by_project_id returns the highest created_at, with no version_number logic used.
- UNIT015 [ ] tests/unit/database/test_technical_estimates_repository.py — verify insert persists 'full' and 'discovery' documents correctly and get_latest_by_project_id returns the highest created_at, with no version_number logic used.
- UNIT016 [ ] tests/unit/intelligence/test_adapters.py — regression test: staff_augmentation path (generate_proposal) remains functionally unchanged after the refactor.
- UNIT017 [ ] tests/unit/bots/test_telegram_handlers.py — verify the handler routes contract_type='project_fixed' to generate_project_fixed_proposal and contract_type='staff_augmentation' to the existing generate_proposal path.

## End Unit Test List

## Integration Test List

- INT001 [ ] tests/integration/api/test_proposals.py — update template-path assertions to the new subfolder-prefixed paths used by the adapters (lines ~526-669).
- INT002 [ ] tests/integration/api/test_proposals.py — verify GET /api/projects/{id} and POST /{projectId}/refine endpoints continue to expose the proposal in the same format with proposal embedded; intermediate artifacts (requirement_analyses, technical_estimates) are NOT exposed in API responses.
- INT003 [ ] tests/integration/pipeline/test_project_fixed_pipeline.py — full pipeline integration: given a project_fixed project, run generate_project_fixed_proposal end-to-end and assert a document exists in requirement_analyses, one in technical_estimates, and one in proposal_versions with the merged JSON (analysis + estimate + proposal).
- INT004 [ ] tests/integration/pipeline/test_project_fixed_pipeline.py — maturity branching integration: with maturity_score >= MATURITY_THRESHOLD, verify technical_estimates contains milestones+summary and estimate_type='full'; with maturity_score < MATURITY_THRESHOLD, verify it contains scope_matrix, phase0_hours, post_discovery_hourly_rate, open_questions and estimate_type='discovery'.
- INT005 [ ] tests/integration/pipeline/test_project_fixed_pipeline.py — guard-rail integration: feed an invalid JSON output for Etapa 1 (or 2) and assert PipelineError is raised, no PREMIUM call is made for Etapa 3, and no proposal_versions document is created.
- INT006 [ ] tests/integration/pipeline/test_project_fixed_pipeline.py — idempotency integration: if Etapa 3 fails after Etapas 1-2 succeed, the persisted technical_estimate remains reusable on retry without re-running Etapas 1-2.
- INT007 [ ] tests/integration/pipeline/test_staff_augmentation_regression.py — verify staff_augmentation still uses the direct generate_proposal path with no Etapa 1/2 calls and no requirement_analyses or technical_estimates inserts.
- INT008 [ ] tests/integration/bots/test_telegram_handlers.py — verify the Telegram commands /analizar, /procesar, /refinar keep the current telemetry message structure and that /procesar routes by contract_type correctly.

## End Integration Test List

## UI Test List

(empty)

## End UI Test List

## Reviewer List

- TASK001:
    - ACK001 [ ] All seven templates exist at the new subfolder paths with semantic prefixes (analyze-, estimate-, write-, refine-, evaluate-, format-)
    - ACK002 [ ] No template file remains at the old name or old location
    - ACK003 [ ] Every get_template() call in the listed files (gemini.py, openrouter.py, factory.py, tests, docs) references the new subfolder-prefixed path
    - ACK004 [ ] Running the test suite shows no template-not-found errors caused by the rename
    - ACK005 [ ] docs/CONTRACT_TYPE_FEATURE.md and docs/USAGE_EXAMPLES.md reflect the new paths
- TASK002:
    - ACK006 [ ] app/models/analysis.py exists with Entities, Gap (or equivalent), and RequirementAnalysis classes
    - ACK007 [ ] RequirementAnalysis.maturity_score is constrained to integers 1..10
    - ACK008 [ ] RequirementAnalysis.branch only accepts the literal values 'full' or 'discovery'
    - ACK009 [ ] Instantiating RequirementAnalysis with valid data succeeds and with invalid data raises ValidationError
    - ACK010 [ ] Models are importable via `from app.models.analysis import RequirementAnalysis, Entities`
- TASK003:
    - ACK011 [ ] app/models/estimate.py exists with TechnicalEstimateFull and TechnicalEstimateDiscovery classes
    - ACK012 [ ] TechnicalEstimateFull.estimate_type is the literal 'full' and TechnicalEstimateDiscovery.estimate_type is the literal 'discovery'
    - ACK013 [ ] Both models reuse Milestone, Task, and MilestoneProposalSummary imported from app.models.project
    - ACK014 [ ] Valid example data validates successfully for both models; invalid data raises ValidationError
    - ACK015 [ ] Both models include a model_used (str) field for audit
- TASK004:
    - ACK016 [ ] Repository exposes insert() and get_latest_by_project_id() methods
    - ACK017 [ ] get_latest_by_project_id returns the document with the highest created_at for the given project_id
    - ACK018 [ ] Required indexes (project_id + created_at DESC, link_hash) are declared on the collection
    - ACK019 [ ] No version_number field is used; lookup is strictly by created_at DESC
    - ACK020 [ ] Repository does not introduce any new external API endpoints
- TASK005:
    - ACK021 [ ] Repository exposes insert() and get_latest_by_project_id() methods
    - ACK022 [ ] Documents for 'full' branch persist milestones and summary, while 'discovery' branch persists scope_matrix, phase0_hours, post_discovery_hourly_rate, and open_questions
    - ACK023 [ ] get_latest_by_project_id returns the document with the highest created_at for the given project_id
    - ACK024 [ ] Required indexes (project_id + created_at DESC, link_hash) are declared on the collection
    - ACK025 [ ] No version_number field is used
- TASK006:
    - ACK026 [ ] Template exists at app/intelligence/prompts/s2-estimation/analyze-requirement.j2
    - ACK027 [ ] Template extends base/base-role.j2
    - ACK028 [ ] Template accepts full_description and threshold variables
    - ACK029 [ ] Output instructions explicitly require maturity_score (1-10 int), maturity_reason, entities, gaps, branch
    - ACK030 [ ] Branch rule (>= threshold → 'full', else → 'discovery') is stated in the prompt instructions
- TASK007:
    - ACK031 [ ] Template exists at app/intelligence/prompts/s2-estimation/estimate-full.j2
    - ACK032 [ ] Template accepts analysis_json as input
    - ACK033 [ ] Output schema defines milestones[] with step, name, tasks (description, hours_with_overhead), hours_with_overhead, subtotal
    - ACK034 [ ] Output schema defines summary with total_hours, total_budget, delivery_time_weeks, hourly_rate_applied
    - ACK035 [ ] 270h minimum rule is preserved as a constraint inside the template
    - ACK036 [ ] Template instructions explicitly forbid commercial/persuasive language; this is a Stage 2A gatekeeper
- TASK008:
    - ACK037 [ ] Template exists at app/intelligence/prompts/s2-estimation/estimate-discovery.j2
    - ACK038 [ ] Template accepts analysis_json as input
    - ACK039 [ ] Output schema defines scope_matrix with in_scope and out_of_scope lists
    - ACK040 [ ] Output schema defines phase0_hours, post_discovery_hourly_rate, and open_questions
    - ACK041 [ ] Template instructions explicitly forbid commercial/persuasive language; this is a Stage 2B gatekeeper
- TASK009:
    - ACK042 [ ] Template at app/intelligence/prompts/s3-commercial/write-proposal.j2 contains zero instructions to compute hours, prices, or milestones
    - ACK043 [ ] Template accepts technical_estimate_json as the sole technical source
    - ACK044 [ ] Output schema is proposal_header, technical_pitch, questions_for_client
    - ACK045 [ ] Conditional CTA and \n\n maquetation are preserved
    - ACK046 [ ] References inside the prompt to numeric generation (270h, floors, milestone construction) are removed
- TASK010:
    - ACK047 [ ] IntelligencePort declares the three new abstract methods with the exact signatures above
    - ACK048 [ ] Existing generate_proposal and refine_proposal abstract methods remain unchanged
    - ACK049 [ ] Imports for Any and CircuitBreaker are present
    - ACK050 [ ] The module compiles without abstract-method-not-implemented errors once the adapters are updated
- TASK011:
    - ACK051 [ ] Gemini adapter renders templates via the new subfolder-prefixed paths
    - ACK052 [ ] analyze_requirement calls Gemini with response_mime_type='application/json' and validates the result with RequirementAnalysis.model_validate
    - ACK053 [ ] estimate_technical selects estimate-full.j2 when branch=='full' and estimate-discovery.j2 when branch=='discovery', each with response_mime_type='application/json' and the corresponding Pydantic validation
    - ACK054 [ ] write_commercial_proposal renders s3-commercial/write-proposal.j2 with technical_estimate_json and does not call any numeric-recomputation prompt
    - ACK055 [ ] generate_project_fixed_proposal orchestrates the three stages in order; if Etapa 1 or 2 raises PipelineError, Etapa 3 is never called
    - ACK056 [ ] generate_proposal (staff aug) and refine_proposal remain functionally unchanged
    - ACK057 [ ] MATURITY_THRESHOLD env var is read with default '8'
- TASK012:
    - ACK058 [ ] OpenRouter adapter renders templates via the new subfolder-prefixed paths
    - ACK059 [ ] analyze_requirement validates the LLM response with RequirementAnalysis.model_validate (post-hoc)
    - ACK060 [ ] estimate_technical validates with the matching TechnicalEstimateFull/TechnicalEstimateDiscovery model post-hoc
    - ACK061 [ ] write_commercial_proposal renders s3-commercial/write-proposal.j2 with technical_estimate_json
    - ACK062 [ ] generate_project_fixed_proposal orchestrates the three stages in order; if Etapa 1 or 2 raises PipelineError, Etapa 3 is never called
    - ACK063 [ ] generate_proposal (staff aug) and refine_proposal remain functionally unchanged
    - ACK064 [ ] MATURITY_THRESHOLD env var is read with default '8'
- TASK013:
    - ACK065 [ ] select_initial_proposal_template returns the new subfolder-prefixed paths for all branches
    - ACK066 [ ] select_estimation_template returns 's2-estimation/estimate-full.j2' when maturity_score >= threshold
    - ACK067 [ ] select_estimation_template returns 's2-estimation/estimate-discovery.j2' when maturity_score < threshold
    - ACK068 [ ] Existing call sites of select_initial_proposal_template continue to compile
    - ACK069 [ ] New helper is importable from app.intelligence.factory
- TASK014:
    - ACK070 [ ] Handler branches by contract_type to the new orchestrator vs the existing generate_proposal
    - ACK071 [ ] On project_fixed success, a document is inserted into requirement_analyses, one into technical_estimates, and one into proposal_versions
    - ACK072 [ ] On staff_augmentation, behavior is unchanged
    - ACK073 [ ] Telemetry message strings keep their current structure (no added/removed fields)
    - ACK074 [ ] No new external command or response format is introduced to the Telegram bot
- TASK015:
    - ACK075 [ ] MATURITY_THRESHOLD is read from os.environ with a default of '8'
    - ACK076 [ ] The parsed int threshold is forwarded to analyze_requirement
    - ACK077 [ ] The persisted RequirementAnalyses document contains maturity_threshold_used matching the value used
    - ACK078 [ ] When the env var is unset, the pipeline still runs with threshold 8
    - ACK079 [ ] When the env var is set to a non-integer, the code raises a clear configuration error rather than silently falling back
- TASK016:
    - ACK080 [ ] write-proposal.j2 contains no instructions to derive hours, prices, milestones, subtotals, or technical floors
    - ACK081 [ ] estimate-full.j2 contains the migrated 270h minimum rule, technical floors, and milestone construction logic
    - ACK082 [ ] Both templates are internally consistent (Stage 2A produces numbers, Stage 3 only renders them)
    - ACK083 [ ] The split does not alter the visual output format (\n\n maquetation and CTA preserved)
- TASK017:
    - ACK084 [ ] docs/USAGE_EXAMPLES.md includes the 4-stage pipeline description with template paths
    - ACK085 [ ] MATURITY_THRESHOLD env var and its default are documented
    - ACK086 [ ] Branch rule (>=T → full, <T → discovery) is documented
    - ACK087 [ ] staff_augmentation is described as unchanged
    - ACK088 [ ] External interfaces (REST API, Telegram bot) are described as unchanged

## End Reviewer List