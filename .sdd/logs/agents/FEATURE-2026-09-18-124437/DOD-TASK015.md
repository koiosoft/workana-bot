# TASK015

## Task
Update app/intelligence/factory.py template selection helpers for the new subfolder paths and add a maturity-aware estimation template selector. [ASSET: ./assets/TASK015_spec.md]

## ACK Checklist

- [x] ACK065 select_initial_proposal_template returns the new subfolder-prefixed paths for all branches
- [x] ACK066 select_estimation_template returns 's2-estimation/estimate-full.j2' when maturity_score >= threshold
- [x] ACK067 select_estimation_template returns 's2-estimation/estimate-discovery.j2' when maturity_score < threshold
- [x] ACK068 Existing call sites of select_initial_proposal_template continue to compile
- [x] ACK069 New helper is importable from app.intelligence.factory


## Review: APPROVED

