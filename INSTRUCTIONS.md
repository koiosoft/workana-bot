## Current Objective
Correct the project update by ID in the API (patch: `/api/projects/{projectId}`) to generate an entry in the `proposal_versions` collection, setting the `source_of_changes` field to `"HUMAN"`. Review, correct, and add the necessary unit and integration tests.

## Key Artifacts (to focus on)
- **Files**: 
  - `app/api/routes/projects.py`
  - `app/database/proposal_versions_repository.py`
  - `app/models/proposal_version.py`
  - `tests/unit/api/test_projects.py`
  - `tests/integration/test_projects.py`
- **Classes/Interfaces**: 
  - `ProposalVersionsRepository`
  - `ProposalVersion`
  - `ProjectsRepository`
- **Configuration**: 
  - `MONGO_URI` (for integration tests)

## Task List
- [x] Read `app/api/routes/projects.py` to understand how the `update_project` endpoint interacts with the `ProjectsRepository` and `ProposalVersionsRepository`, then modify the `update_project` function to remove the use of the `proposal` field in the `projects` collection and instead call `ProposalVersionsRepository.insert_version()` to create a new version in the `proposal_versions` collection, ensuring the `source_of_changes` is set to `"HUMAN"`.
- [x] Examine `app/database/proposal_versions_repository.py` and `app/models/proposal_version.py` to ensure that the `insert_version` method in `ProposalVersionsRepository` is correctly handling the insertion of new proposal versions with the `source_of_changes` field set to `"HUMAN"` when called by the `update_project` endpoint.
- [x] Review `app/database/projects_repository.py` and modify the `update_project_by_id` method to remove any logic that updates the `proposal` field in the `projects` collection, as this is no longer needed.
- [x] Create a new unit test in `tests/unit/api/test_projects.py` that mocks the `update_project` endpoint and verifies that calling it generates a new entry in the `proposal_versions` collection with the `source_of_changes` set to `"HUMAN"`, and does not modify the `proposal` field in the `projects` collection.
- [x] Create a new integration test in `tests/integration/test_projects.py` that uses the `MONGO_URI` configuration to test the `update_project` endpoint in a real MongoDB environment, ensuring that it correctly generates a new entry in the `proposal_versions` collection with the `source_of_changes` set to `"HUMAN"`.
- [x] Review and correct any existing unit or integration tests in `tests/unit/api/test_projects.py` and `tests/integration/test_projects.py` that may be relying on the `proposal` field in the `projects` collection, updating them to reflect the new behavior of using the `proposal_versions` collection.
- [x] Ensure that all test functions in `tests/unit/api/test_projects.py` and `tests/integration/test_projects.py` are strictly typed, use `pytest.mark.asyncio`, and do not include network I/O, using mocks instead for unit tests.
- [x] Add logging and error handling to the `update_project` function in `app/api/routes/projects.py` to ensure that any errors during the creation of a new proposal version are properly captured and returned to the client.

## End Task List