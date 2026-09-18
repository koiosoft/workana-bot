# Test 2 (unit test)

## Task
tests/unit/intelligence/test_factory.py — verify select_estimation_template returns 's2-estimation/estimate-full.j2' when maturity_score >= threshold and 's2-estimation/estimate-discovery.j2' when maturity_score < threshold.

## Status
Completed

## Justification
The test file `tests/unit/intelligence/test_factory.py` already contains a `TestSelectEstimationTemplate` class (lines 511–533) with five tests that fully cover the specification:

- `test_returns_full_j2_when_maturity_exceeds_threshold` — 0.8 >= 0.5 → full
- `test_returns_full_j2_when_maturity_equals_threshold` — 0.5 >= 0.5 → full
- `test_returns_discovery_j2_when_maturity_below_threshold` — 0.3 < 0.5 → discovery
- `test_returns_discovery_j2_for_zero_maturity` — 0.0 < 0.5 → discovery
- `test_returns_full_j2_for_perfect_maturity` — 1.0 >= 0.5 → full

All assertions use exact path strings (`'s2-estimation/estimate-full.j2'` and `'s2-estimation/estimate-discovery.j2'`) matching the contract in `select_estimation_template` (lines 95–114 of `app/intelligence/factory.py`). No additional tests are needed.
