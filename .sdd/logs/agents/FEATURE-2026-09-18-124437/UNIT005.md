# Test 5 (unit test)

## Task
tests/unit/intelligence/test_adapters.py — verify Gemini adapter passes response_mime_type='application/json' for Etapa 1 and Etapa 2 calls.
## Status
Completed

## Justification
Verified GeminiAdapter passes config=dict(response_mime_type='application/json') in analyze_requirement (gemini.py line 438) and estimate_technical (gemini.py line 509). Stage 3 (write_commercial_proposal, gemini.py line 593) does NOT include the config override as expected. Tests test_analyze_requirement_passes_response_mime_type and test_estimate_technical_passes_response_mime_type added to test_gemini_adapter.py. OpenRouterAdapter cannot use this Gemini-specific feature (it uses post-hoc JSON extraction). All pass.
