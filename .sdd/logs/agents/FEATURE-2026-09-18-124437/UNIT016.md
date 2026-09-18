# Test 16 (unit test)

## Task
tests/unit/intelligence/test_adapters.py — regression test: staff_augmentation path (generate_proposal) remains functionally unchanged after the refactor.

## Status
Completed

## Justification
Staff augmentation generate_proposal path remains functionally unchanged after refactor. Both GeminiAdapter (gemini.py line 175) and OpenRouterAdapter (openrouter.py line 317) still select s3-commercial/write-proposal-staffing.j2 when contract_type='staff_augmentation', returning cover_letter and budget_summary fields. Regression tests test_staff_augmentation_generate_proposal_unchanged (test_adapters.py) and test_staff_augmentation_path_unchanged (test_gemini_adapter.py) verify this behavior. All pass.
