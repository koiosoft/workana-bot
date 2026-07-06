## Current Objective
Create and manage AI model provider collections, implement API endpoints for model and provider data, and ensure test coverage for new functionality.

## Key Artifacts (to focus on)
- **Files**: 
  - `app/models/provider.py` (new file)
  - `app/models/model.py` (new file)
  - `app/database/mongo.py`
  - `app/api/routes/models.py` (new file)
  - `app/intelligence/factory.py` (if exists, otherwise create)
  - `tests/unit/models/test_provider.py` (new file)
  - `tests/unit/models/test_model.py` (new file)
  - `tests/integration/test_models_endpoints.py` (new file)
  - `migrations/0002_initial_models.py` (new migration file)
- **Classes/Interfaces**: 
  - `ProviderModel` (Pydantic model)
  - `ModelModel` (Pydantic model with validation rules)
  - `ProvidersRepository` (MongoDB repository class)
  - `ModelsRepository` (MongoDB repository class)
  - `get_model_by_id` (API endpoint function)
  - `list_providers` (API endpoint function)
  - `list_models` (API endpoint function)
- **Configuration**: 
  - `MONGO_URI` environment variable
  - `AUTH_SECRET` environment variable (for test authentication)

## Task List
- [x] Create `app/models/provider.py` defining a `ProviderModel` Pydantic class with fields `key`, `name`, and `url`, then modify `app/database/mongo.py` to add a `providers` collection with schema validation for these fields. Fields: key (text field, required), name (text field, required), url  (text field, required).
- [x] Create `app/models/model.py` defining a `ModelModel` Pydantic class with fields `model_id`, `provider_key`, `is_default`, and `is_premium`, including validation rules to enforce no more than 2 default models, exactly 1 default premium model, and exactly 1 default standard model, then modify `app/database/mongo.py` to add a `models` collection with schema validation for these rules. Fields: model_id (text field, required), provider_key (text field, required), is_default(boolean field, required), and is_premium (bolean field, required)
- [x] Read `app/intelligence/adapters/openrouter.py` and `app/intelligence/adapters/gemini.py` to extract `STANDARD_MODEL` and `PREMIUM_MODEL` values, then create `migrations/0002_initial_models.py` to insert these models into the `models` collection with `is_default: true` for OpenRouter's standard model and `is_default: true` for its premium model, ensuring the constraints of exactly 1 default standard and 1 default premium model are met.
- [x] Create `app/api/routes/models.py` and implement the following endpoints:
  - `list_providers`: Query the `providers` collection and return a list of provider objects.
  - `list_models`: Include a `filter` query parameter to return standard or premium models (with default indicators) by joining with the `providers` collection for brand names.
- [x] Create `tests/unit/models/test_provider.py` with unit tests for `ProviderModel` validation rules, including tests for required fields and format constraints.
- [x] Modify `app/intelligence/factory.py` (or create if missing) to include logic for selecting models based on the `models` collection's default flags, ensuring the factory uses the correct default standard and premium models from the database rather than hardcoded values in adapters.
- [x] Create `tests/unit/models/test_model.py` with unit tests for `ModelModel` validation rules, including tests for the exact constraints on default models (max 2 defaults, exactly 1 default premium, exactly 1 default standard).
- [x] Create `tests/integration/test_models_endpoints.py` with integration tests for the `list_providers` and `list_models` endpoints, including tests for unauthorized access and valid/invalid filter parameters.
- [x] Add `pytest` test cases to `tests/unit/intelligence/test_adapters.py` to validate that `OpenRouterAdapter` and other adapters use model IDs from the `models` collection rather than hardcoded values, ensuring proper integration with the new model management system.

## End Task List