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
- **Files**: app/intelligence/adapters/gemini.py, app/intelligence/adapters/openrouter.py, app/intelligence/factory.py, app/intelligence/port.py, app/exceptions.py, app/models/analysis.py, app/models/estimate.py, app/models/project.py, app/database/requirement_analyses_repository.py, app/database/technical_estimates_repository.py, app/bots/telegram/handlers.py, app/intelligence/prompts/base/base-role.j2, app/intelligence/prompts/s1-analysis/evaluate-project.j2, app/intelligence/prompts/s1-analysis/format-description.j2, app/intelligence/prompts/s2-estimation/analyze-requirement.j2, app/intelligence/prompts/s2-estimation/estimate-full.j2, app/intelligence/prompts/s2-estimation/estimate-discovery.j2, app/intelligence/prompts/s3-commercial/write-proposal.j2, app/intelligence/prompts/s3-commercial/write-proposal-staffing.j2, app/intelligence/prompts/s4-refine/refine-proposal.j2, app/intelligence/prompts/s4-refine/refine-proposal-staffing.j2, tests/unit/intelligence/test_adapters.py, tests/unit/intelligence/test_factory.py, tests/unit/intelligence/test_gemini_adapter.py, tests/integration/api/test_proposals.py, docs/CONTRACT_TYPE_FEATURE.md, docs/USAGE_EXAMPLES.md
- **Classes/Interfaces**: IntelligencePort, RequirementAnalysis, Entities, TechnicalEstimateFull, TechnicalEstimateDiscovery, Milestone, Task, MilestoneProposalSummary, RequirementAnalysesRepository, TechnicalEstimatesRepository, PipelineError
- **Configuration**: MATURITY_THRESHOLD

## Task List

