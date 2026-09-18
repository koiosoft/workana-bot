# Test 1 (unit test)

## Task
tests/unit/intelligence/test_factory.py — verify select_initial_proposal_template returns the new subfolder-prefixed paths and select_estimation_template(maturity_score, threshold) routes to estimate-full.j2 or estimate-discovery.j2 correctly.

## Status
Completed

## Justification
All three test requirements were already present in the existing test file:

1. **`TestSelectInitialProposalTemplate`** — already tests subfolder-prefixed paths:
   - `test_returns_proposal_j2_for_project_fixed` → `"s3-commercial/write-proposal.j2"` ✓
   - `test_returns_proposal_staffing_j2_for_staff_augmentation` → `"s3-commercial/write-proposal-staffing.j2"` ✓
   - `test_defaults_to_proposal_j2_for_unknown_type` → `"s3-commercial/write-proposal.j2"` ✓

2. **`TestSelectEstimationTemplate`** — already tests routing to `estimate-full.j2` when score >= threshold:
   - `test_returns_full_j2_when_maturity_exceeds_threshold` (0.8 >= 0.5) → `"s2-estimation/estimate-full.j2"` ✓
   - `test_returns_full_j2_when_maturity_equals_threshold` (0.5 >= 0.5) → `"s2-estimation/estimate-full.j2"` ✓
   - `test_returns_full_j2_for_perfect_maturity` (1.0 >= 0.5) → `"s2-estimation/estimate-full.j2"` ✓

3. **`TestSelectEstimationTemplate`** — already tests routing to `estimate-discovery.j2` when score < threshold:
   - `test_returns_discovery_j2_when_maturity_below_threshold` (0.3 < 0.5) → `"s2-estimation/estimate-discovery.j2"` ✓
   - `test_returns_discovery_j2_for_zero_maturity` (0.0 < 0.5) → `"s2-estimation/estimate-discovery.j2"` ✓

The test methods match the implementation in `app/intelligence/factory.py` exactly:
- `select_initial_proposal_template` returns `"s3-commercial/write-proposal.j2"` for `"project_fixed"` (and fallback), and `"s3-commercial/write-proposal-staffing.j2"` for `"staff_augmentation"`.
- `select_estimation_template` returns `"s2-estimation/estimate-full.j2"` when `maturity_score >= threshold`, and `"s2-estimation/estimate-discovery.j2"` otherwise.
No new test methods were needed — the existing coverage already satisfies all three task requirements.
