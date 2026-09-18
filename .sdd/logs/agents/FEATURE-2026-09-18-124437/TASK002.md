# Task 2

## Task
Update every Jinja template reference (get_template calls and template_name literals) across the codebase to the new subfolder-prefixed paths. [ASSET: ./assets/TASK002_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.

## Status
Completed

## Justification
All Jinja template references updated from old flat names to new subfolder-prefixed paths:

### Source code (app/)
- `app/intelligence/adapters/gemini.py` — Already updated. Refs: `s1-analysis/evaluate-project.j2`, `s1-analysis/format-description.j2`, `s3-commercial/write-proposal.j2`, `s3-commercial/write-proposal-staffing.j2`, `s4-refine/refine-proposal.j2`, `s4-refine/refine-proposal-staffing.j2`
- `app/intelligence/adapters/openrouter.py` — Already updated. Same paths.
- `app/intelligence/factory.py` — Already updated. `select_initial_proposal_template()` returns `s3-commercial/write-proposal.j2` / `s3-commercial/write-proposal-staffing.j2`

### Test files — Updated assert values and docstrings
- `tests/unit/intelligence/test_gemini_adapter.py` — 10 assertion/docstring updates
- `tests/unit/intelligence/test_adapters.py` — 8 assertion/docstring updates
- `tests/unit/intelligence/test_factory.py` — 4 assertion/docstring updates (+1 indentation fix)
- `tests/integration/api/test_proposals.py` — 4 get_template() call + assertion updates

### Documentation files — Updated template references
- `docs/CONTRACT_TYPE_FEATURE.md` — 7 outdated .j2 references updated
- `docs/USAGE_EXAMPLES.md` — 1 table cell updated

### Verification
- All 103 unit tests in `tests/unit/intelligence/` pass
- Old `__pycache__` binary files cleaned to prevent stale mock confusion
- No `.j2` references to old flat names remain in source/test/doc files
