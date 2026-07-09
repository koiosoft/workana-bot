# Intelligence Layer Technical Specification

## 1. Ports and Adapters Architecture

### MongoDB-Driven Configuration

```text
[Client Service] --> (IntelligencePort) 
                          |
                          v
                [Adapter Factory]
                          |
                          v
               [DB: models.collection] --> [GeminiAdapter or OpenRouterAdapter]
```

**Key Characteristics**:
- Model configuration loaded from `models` MongoDB collection
- Provider resolution via `provider_key` field in model docs
- Automatic adapter instantiation based on model metadata

## 2. Port Specification

### Database-Driven Contracts
- **Model Defaults**: Stored in `models` collection with `is_default` flag
- **Provider Mapping**:
  ```json
  {
    "model_id": "models/gemini-2.5-flash",
    "provider_key": "gemini",
    "is_default": true,
    "is_premium": false
  }
  ```

### Interface Methods
```python
async def evaluate_projects()
async def generate_proposal()
async def refine_proposal()
async def format_project_description()
```

## 3. Adapter Framework Analysis

### Model Resolution Logic

```python
# From factory.py
standard_info, premium_info = await get_default_models_from_db()
instances['STANDARD'] = _create_adapter(standard_info.provider_key, standard_info.model_id)
```

**MongoDB Dependencies**:
- `is_default`: Designates standard/premium model
- `provider_key`: "gemini" or "openrouter"
- `model_id`: Provider-specific model identifier

### Adapter Instantiation
- Uses environment variables for API keys:
  - GEMINI_API_KEY
  - OPENROUTER_API_KEY
- Falls back to Gemini defaults on DB errors

## 4. Factory Logic

### Database Query Flow

```mermaid
graph TD
    A[get_intelligence_service()] --> B[Query models.collection]
    B --> C{DB Available?}
    C -->|Yes| D[Resolve provider_key/model_id]
    C -->|No| E[Use Gemini defaults]
    D --> F[Create adapter for provider_key]
    E --> F
```

### Fallback Mechanism
- On DB failure: Uses hardcoded Gemini models
- Explicit fallback in documentation:
  ```python
  # Fallback to Gemini defaults
  standard_info = ModelInfo(model_id="", provider_key="gemini")
  ```

## 5. Execution Flow with MongoDB

```mermaid
graph TD
    A[Client] --> B{get_intelligence_service()}
    B --> C[Query models.collection]
    C --> D[Resolve provider_key]
    D --> E[Create Gemini/OpenRouter Adapter]
    E --> F[Jinja2 Template Rendering]
    F --> G[LLM API Call]
    G --> H[Database-Driven Model Config]
    H --> I[Response Validation]
    I --> J[Port Interface Return]
```

**Critical Database Relationships**:
1. `models.collection` → defines model defaults
2. `provider_key` → maps to specific adapter class
3. `is_premium` → determines pricing tier handling

## 6. Environmental Configuration

### Required Secrets
- GEMINI_API_KEY: For Google Cloud API access
- OPENROUTER_API_KEY: For OpenRouter endpoint routing
- GEMINI_DELAY_OVERRIDE (optional): Model-specific delay control

### Connection Behavior
- Adapter initialization will fail without configured API keys
- Factory provides fallback only for model resolution, not API credential errors