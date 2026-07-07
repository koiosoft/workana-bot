## Current Objective
Fix the test failures related to invalid ObjectId usage and event loop closure in the application.

## Task List
- [x] **Error in app/database/proposal_versions_repository.py:111**
  - **Error:** bson.errors.InvalidId: 'version-1' is not a valid ObjectId, it must be a 12-byte input or a 24-character hex string
  - **Context:** The test is trying to update a proposal version using a string 'version-1' as an ObjectId, which is invalid.
  - **Action Required:** Modify the test setup to use a valid MongoDB ObjectId for the `_id` field in the mock data. Ensure that the `find_one` method returns a document with an `_id` that is a valid ObjectId (either as a string with 24 hex characters or as a bson.ObjectId instance).

- [x] **Error in app/database/proposal_versions_repository.py:111**
  - **Error:** bson.errors.InvalidId: 'version-custom' is not a valid ObjectId, it must be a 12-byte input or a 24-character hex string
  - **Context:** Similar to the previous error, the test is using an invalid string 'version-custom' as an ObjectId.
  - **Action Required:** Update the test to use a valid MongoDB ObjectId for the `_id` field in the mock data. Ensure that the `find_one` method returns a document with a valid `_id`.

- [x] **Error in app/database/users_repository.py:138**
  - **Error:** RuntimeError: Event loop is closed
  - **Context:** The test is attempting to call `ensure_indexes` on a repository, which calls `create_index` on a collection, but the event loop is closed during this operation.
  - **Action Required:** Investigate why the event loop is closed during the test execution. Ensure that the test is properly setting up and tearing down the event loop, and that all asynchronous operations are correctly awaited and handled within the test environment.