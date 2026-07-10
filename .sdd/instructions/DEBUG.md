## Current Objective
Resolve the issue where the `proposal_data` field in the `proposal_versions` collection remains empty after refining a proposal via the `/api/proposals/{project_id}/refine` endpoint.

## Task List
- [x] **Error in app/api/routes/proposals.py:78**
  - **Error:** `KeyError: 'proposal'`
  - **Context:** The code attempts to extract `inner_proposal` using `refined.pop("proposal", refined)`, but the LLM response lacks the expected `proposal` key, leading to an empty `proposal_data` in the database.
  - **Action Required:** 
    1. Inspect the `refine.j2` template in `app/intelligence/prompts/` to ensure it explicitly instructs the LLM to return a `proposal` object with the required structure.
    2. Validate that the LLM response includes a `proposal` key with valid content before attempting to extract it.
    3. Add error handling in `refine_proposal` to log or raise an exception if the `proposal` key is missing, preventing empty `proposal_data` from being stored.

- [x] **Error in app/database/proposal_versions_repository.py:42**
  - **Error:** `InvalidDocument: Document must contain a field: 'proposal_data'`
  - **Context:** The `insert_version` method requires `proposal_data` to be present, but the refinement process produces an empty dictionary due to the missing `proposal` key in the LLM response.
  - **Action Required:** 
    1. Modify the `insert_version` method to include validation that `proposal_data` is non-empty before attempting to insert into the database.
    2. Ensure that the `refine_proposal_intel` function guarantees the presence of `proposal_data` by enforcing the LLM to return structured content, potentially by adjusting the prompt template or adding fallback logic.