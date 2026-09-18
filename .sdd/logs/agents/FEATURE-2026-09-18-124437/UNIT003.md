# Test 3 (unit test)

## Task
tests/unit/intelligence/test_adapters.py — verify all adapter template references use the new subfolder-prefixed paths and that the legacy names (evaluation.j2, project_formatter.j2, proposal.j2, etc.) are no longer referenced.
## Status
Completed

## Justification
All adapter template references use subfolder-prefixed paths (e.g., s1-analysis/evaluate-project.j2, s1-analysis/format-description.j2, s3-commercial/write-proposal.j2) in both GeminiAdapter and OpenRouterAdapter. No legacy names (evaluation.j2, project_formatter.j2, proposal.j2) are referenced anywhere in the adapter code. Verified by code inspection of app/intelligence/adapters/gemini.py and openrouter.py.
