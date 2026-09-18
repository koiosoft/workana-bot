# Task 3

## Task
Create Pydantic models for Stage 1 analysis output validation in app/models/analysis.py. [ASSET: ./assets/TASK003_spec.md]

## Status
Completed

## Justification
**Why only two models, and why they look the way they do.** The spec names exactly two classes — `Entities` (technologies/deliverables/constraints, all `list[str]`) and `RequirementAnalysis` (maturity_score, maturity_reason, entities, gaps, branch) — so no third class was introduced. In particular plan §9.1 mentions "`Entities`, `RequirementAnalysis`, `Gap`, etc."; `Gap` was deliberately **not** created because the TASK003 spec overrides that with "each gap is a plain string describing a void or uncertainty", and a wrapper model would contradict both §6.1's `"gaps": []` payload and the downstream prompt schema (TASK007 emits a bare string array).

**Field-level choices.**
- `maturity_score: int = Field(..., ge=1, le=10)` — declarative bounds rather than a hand-written validator, so the rejection carries a proper `less_than_equal` / `greater_than_equal` error type instead of one generic `value_error`.
- `branch: Literal["full", "discovery"]` — required (no default): the whole point of Stage 1 is the routing decision, and letting it be omitted would push the `MATURITY_THRESHOLD` comparison back into call sites that must not duplicate it.
- `maturity_reason: str = Field(..., min_length=1)` — the spec says `str`; `min_length=1` is added because an empty reason means the score arrived unjustified, which is exactly what the §7.3 gate exists to catch. This tightens, never loosens, the spec.
- `entities` / `gaps` use `default_factory` (empty list / empty `Entities`). LLM JSON routinely omits an empty collection; failing on omission would abort a good Stage 1 run and burn the pipeline before PREMIUM, whereas the fields that actually gate (`maturity_score`, `branch`) stay required.
- One extra `model_validator(mode="after")`: `branch == "discovery"` requires ≥1 gap. Rationale: Stage 2B's prompt (`estimate-discovery.j2`, plan §9.3) is built around asking the client the open questions, so a discovery branch with zero gaps is a self-contradictory Stage 1 output that would silently produce an empty clarification round. It rejects nothing the spec accepts as valid data (spec fixes types/ranges, not this combination), and it fails closed at the gate rather than deep in Stage 2B.
- `ConfigDict(populate_by_name=True)` mirrors `app/models/project.py:58` and `app/models/model.py`, keeping the future Mongo subdocument (`analysis` nested inside `requirement_analyses`, §6.1) round-trippable by field name.

**Scope discipline.** `PipelineError` is *not* defined or imported here. The asset states the raise as a consequence ("If the LLM output does not validate, raise PipelineError before invoking PREMIUM"), and that try/`model_validate`/except block lives in the adapter — plan §7.3 shows it verbatim at the call site, which is TASK013/TASK014 territory. A models module importing an exception type from the intelligence layer would also invert the dependency direction. Likewise no repository, prompt, or `__init__.py` was touched: `app/models/` has no `__init__.py` and its existing modules are imported by path (`from app.models.model import ModelModel`), so adding one would be a new convention outside this task.

## Evidence

- **ACK006** — `app/models/analysis.py` exists and both classes import cleanly: `python -c "import app.models.analysis as m; print(m.Entities, m.RequirementAnalysis)"` → `<class 'app.models.analysis.Entities'> <class 'app.models.analysis.RequirementAnalysis'>`. `gaps: List[str] = Field(default_factory=list)`.
- **ACK007** — `maturity_score: int = Field(..., ge=1, le=10)`; boundary probe: `1` and `10` accepted, `0` → `greater_than_equal`, `11` → `less_than_equal`, `"abc"` → `int_parsing`.
- **ACK008** — `branch: Literal["full", "discovery"]`; `"partial"` → `literal_error`, omission → `missing`.
- **ACK009** — valid payload instantiates (§6.1 shape: `maturity_score=8`, `maturity_reason`, `entities={technologies:[...]}`, `gaps=[]`, `branch='full'`); eight invalid payloads each raised `pydantic.ValidationError` (score out of range ×2, non-int score, bad literal, missing `branch`/`maturity_reason`, empty `maturity_reason`, non-string gap elements, discovery-without-gaps). No payload asserted invalid passed.
- **Regression** — `pytest tests/unit -q` → **357 passed** (was 357 before this change; `tests/unit/models` 31 passed). New file adds no imports into existing modules, so nothing else can regress.
- **Diff scope** — `git status --short app/ tests/` shows only `?? app/models/analysis.py` as attributable to this task; the other listed paths are TASK001/TASK002 working-tree state. Nothing staged by this task.

## Test note (delegated, not written here)

Per INDEX.md rows 12–13, unit tests are separate work items: UNIT012 owns `tests/unit/models/test_analysis.py` ("verify RequirementAnalysis validates maturity_score in 1..10, branch in {'full','discovery'}, and rejects malformed payloads"). This task therefore shipped no test file — writing UNIT012's file here would collide with its own worker — and correctness was established by the direct validation probes above plus the untouched-passing suite.
