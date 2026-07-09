## Current Objective
Update the refine_proposal endpoint to support an optional `contract_type` field with validation and logic to handle contract type changes by discarding previous proposal history and using initial proposal templates.

## Key Artifacts (to focus on)
- **Files**: 
  - `app/api/routes/proposals.py`
  - `app/models/project.py`
  - `app/database/proposal_versions_repository.py`
  - `app/intelligence/factory.py`
- **Classes/Interfaces**: 
  - `RefineProposalRequest`
  - `ProposalVersionsRepository`
  - `IntelligencePort`
  - `Project`
- **Configuration**: None

## Task List
- [ ] Read `app/api/routes/proposals.py` to understand the existing `RefineProposalRequest` model and `refine_proposal` endpoint logic, then modify the `RefineProposalRequest` class to add an optional `contract_type` field with validation for allowed values `"project_fixed"` and `"staff_augmentation"` (raising an error if unsupported). Update the `refine_proposal` function to check if the provided `contract_type` differs from the project's existing field; if it differs, delete all existing proposal versions using `ProposalVersionsRepository` and always call `refine_proposal_intel` passing the new `contract_type`.
- [ ] Examine `app/models/project.py` to confirm the `contract_type` field exists as a `ContractType` Literal, ensuring validation compatibility with the API route.
- [ ] Read `app/database/proposal_versions_repository.py` to understand how proposal versions are stored, then add a new method `delete_versions_for_project` to this class that deletes all proposal versions for a given `project_id` using MongoDB's `delete_many` operation.
- [ ] Examine `app/intelligence/factory.py` and implement a `select_initial_proposal_template` function that returns `proposal.j2` for "project_fixed" or `proposal_staffing.j2` for "staff_augmentation". Modify `refine_proposal_intel` to apply the following conditional template logic:
  1. If `contract_type` has changed, bypass the refinement templates and use the new template selector to load the correct initial template instead (rendering `proposal_staffing.j2` if switching to "staff_augmentation").
  2. If `contract_type` is missing or has not changed, proceed with the standard refinement process: use the existing refinement template (`refine.j2`) for `"project_fixed"`, and implement the new staffing refinement branch using `app/intelligence/prompts/refine-staffing.j2` when the contract type is `"staff_augmentation"`.
- [ ] **Run and improve Unit Tests:** Review existing unit tests for the factory and repository layers. Add or upgrade test cases to verify the `select_initial_proposal_template` logic, the conditional template routing inside `refine_proposal_intel`, and the correct behavior of `delete_versions_for_project` in the repository.
- [ ] **Run and improve Integration Tests:** Review and run API integration tests for the proposal endpoints. Add test cases to cover the full workflow of the updated `POST /api/proposals/{project_id}/refine` endpoint, verifying validation errors for invalid contract types, successful workflow resets when `contract_type` changes, and proper template generation for the new staffing refinement branch using `refine-staffing.j2`.

## End Task List