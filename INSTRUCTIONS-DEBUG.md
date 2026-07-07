## Current Objective
Resolve the integration test failure where the `/api/projects` endpoint does not return any projects despite a proposal version being inserted.

## Task List
- [x] **Error in tests/integration/test_projects_integration.py:205**
  - **Error:** `AssertionError: assert 0 >= 1`
  - **Context:** The test inserts a proposal version document but no corresponding project document exists in the `projects` collection, resulting in an empty response from the `/api/projects` endpoint.
  - **Action Required:** 
    1. Modify the test to insert a matching project document into the `projects` collection with the same `project_id` as the inserted proposal version.
    2. Ensure the project document contains the required fields (`link_hash`, `proposal_status`, etc.) to be retrieved by the `get_projects` method.
    3. Verify that the `projects` collection is properly queried by the API endpoint and that the `populate_proposals_for_projects` method correctly joins with the `proposal_versions` collection using the `project_id` field.