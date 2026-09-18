# Task 20

## Task
Define PipelineError in app/exceptions.py for the staged pipeline guard rail, used by the Stage 1 and Stage 2 validation gatekeepers. [ASSET: ./assets/TASK020_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.

## Status
Completed

## Justification

### What was done
Added a `PipelineError` exception class to `app/exceptions.py` following the
convention of `AIConnectionError`. This exception is the guard-rail signal
raised when Stage 1 (analyze-requirement) or Stage 2 (estimate-full /
estimate-discovery) LLM output fails Pydantic validation. Both Gemini and
OpenRouter adapters will import and raise this exception when
`RequirementAnalysis.model_validate()` or `TechnicalEstimate*.model_validate()`
raise a `pydantic.ValidationError`, stopping the pipeline before the PREMIUM
(Stage 3) call is billed.

### Why approaches chosen
- Follows the existing exception convention (simple `Exception` subclass)
- Minimal implementation: no extra fields required (unlike CircuitBreakerError
  which carries `failures`/`backoff`)
- References in `app/models/analysis.py` and `app/models/estimate.py` already
  mention PipelineError by name — this class resolves those dangling references

### Tradeoffs or technical debt
None identified. The class is lightweight and ready for import by the adapters.
