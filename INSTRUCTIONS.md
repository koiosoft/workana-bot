## Current Objective
Implement REST endpoints for managing Model Providers and Models (LLMs), including endpoints for setting default and premium models, along with corresponding unit and integration tests.

## Key Artifacts (to focus on)
- **Files**:
  - `app/api/routes/models.py` (new file to create)
  - `tests/unit/api/test_models.py` (new file to create)
  - `tests/integration/test_models_integration.py` (new file to create)
- **Classes/Interfaces**:
  - `ModelProvider` (Pydantic model)
  - `Model` (Pydantic model)
  - `ModelsRouter` (FastAPI router)
- **Configuration**:
  - Environment variables related to MongoDB connection
  - `MONGO_URI` for integration tests

## Task List
- [x] Read `app/api/main.py` to understand the existing FastAPI setup, then create `app/api/routes/models.py`.
- [x] Define `POST /providers` endpoint in `ModelsRouter` for creating Model Providers with validation against `ModelProvider` Pydantic model.
- [x] Define `POST /models` endpoint in `ModelsRouter` for creating Models (LLMs) with validation against `Model` Pydantic model.
- [x] Create `tests/unit/api/test_models.py` and implement unit tests for `POST /providers` and `POST /models` endpoints.
- [x] Create `tests/integration/test_models_integration.py` and implement integration tests for `POST` endpoints with MongoDB interaction via `MONGO_URI`.
- [x] Define `PUT /providers/{provider_id}` endpoint in `ModelsRouter` for updating Model Providers (name, description, etc.)
- [x] Define `PUT /models/{model_id}` endpoint in `ModelsRouter` to update Model flags: set `is_default` and `is_premium` while ensuring mutual exclusion with existing defaults/premium models.
- [x] Extend `tests/unit/api/test_models.py` to include unit tests for `PUT` endpoints, validating input types and business logic.
- [x] Extend `tests/integration/test_models_integration.py` to include integration tests for `PUT` endpoints with database state validation.
- [x] Define `DELETE /providers/{provider_id}` endpoint in `ModelsRouter` for soft-deleting Model Providers (add `is_deleted` flag and cascade to associated models)
- [x] Define `DELETE /models/{model_id}` endpoint in `ModelsRouter` for soft-deleting Models while preserving historical usage records.
- [x] Extend `tests/unit/api/test_models.py` to include unit tests for `DELETE` endpoints with validation of deletion constraints.
- [x] Extend `tests/integration/test_models_integration.py` to include integration tests for `DELETE` endpoints with database state validation.
- [x] Examine `app/models/provider.py` and create `ModelProvider` Pydantic model in `app/models/models.py` with required fields: id, name, description, created_at, updated_at.
- [x] Examine `app/models/project.py` and create `Model` Pydantic model in `app/models/models.py` with required fields: id, provider_id, name, is_default, is_premium, created_at, updated_at.
- [x] Ensure all files adhere to PEP 8, use strict type hints, and include `pytest.mark.asyncio` for async tests with no network I/O in unit tests and proper Loguru logging.

## End Task List