- TASK001 [ ] Move the seven Jinja prompt templates into the new subfolder structure under app/intelligence/prompts/ as a clean cut (no backward-compatible aliases). [ASSET: ./assets/TASK001_spec.md]
- TASK002 [ ] Update every Jinja template reference (get_template calls and template_name literals) across the codebase to the new subfolder-prefixed paths. [ASSET: ./assets/TASK002_spec.md]
- TASK003 [ ] Create Pydantic models for Stage 1 analysis output validation in app/models/analysis.py. [ASSET: ./assets/TASK003_spec.md]
- TASK004 [ ] Create Pydantic models for Stage 2 technical estimation output validation in app/models/estimate.py, reusing existing Milestone, Task, and MilestoneProposalSummary from app/models/project.py. [ASSET: ./assets/TASK004_spec.md]
- TASK005 [ ] Create the RequirementAnalysesRepository in app/database/requirement_analyses_repository.py with insert and get_latest_by_project_id methods (no sequential versioning). [ASSET: ./assets/TASK005_spec.md]
- TASK006 [ ] Create the TechnicalEstimatesRepository in app/database/technical_estimates_repository.py with insert and get_latest_by_project_id methods (no sequential versioning). [ASSET: ./assets/TASK006_spec.md]
- TASK007 [ ] Create the Stage 1 prompt template analyze-requirement.j2 in app/intelligence/prompts/s2-estimation/ that extracts entities, gaps, and assigns maturity_score. [ASSET: ./assets/TASK007_spec.md]
- TASK008 [ ] Create the Stage 2A prompt template estimate-full.j2 in app/intelligence/prompts/s2-estimation/ that produces a structured technical estimate for mature requirements. [ASSET: ./assets/TASK008_spec.md]
- TASK009 [ ] Create the Stage 2B prompt template estimate-discovery.j2 in app/intelligence/prompts/s2-estimation/ that produces a discovery-mode technical estimate for ambiguous requirements. [ASSET: ./assets/TASK009_spec.md]
- TASK010 [ ] Refactor write-proposal.j2 into a 100% commercial-writing prompt that emits the full flat MilestoneProposal contract (proposal_header, milestones, summary, technical_pitch, questions_for_client), carrying milestones and summary verbatim from the technical estimate. [ASSET: ./assets/TASK010_spec.md]
- TASK011 [ ] Add the three new abstract methods to IntelligencePort in app/intelligence/port.py for the staged pipeline. [ASSET: ./assets/TASK011_spec.md]
- TASK012 [ ] Add app/intelligence/config.py with a get_maturity_threshold() helper that reads MATURITY_THRESHOLD from the environment (default 8) with strict parsing, as the single source for the staged pipeline threshold. [ASSET: ./assets/TASK012_spec.md]
- TASK013 [ ] Update the Gemini adapter to implement the new staged pipeline methods with strict Pydantic validation and structured output, plus the project_fixed orchestrator. [ASSET: ./assets/TASK013_spec.md]
- TASK014 [ ] Update the OpenRouter adapter to implement the new staged pipeline methods with post-hoc Pydantic validation, plus the project_fixed orchestrator. [ASSET: ./assets/TASK014_spec.md]
- TASK015 [ ] Update app/intelligence/factory.py template selection helpers for the new subfolder paths and add a maturity-aware estimation template selector. [ASSET: ./assets/TASK015_spec.md]
- TASK016 [ ] Update app/bots/telegram/handlers.py to route by contract_type and persist the three collections, keeping the telemetry message format unchanged. [ASSET: ./assets/TASK016_spec.md]
- TASK017 [ ] Consolidate the maturity-threshold wiring: verify the get_maturity_threshold helper is the single source and the value is persisted on the analysis record. [ASSET: ./assets/TASK017_spec.md]
- TASK018 [ ] Consolidate the numeric/commercial split: verify estimate-full.j2 owns all numeric generation and write-proposal.j2 contains zero numeric instructions, fixing any gap. [ASSET: ./assets/TASK018_spec.md]
- TASK019 [ ] Document the new staged pipeline in docs/USAGE_EXAMPLES.md, including the MATURITY_THRESHOLD configuration and branch behavior. [ASSET: ./assets/TASK019_spec.md]
- TASK020 [ ] Define PipelineError in app/exceptions.py for the staged pipeline guard rail, used by the Stage 1 and Stage 2 validation gatekeepers. [ASSET: ./assets/TASK020_spec.md]

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
- UNIT018 [ ] tests/unit/intelligence/test_adapters.py — contract test: the output of write_commercial_proposal validates against MilestoneProposal from app/models/project.py and contains exactly the fields proposal_header, milestones, summary, technical_pitch, questions_for_client.
- UNIT019 [ ] tests/unit/intelligence/test_adapters.py — verbatim test: the milestones and summary in the Stage 3 output are deep-equal to those in the technical_estimate_json input (no recompute, rename, restyle or drop).
- UNIT020 [ ] tests/unit/intelligence/test_adapters.py — accumulation test: each stage adds its block without losing the previous ones (Stage 1 -> analysis; Stage 2 -> analysis+estimate; Stage 3 -> the merged final MilestoneProposal).
- UNIT021 [ ] tests/unit/intelligence/test_config.py — verify get_maturity_threshold() returns 8 when MATURITY_THRESHOLD is unset, returns the parsed int when set to a valid integer, and raises a clear configuration error when set to a non-integer value (no silent fallback).
- UNIT022 [ ] tests/unit/intelligence/test_prompts.py — verify the three staged prompt templates exist at their subfolder paths (s2-estimation/analyze-requirement.j2, s2-estimation/estimate-full.j2, s2-estimation/estimate-discovery.j2), extend base/base-role.j2, and render without error when given their documented context variables.

## End Unit Test List

## Integration Test List

