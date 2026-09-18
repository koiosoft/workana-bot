# Test 10 (unit test)

## Task
tests/unit/intelligence/test_adapters.py — verify MATURITY_THRESHOLD env var is read with default 8 and forwarded to analyze_requirement.

## Status
Completed

## Justification
Verified MATURITY_THRESHOLD env var is read with default '8' in app/intelligence/config.py line 27. Both adapters' generate_project_fixed_proposal methods (gemini.py line 652, openrouter.py line 802) call get_maturity_threshold() and forward it to analyze_requirement as maturity_threshold parameter. Tests test_maturity_threshold_default_forwarded (test_adapters.py) and test_maturity_threshold_read_and_forwarded (test_gemini_adapter.py) verify the threshold=8 is passed to _render_prompt. All pass.
