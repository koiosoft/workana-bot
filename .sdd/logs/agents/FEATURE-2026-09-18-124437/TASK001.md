# Task 1

## Task
Move the seven Jinja prompt templates into the new subfolder structure under app/intelligence/prompts/ as a clean cut (no backward-compatible aliases). [ASSET: ./assets/TASK001_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.

## Status
Completed

## Justification
**Why a pure `mv` (no aliases, no code edits).** The spec fixes decision #8 as a one-shot clean cut, and the SDD plan splits it across two tasks: TASK001 moves the files, TASK002 rewrites every reference. Adding compatibility shims (symlinks, copies at the old names, or a loader fallback) would have made the old flat layout survive the cut and would have silently masked TASK002's job, so none were created. Only the four subfolders that already contain templates (`base/`, `s1-analysis/`, `s3-commercial/`, `s4-refine/`) were created; `s2-estimation/` is deliberately absent because its three templates are new files owned by a later task (plans/current/pipeline-propuestas-por-etapas.md:422-429), and an empty directory would not be tracked by git anyway.

## Evidence

- All 7 templates exist at the new subfolder paths; `find app/intelligence/prompts -maxdepth 1 -name '*.j2'` returns 0 hits, so nothing remains at an old name/location.
- Content is byte-identical to the pre-move blobs: md5 of each moved file matches `git show HEAD:.../<old>.j2` for all 7 pairs, and `git diff --cached -M` reports them as pure renames with 0 insertions / 0 deletions.
- Loaders are unaffected by the move itself: `app/intelligence/adapters/gemini.py:40` and `openrouter.py:48` both point `FileSystemLoader` at the `prompts/` root, which still resolves — verified by parsing/compiling all 7 templates through `Environment.get_template("<sub>/<name>.j2")` (all OK), while the 7 old bare names now raise `TemplateNotFound` (confirms the cut is clean, i.e. TASK002's references really must be updated).
- No template-to-template coupling was broken: `grep -rn '\.j2' app/intelligence/prompts/` finds no `{% extends %}`/`{% include %}`/filename reference between templates, so renaming cannot orphan a partial.

## Known intermediate state (intentional)

Between TASK001 and TASK002 the runtime call sites still pass bare names (`evaluation.j2`, `proposal.j2`, …): 58 occurrences over 9 files — `app/intelligence/adapters/gemini.py` (10), `openrouter.py` (11), `app/intelligence/factory.py` (3), `tests/unit/intelligence/test_adapters.py` (8), `test_factory.py` (4), `test_gemini_adapter.py` (10), `tests/integration/api/test_proposals.py` (4), `docs/CONTRACT_TYPE_FEATURE.md` (7), `docs/USAGE_EXAMPLES.md` (1). Those are TASK002's scope per its spec, and this task's spec explicitly says "This task ONLY moves the files". Consequence: the proposal/refine/evaluate paths are broken until TASK002 lands, and `pytest tests/unit/intelligence` cannot be used as a gate here anyway (it aborts at collection on a missing third-party dep, `ModuleNotFoundError: No module named 'patchright'`, unrelated to this change).