- INT001 [ ] tests/integration/api/test_proposals.py — update template-path assertions to the new subfolder-prefixed paths used by the adapters (lines ~526-669).
- INT002 [ ] tests/integration/api/test_proposals.py — verify GET /api/projects/{id} and POST /{projectId}/refine endpoints continue to expose the proposal in the same format with proposal embedded; intermediate artifacts (requirement_analyses, technical_estimates) are NOT exposed in API responses.
- INT003 [ ] tests/integration/pipeline/test_project_fixed_pipeline.py — full pipeline integration: given a project_fixed project, exercise the Telegram handler processing path (which owns persistence) so that generate_project_fixed_proposal runs end-to-end and a document exists in requirement_analyses, one in technical_estimates, and one in proposal_versions. Assert the proposal_versions document carries the merged JSON (analysis + estimate + proposal). The orchestrator itself returns the accumulated JSON and does NOT persist; persistence is asserted at the handler level.
- INT004 [ ] tests/integration/pipeline/test_project_fixed_pipeline.py — maturity branching integration: with maturity_score >= MATURITY_THRESHOLD, verify technical_estimates contains milestones+summary and estimate_type='full'; with maturity_score < MATURITY_THRESHOLD, verify it contains scope_matrix, phase0_hours, post_discovery_hourly_rate, open_questions and estimate_type='discovery'.
- INT005 [ ] tests/integration/pipeline/test_project_fixed_pipeline.py — guard-rail integration: feed an invalid JSON output for Etapa 1 (or 2) and assert PipelineError is raised, no PREMIUM call is made for Etapa 3, and no proposal_versions document is created.
- INT006 [ ] tests/integration/pipeline/test_project_fixed_pipeline.py — idempotency integration: if Etapa 3 fails after Etapas 1-2 succeed, the persisted technical_estimate remains reusable on retry without re-running Etapas 1-2.
- INT007 [ ] tests/integration/pipeline/test_staff_augmentation_regression.py — verify staff_augmentation still uses the direct generate_proposal path with no Etapa 1/2 calls and no requirement_analyses or technical_estimates inserts.
- INT008 [ ] tests/integration/bots/test_telegram_handlers.py — verify the Telegram commands /analizar, /procesar, /refinar keep the current telemetry message structure and that /procesar routes by contract_type correctly.
- INT009 [ ] tests/integration/api/test_proposals.py — external contract integration: the document persisted in proposal_versions.proposal_data validates against MilestoneProposal and GET /api/projects/{id} exposes the proposal with the exact same structure the Workana dashboard consumes (proposal_header, milestones[], summary, technical_pitch, questions_for_client).

## End Integration Test List

## UI Test List

(empty)

## End UI Test List

## Reviewer List

- TASK001:
    - ACK001 [ ] All seven templates exist at the new subfolder paths with semantic prefixes (analyze-, estimate-, write-, refine-, evaluate-, format-); the move uses the plain shell `mv` command
    - ACK002 [ ] No template file remains at the old name or old location
    - ACK095 [ ] A repository-wide search confirms no bare template reference (e.g. 'evaluation.j2', 'proposal.j2', 'base_role.j2') remains outside the new subfolders
- TASK002:
    - ACK003 [ ] Every Jinja template reference in the listed files (gemini.py, openrouter.py, factory.py, tests, docs) — including template_name string literals, not only get_template() calls — references the new subfolder-prefixed path
    - ACK004 [ ] Running the test suite shows no template-not-found errors caused by the rename
    - ACK005 [ ] docs/CONTRACT_TYPE_FEATURE.md and docs/USAGE_EXAMPLES.md reflect the new paths
- TASK003:
    - ACK006 [ ] app/models/analysis.py exists with Entities and RequirementAnalysis classes (importable), where RequirementAnalysis.gaps is a list of strings
    - ACK007 [ ] RequirementAnalysis.maturity_score is constrained to integers 1..10
    - ACK008 [ ] RequirementAnalysis.branch only accepts the literal values 'full' or 'discovery'
    - ACK009 [ ] Instantiating RequirementAnalysis with valid data succeeds and with invalid data raises ValidationError
- TASK004:
    - ACK011 [ ] app/models/estimate.py exists with TechnicalEstimateFull and TechnicalEstimateDiscovery classes
    - ACK012 [ ] TechnicalEstimateFull.estimate_type is the literal 'full' and TechnicalEstimateDiscovery.estimate_type is the literal 'discovery'
    - ACK013 [ ] Both models reuse Milestone, Task, and MilestoneProposalSummary imported from app.models.project
    - ACK014 [ ] Valid example data validates successfully for both models; invalid data raises ValidationError
    - ACK015 [ ] Both models include a model_used (str) field for audit
- TASK005:
    - ACK016 [ ] Repository exposes insert() and get_latest_by_project_id() methods
    - ACK017 [ ] get_latest_by_project_id returns the document with the highest created_at for the given project_id (lookup strictly by created_at DESC; no version_number is used)
    - ACK018 [ ] Required indexes (project_id + created_at DESC, link_hash) are declared on the collection
    - ACK020 [ ] Repository does not introduce any new external API endpoints
