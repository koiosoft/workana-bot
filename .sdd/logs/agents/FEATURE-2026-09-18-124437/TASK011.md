# Task 11

## Task
Add the three new abstract methods to IntelligencePort in app/intelligence/port.py for the staged pipeline. [ASSET: ./assets/TASK011_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.

## Status
Completed

## Justification
Added three abstract methods (`analyze_requirement`, `estimate_technical`, `write_commercial_proposal`) to `IntelligencePort` in `app/intelligence/port.py`. These mirror the new staged pipeline stages from §7.1 and must be implemented by both Gemini and OpenRouter adapters. The signatures follow the spec exactly, using the `TYPE_CHECKING` forward-reference pattern already established in the file for `CircuitBreaker`. Syntax validated with `ast.parse`.
