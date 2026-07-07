## Current Objective
Fix the integration test failures related to duplicate key constraints in the `providers` and `models` collections when attempting to create duplicate entries via the API.

## Task List
- [x] **Error in tests/integration/test_models_integration.py:120**
  - **Error:** `AssertionError: assert 201 == 409`
  - **Context:** The test `test_create_provider_duplicate_key` is failing because inserting a duplicate provider key into the `providers` collection is not correctly returning a 409 Conflict status code. Instead, it is returning a 201 Created status.
  - **Action Required:** Investigate the `create_provider` endpoint in `app/api/routes/models.py` to verify if the unique index on the `key` field in the `providers` collection is being enforced correctly. Ensure that the API returns a 409 Conflict when a duplicate key is attempted, and that the database schema validation is correctly implemented in `app/database/mongo.py` for the `providers` collection.

- [x] **Error in tests/integration/test_models_integration.py:262**
  - **Error:** `AssertionError: assert 201 == 409`
  - **Context:** The test `test_create_model_duplicate_key` is failing because inserting a duplicate `(model_id, provider_key)` combination into the `models` collection is not correctly returning a 409 Conflict status code. Instead, it is returning a 201 Created status.
  - **Action Required:** Investigate the `create_model` endpoint in `app/api/routes/models.py` to verify if the unique compound index on the `model_id` and `provider_key` fields in the `models` collection is being enforced correctly. Ensure that the API returns a 409 Conflict when a duplicate key combination is attempted, and that the database schema validation is correctly implemented in `app/database/mongo.py` for the `models` collection.