- TASK006:
    - ACK021 [ ] Repository exposes insert() and get_latest_by_project_id() methods
    - ACK022 [ ] Documents for 'full' branch persist milestones and summary, while 'discovery' branch persists scope_matrix, phase0_hours, post_discovery_hourly_rate, and open_questions
    - ACK023 [ ] get_latest_by_project_id returns the document with the highest created_at for the given project_id (no version_number is used)
    - ACK024 [ ] Required indexes (project_id + created_at DESC, link_hash) are declared on the collection
- TASK007:
    - ACK026 [ ] Template exists at app/intelligence/prompts/s2-estimation/analyze-requirement.j2
    - ACK027 [ ] Template extends base/base-role.j2
    - ACK028 [ ] Template accepts full_description and threshold variables
    - ACK029 [ ] Output instructions explicitly require maturity_score (1-10 int), maturity_reason, entities, gaps, branch
    - ACK030 [ ] Branch rule (>= threshold → 'full', else → 'discovery') is stated in the prompt instructions
- TASK008:
    - ACK031 [ ] Template exists at app/intelligence/prompts/s2-estimation/estimate-full.j2
    - ACK032 [ ] Template accepts analysis_json as input
    - ACK033 [ ] Output schema defines milestones[] with step, name, tasks (description, hours_with_overhead), hours_with_overhead, subtotal
    - ACK034 [ ] Output schema defines summary with total_hours, total_budget, delivery_time_weeks, hourly_rate_applied
    - ACK035 [ ] 270h minimum rule is preserved as a constraint inside the template
    - ACK036 [ ] Template instructions explicitly forbid commercial/persuasive language; this is a Stage 2A gatekeeper
- TASK009:
    - ACK037 [ ] Template exists at app/intelligence/prompts/s2-estimation/estimate-discovery.j2
    - ACK038 [ ] Template accepts analysis_json as input
    - ACK039 [ ] Output schema defines scope_matrix with in_scope and out_of_scope lists
    - ACK040 [ ] Output schema defines phase0_hours, post_discovery_hourly_rate, and open_questions
    - ACK041 [ ] Template instructions explicitly forbid commercial/persuasive language; this is a Stage 2B gatekeeper
- TASK010:
    - ACK042 [ ] Template at app/intelligence/prompts/s3-commercial/write-proposal.j2 contains zero instructions to COMPUTE hours, prices, milestones, or subtotals (it may only carry them through verbatim), and explicitly forbids omitting, renaming, restyling or summarizing milestones and summary
    - ACK043 [ ] Template accepts technical_estimate_json as the sole technical source
    - ACK044 [ ] Output schema is the full MilestoneProposal contract: proposal_header, milestones, summary, technical_pitch, questions_for_client (milestones and summary carried through verbatim from the technical estimate)
    - ACK045 [ ] Conditional CTA and \n\n maquetation are preserved
    - ACK046 [ ] References inside the prompt to numeric generation (270h, floors, milestone construction) are removed
    - ACK093 [ ] The Stage 3 rendered output validates against MilestoneProposal from app/models/project.py and exposes all six fields required by the Workana dashboard
- TASK011:
    - ACK047 [ ] IntelligencePort declares the three new abstract methods with the exact signatures above
    - ACK048 [ ] Existing generate_proposal and refine_proposal abstract methods remain unchanged
    - ACK049 [ ] Imports for Any and CircuitBreaker are present
    - ACK050 [ ] The module compiles without abstract-method-not-implemented errors once the adapters are updated
- TASK012:
    - ACK096 [ ] app/intelligence/config.py exists with a get_maturity_threshold() helper returning an int
    - ACK097 [ ] get_maturity_threshold() reads MATURITY_THRESHOLD with default 8 and raises a clear configuration error when the value is present but not a valid integer
- TASK013:
    - ACK052 [ ] analyze_requirement calls Gemini with response_mime_type='application/json' and validates the result with RequirementAnalysis.model_validate
    - ACK053 [ ] estimate_technical selects estimate-full.j2 when branch=='full' and estimate-discovery.j2 when branch=='discovery', each with response_mime_type='application/json' and the corresponding Pydantic validation
    - ACK054 [ ] write_commercial_proposal renders s3-commercial/write-proposal.j2 with technical_estimate_json and does not call any numeric-recomputation prompt
    - ACK055 [ ] generate_project_fixed_proposal orchestrates the three stages in order; if Etapa 1 or 2 raises PipelineError, Etapa 3 is never called
    - ACK056 [ ] generate_proposal (staff aug) and refine_proposal remain functionally unchanged
    - ACK057 [ ] The adapter calls get_maturity_threshold() to obtain the threshold passed to analyze_requirement
