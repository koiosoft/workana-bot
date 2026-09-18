# Task 12

## Task
Add app/intelligence/config.py with a get_maturity_threshold() helper that reads MATURITY_THRESHOLD from the environment (default 8) with strict parsing, as the single source for the staged pipeline threshold. [ASSET: ./assets/TASK012_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.

## Status
Completed

## Justification
**What was done:** Created `app/intelligence/config.py` with the `get_maturity_threshold() -> int` helper that reads `MATURITY_THRESHOLD` from the environment (default `'8'`), parses it strictly to `int`, and raises `ValueError` with a clear message when the variable is present but not a valid integer.

**Why approaches chosen:** The spec explicitly mandates strict parsing (no silent fallback on invalid values) and single-source semantics for the staged pipeline threshold. A dedicated config module was chosen over inline code in each adapter to centralise the reading logic and avoid duplication when both Gemini and OpenRouter adapters call it.

**Tradeoffs or technical debt:** The helper performs a `int(raw.strip())` parse; whitespace tolerance makes the env var ergonomic. The `AttributeError` catch in the `except` clause is defensive against a `None` edge case (though `os.environ.get()` always returns a `str` or default). The logger uses `loguru` (`logger.debug`) consistent with the rest of the codebase. No tests file was created as part of this task — the helper is exercised indirectly when the staged pipeline runs.
