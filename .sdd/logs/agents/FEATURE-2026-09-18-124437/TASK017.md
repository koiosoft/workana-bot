# Task 17

## Task
Consolidate the maturity-threshold wiring: verify the get_maturity_threshold helper is the single source and the value is persisted on the analysis record. [ASSET: ./assets/TASK017_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.

## Status
Completed

## Justification

### Verification Results

1. **`get_maturity_threshold()` is the single source of truth**
   - Defined in `app/intelligence/config.py` (lines 16-39)
   - Reads `MATURITY_THRESHOLD` env var with default "8"
   - Raises clear `ValueError` when env var is present but not a valid integer (ACK079 compliant)
   - Documented as the single source in the module docstring

2. **Both adapters call it inside `generate_project_fixed_proposal`**
   - `app/intelligence/adapters/gemini.py:652` — `threshold = get_maturity_threshold()`
   - `app/intelligence/adapters/openrouter.py:802` — `threshold = get_maturity_threshold()`
   - Both pass the resolved threshold to Stage 1 (`analyze_requirement`) as `maturity_threshold=`

3. **Value is persisted on the analysis record**
   - The Telegram handler (`app/bots/telegram/handlers.py:473`) stores `maturity_threshold_used` via `get_maturity_threshold()`
   - The repository (`app/database/requirement_analyses_repository.py:140-141`) normalises it with `_as_int()` ensuring it becomes a BSON int

4. **Duplicated inline env read eliminated**
   - FIXED: Replaced `int(os.getenv("MATURITY_THRESHOLD", "8"))` in handlers.py with `get_maturity_threshold()`
   - Added import: `from app.intelligence.config import get_maturity_threshold`

### Final State
No remaining `os.environ.get("MATURITY_THRESHOLD")`/`os.getenv("MATURITY_THRESHOLD")` calls exist outside `app/intelligence/config.py`. All consumers funnel through `get_maturity_threshold()`, and the resolved value is persisted as `maturity_threshold_used` via the handler + repository layer.