- TASK014:
    - ACK059 [ ] analyze_requirement validates the LLM response with RequirementAnalysis.model_validate (post-hoc)
    - ACK060 [ ] estimate_technical validates with the matching TechnicalEstimateFull/TechnicalEstimateDiscovery model post-hoc
    - ACK061 [ ] write_commercial_proposal renders s3-commercial/write-proposal.j2 with technical_estimate_json
    - ACK062 [ ] generate_project_fixed_proposal orchestrates the three stages in order; if Etapa 1 or 2 raises PipelineError, Etapa 3 is never called
    - ACK063 [ ] generate_proposal (staff aug) and refine_proposal remain functionally unchanged
    - ACK064 [ ] The adapter calls get_maturity_threshold() to obtain the threshold passed to analyze_requirement
- TASK015:
    - ACK065 [ ] select_initial_proposal_template returns the new subfolder-prefixed paths for all branches
    - ACK066 [ ] select_estimation_template returns 's2-estimation/estimate-full.j2' when maturity_score >= threshold
    - ACK067 [ ] select_estimation_template returns 's2-estimation/estimate-discovery.j2' when maturity_score < threshold
    - ACK068 [ ] Existing call sites of select_initial_proposal_template continue to compile
    - ACK069 [ ] New helper is importable from app.intelligence.factory
- TASK016:
    - ACK070 [ ] Handler branches by contract_type to the new orchestrator vs the existing generate_proposal
    - ACK071 [ ] On project_fixed success, a document is inserted into requirement_analyses, one into technical_estimates, and one into proposal_versions; the proposal_versions.proposal_data is the flat MilestoneProposal contract (proposal_header, milestones, summary, technical_pitch, questions_for_client), not the nested accumulated shape
    - ACK072 [ ] On staff_augmentation, behavior is unchanged
    - ACK073 [ ] Telemetry message strings keep their current structure (no added/removed fields)
    - ACK074 [ ] No new external command or response format is introduced to the Telegram bot
- TASK017:
    - ACK076 [ ] The parsed int threshold is forwarded to analyze_requirement
    - ACK077 [ ] The persisted RequirementAnalyses document contains maturity_threshold_used matching the value used
    - ACK078 [ ] When the env var is unset, the pipeline still runs with threshold 8
    - ACK079 [ ] When the env var is set to a non-integer, the code raises a clear configuration error rather than silently falling back
    - ACK098 [ ] get_maturity_threshold is the single source of the threshold and no inline os.getenv('MATURITY_THRESHOLD') read remains in the adapters
- TASK018:
    - ACK080 [ ] write-proposal.j2 contains no instructions to derive hours, prices, milestones, subtotals, or technical floors
    - ACK081 [ ] estimate-full.j2 contains the migrated 270h minimum rule, technical floors, and milestone construction logic
    - ACK082 [ ] Both templates are internally consistent (Stage 2A produces numbers, Stage 3 only renders them)
    - ACK083 [ ] The split does not alter the visual output format (\n\n maquetation and CTA preserved)
- TASK019:
    - ACK084 [ ] docs/USAGE_EXAMPLES.md includes the 4-stage pipeline description with template paths
    - ACK085 [ ] MATURITY_THRESHOLD env var and its default are documented
    - ACK086 [ ] Branch rule (>=T → full, <T → discovery) is documented
    - ACK087 [ ] staff_augmentation is described as unchanged
    - ACK088 [ ] External interfaces (REST API, Telegram bot) are described as unchanged
- TASK020:
    - ACK089 [ ] PipelineError is defined in app/exceptions.py and is importable
    - ACK090 [ ] analyze_requirement and estimate_technical raise PipelineError when Pydantic validation fails
    - ACK091 [ ] The orchestrator aborts before the Stage 3 (PREMIUM) call when PipelineError is raised
    - ACK092 [ ] PipelineError follows the existing exception convention in app/exceptions.py

## End Reviewer List