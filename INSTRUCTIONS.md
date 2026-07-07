## Current Objective
Refactor the AI adapter selection mechanism to retrieve STANDARD, PREMIUM, and FILTER adapters from MongoDB based on `is_default: True` models, replacing the current environment variable-based approach.

## Key Artifacts (to focus on)
- **Files**:  
  - `app/intelligence/factory.py`  
  - `app/intelligence/adapters/openrouter.py`  
  - `app/intelligence/adapters/gemini.py`  
  - `app/bots/telegram/handlers.py`  
  - `tests/integration/intelligence/test_factory.py`  
  - `tests/unit/intelligence/test_factory.py`  
  - `app/models/models.py`  
  - `app/models/provider.py`  
- **Classes/Interfaces**:  
  - `IntelligencePort` (from `app/intelligence/port.py`)  
  - `OpenRouterAdapter`, `GeminiAdapter` (from `app/intelligence/adapters/`)  
  - `get_intelligence_service`, `create_intelligence_service` (from `app/intelligence/factory.py`)  
  - `Model` (from `app/models/models.py`)  
- **Configuration**:  
  - `AI_PROVIDER` environment variable  
  - `MONGO_URI` for database access  

## Task List
- [x] Read `app/intelligence/factory.py` to:
    - Understand `get_intelligence_service` and `create_intelligence_service` logic.
    - Modify `get_intelligence_service` to delegate to `create_intelligence_service` and remove environment variable dependency.
    - Ensure the three adapters are retrieved from MongoDB via `is_default: True` models and passed to downstream components.
- [x] Examine `app/intelligence/adapters/openrouter.py` and `app/intelligence/adapters/gemini.py` to:
    - Confirm `standard_model` and `premium_model` parameters override hardcoded IDs.
    - Add `filter_model` initialization in `create_intelligence_service` using database-retrieved IDs.
    - Ensure all three adapters are uniquely instantiated and injected into service objects.
- [x] Modify `app/bots/telegram/handlers.py` to:
    - Replace `get_intelligence_service()` with `create_intelligence_service()` to retrieve all three adapters.
    - Add user-tier-based logic to select between STANDARD, PREMIUM, and FILTER adapters.
    - Ensure adapter instances are used explicitly in `process_projects` logic for their respective use cases.
- [x] Update `app/intelligence/factory.py` to:
    - Enhance `get_default_models_from_db` to raise descriptive errors for missing default models.
    - Ensure `create_intelligence_service` returns a dictionary of adapters: `{STANDARD: ..., PREMIUM: ..., FILTER: ...}`.
    - Default to hardcoded values only if MongoDB is unavailable, preserving adapter isolation.
- [x] Examine `tests/unit/intelligence/test_factory.py` to:
    - Mock MongoDB queries for `get_default_models_from_db`.
    - Verify STANDARD, PREMIUM, and FILTER adapters are correctly instantiated with database models.
    - Add assertions to check adapter `is_default` and `is_premium` flags align with database records.
- [x] Review `tests/integration/intelligence/test_factory.py` to:
    - Add tests for database edge cases (missing default models, multiple default models).
    - Verify `create_intelligence_service` raises correct errors and uses hardcoded fallbacks.
    - Ensure integration tests validate all three adapters are instantiated in normal/edge cases.
- [x] Ensure `app/models/models.py` and `app/models/provider.py` are referenced in `get_default_models_from_db` to:
    - Correctly query the `models` collection for `is_default: True` entries.
    - Distinguish between STANDARD (is_premium: False) and PREMIUM (is_premium: True) models.
    - Exclude FILTER models from `is_premium` checks if they are non-transactional.

## End Task List