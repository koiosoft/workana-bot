# TASK006

## Task
Create the TechnicalEstimatesRepository in app/database/technical_estimates_repository.py with insert and get_latest_by_project_id methods (no sequential versioning). [ASSET: ./assets/TASK006_spec.md]

## ACK Checklist

- [x] ACK021 Repository exposes insert() and get_latest_by_project_id() methods
- [x] ACK022 Documents for 'full' branch persist milestones and summary, while 'discovery' branch persists scope_matrix, phase0_hours, post_discovery_hourly_rate, and open_questions
- [x] ACK023 get_latest_by_project_id returns the document with the highest created_at for the given project_id (no version_number is used)
- [x] ACK024 Required indexes (project_id + created_at DESC, link_hash) are declared on the collection


## Review: APPROVED

