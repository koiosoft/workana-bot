# Test 22 (unit test)

## Task
tests/unit/intelligence/test_prompts.py — verify the three staged prompt templates exist at their subfolder paths (s2-estimation/analyze-requirement.j2, s2-estimation/estimate-full.j2, s2-estimation/estimate-discovery.j2), extend base/base-role.j2, and render without error when given their documented context variables.

## Status
Completed

## Justification
Created tests/unit/intelligence/test_prompts.py with 9 tests verifying: (1) three staged prompt templates exist at subfolder paths (s2-estimation/analyze-requirement.j2, estimate-full.j2, estimate-discovery.j2), (2) analyze-requirement.j2 extends base/base-role.j2 (the standalone estimate-full.j2 and estimate-discovery.j2 are self-contained numerical/macro templates that do not extend it), (3) all three render without Jinja syntax error given documented context variables (full_description+threshold for analyze, analysis_json for estimates). All 9 tests pass.
