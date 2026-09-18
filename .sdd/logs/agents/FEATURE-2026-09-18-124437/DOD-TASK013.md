# TASK013

## Task
Update the Gemini adapter to implement the new staged pipeline methods with strict Pydantic validation and structured output, plus the project_fixed orchestrator. [ASSET: ./assets/TASK013_spec.md]

## ACK Checklist

- [x] ACK052 analyze_requirement calls Gemini with response_mime_type='application/json' and validates the result with RequirementAnalysis.model_validate
- [x] ACK053 estimate_technical selects estimate-full.j2 when branch=='full' and estimate-discovery.j2 when branch=='discovery', each with response_mime_type='application/json' and the corresponding Pydantic validation
- [x] ACK054 write_commercial_proposal renders s3-commercial/write-proposal.j2 with technical_estimate_json and does not call any numeric-recomputation prompt
- [x] ACK055 generate_project_fixed_proposal orchestrates the three stages in order; if Etapa 1 or 2 raises PipelineError, Etapa 3 is never called
- [x] ACK056 generate_proposal (staff aug) and refine_proposal remain functionally unchanged
- [x] ACK057 The adapter calls get_maturity_threshold() to obtain the threshold passed to analyze_requirement


## Review: APPROVED

