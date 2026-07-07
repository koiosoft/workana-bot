## Current Objective
Add a `source_of_changes` field to MongoDB's `proposal_versions` collection with values "IA" (for proposals created by the Telegram bot) or "HUMAN" (for project updates), and ensure unit/integration tests validate this behavior.

## Key Artifacts (to focus on)
- **Files**:  
  - `app/models/proposal_version.py`  
  - `app/database/proposal_versions_repository.py`  
  - `app/api/routes/projects.py`  
  - `tests/unit/database/test_proposal_versions_repository.py`  
  - `tests/integration/test_proposal_versions.py` (new file)  
- **Classes/Interfaces**:  
  - `ProposalVersion` (Pydantic model)  
  - `ProposalVersionsRepository`  
  - `update_project` (API endpoint)  
- **Configuration**:  
  - MongoDB schema for `proposal_versions` collection  

## Task List
- [x] Read `app/models/proposal_version.py` to understand the `ProposalVersion` Pydantic model, then modify it to include a new field `source_of_changes: Optional[str] = Field(None, description="Source of changes: 'IA' or 'HUMAN'")` to ensure MongoDB documents can store this value.  
- [x] Examine `app/database/proposal_versions_repository.py` and modify the `insert_version` method to include `source_of_changes="IA"` in the `doc` dictionary when inserting a new proposal version.  
- [x] Add a new method `update_source_of_changes` to `ProposalVersionsRepository` that updates the `source_of_changes` field to "HUMAN" for the latest version of a given `project_id`. This method should query the latest version using `get_latest_version`, update its `source_of_changes` field, and save the change.  
- [x] Read `app/api/routes/projects.py` and modify the `update_project` function to call `update_source_of_changes` on `ProposalVersionsRepository` with `source_of_changes="HUMAN"` after successfully updating the project.  
- [x] Create a new file `tests/integration/test_proposal_versions.py` and write integration tests to verify that:  
  - `source_of_changes` is set to "IA" when a proposal is inserted via the Telegram bot.  
  - `source_of_changes` is set to "HUMAN" when a project is updated through the API.  
- [x] Examine `tests/unit/database/test_proposal_versions_repository.py` and add unit tests for the new `insert_version` logic (verifying "IA" is set) and the new `update_source_of_changes` method (verifying "HUMAN" is set).  
- [x] Ensure all test files use `pytest.mark.asyncio` and include proper mocks for database interactions, adhering to the project's test structure and type hinting requirements.  

## End Task List