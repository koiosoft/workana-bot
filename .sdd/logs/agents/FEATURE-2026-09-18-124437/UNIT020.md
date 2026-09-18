# Test 20 (unit test)

## Task
tests/unit/intelligence/test_adapters.py — accumulation test: each stage adds its block without losing the previous ones (Stage 1 -> analysis; Stage 2 -> analysis+estimate; Stage 3 -> the merged final MilestoneProposal).

## Status
Completed

## Justification
Accumulation test verifies that generate_project_fixed_proposal returns analysis + estimate + proposal keys, each stage adding its block without losing previous ones. Both adapters' orchestrator methods (gemini.py lines 656-683, openrouter.py lines 808-835) call the three stages in sequence and return accumulated dict. Tests test_generate_project_fixed_proposal_accumulates in both files mock all three stage methods and verify result contains and preserves all three blocks. All pass.
