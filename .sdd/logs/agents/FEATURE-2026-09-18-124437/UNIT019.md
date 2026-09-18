# Test 19 (unit test)

## Task
tests/unit/intelligence/test_adapters.py — verbatim test: the milestones and summary in the Stage 3 output are deep-equal to those in the technical_estimate_json input (no recompute, rename, restyle or drop).

## Status
Completed

## Justification
Verbatim test confirms milestones and summary in Stage 3 output are deep-equal to those in the technical_estimate_json input — no recompute, rename, restyle or drop. Both adapters inject these fields from technical_estimate after LLM response (gemini.py lines 613-616, openrouter.py lines 776-779). Tests test_write_commercial_proposal_verbatim_milestones_summary in both files mock an LLM response with WRONG values and verify the output uses the original estimate values. All pass.
