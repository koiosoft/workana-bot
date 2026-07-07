## Current Objective
Decouple the `proposal` data from the `projects` collection to enable full version history, audit trails, and AI-driven refinements while maintaining backward compatibility with all existing API responses.

## Key Artifacts (to focus on)
- **Files**:  
  - `app/models/project.py` (current embedded proposal structure)  
  - `app/database/projects_repository.py` (project data access logic)  
  - `app/api/routes/projects.py` (GET /api/projects/{projectId} and paginated endpoints)  
  - `app/models/models.py` (Pydantic models for API responses)  
  - `tests/unit/database/test_projects_repository.py` (unit tests for repository logic)  
  - `tests/integration/test_projects.py` (integration tests for API endpoints)  
  - `app/database/mongo.py` (MongoDB connection and collection management)  
  - New file: `app/database/proposal_versions_repository.py`  
  - New file: `tests/unit/database/test_proposal_versions_repository.py`  

- **Classes/Interfaces**:  
  - `Project` (Pydantic model in `app/models/project.py`)  
  - `ProjectsRepository` (MongoDB access layer in `app/database/projects_repository.py`)  
  - `ProposalVersionsRepository` (new repository class)  
  - `IntelligencePort` (AI adapter interface in `app/intelligence/port.py`)  

- **Configuration**:  
  - MongoDB collection names (`projects`, `proposal_versions`)  
  - Environment variables for MongoDB connection (`MONGO_URI`)  

## Task List
- [x] Read `app/models/project.py` to analyze the structure of the `proposal` field, then create `app/models/proposal_version.py` containing `ProposalVersion` model that extends the proposal schema with version control fields: `version_number`, `project_id`, `refinement_log`, and `created_at`.  
- [x] Examine `app/database/projects_repository.py` and modify its `save_project` method to no longer store `proposal` data in the `projects` collection. Instead, create a new class `ProposalVersionsRepository` in `app/database/proposal_versions_repository.py` with methods to insert, query, and aggregate proposal versions.  
- [x] Modify `app/api/routes/projects.py` to update the `get_project` endpoint: query `proposal_versions` for the latest version matching `project_id`, sort by `version_number` descending, and populate the `proposal` field in the API response using the same structure as before.  
- [x] Update the paginated `list_projects` endpoint in `app/api/routes/projects.py` to implement a two-step query strategy: fetch project metadata, extract `project_ids`, and use MongoDB aggregation on `proposal_versions` to group by `project_id` and retain the latest version. Map results back to the project list.  
- [x] Modify `app/database/mongo.py` to add compound indexes on the `proposal_versions` collection: `(project_id, version_number)` and `(project_id)` for performance.  
- [x] Read `app/intelligence/adapters/gemini.py` to analyze its `generate_proposal` method implementation, then modify both `app/intelligence/adapters/gemini.py` and `app/intelligence/adapters/openrouter.py` to insert new proposal versions into `proposal_versions` collection with `version_number = MAX + 1` during refinements instead of updating embedded proposals.  
- [x] Create `app/migrations/migrate_proposals_to_versions.py` by reading `app/models/project.py` to extract proposal schema, then implement a script that: 1) Iterates projects collection; 2) Extracts embedded `proposal` field; 3) Transforms into `proposal_versions` documents with `version_number = 1` and null refinement/user fields; 4) Inserts into new collection.  
- [x] Read `app/database/proposal_versions_repository.py` to understand its API, then create `tests/unit/database/test_proposal_versions_repository.py` with unit tests for: 1) Insert operations 2) Latest version lookup 3) Aggregation queries 4) Index validation.  
- [x] Modify `tests/integration/test_projects.py` to add integration tests for the `GET /api/projects/{projectId}` and `GET /api/projects` endpoints, verifying that the `proposal` field is populated correctly from `proposal_versions` and handles missing versions gracefully.  
- [x] Read `app/database/mongo.py` to understand indexing strategy, then implement unit tests in `tests/unit/database/test_proposal_versions_repository.py` for: 1) Compound index validation 2) Query performance 3) Aggregation pipeline accuracy.  
- [x] Update `app/models/models.py` to ensure that the `ProposalVersion` model aligns with the API response structure, maintaining backward compatibility with existing frontend code.  

## End Task List