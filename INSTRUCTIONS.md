# Integration Instructions: OpenRouter AI Provider

## 1. Implementation Goals

- Add OpenRouter as an alternative AI model provider alongside Gemini
- Enable seamless provider switching through configuration
- Maintain strict adherence to project conventions and architecture

## 2. Key Implementation Steps

### 2.1 File Structure Updates

**Files to modify:**
- `app/intelligence/adapters/openrouter.py` (Pending creation)
- `app/intelligence/adapters/__init__.py` (Pending update)
- `app/intelligence/factory.py` (Pending update)
- `.env.example` (Pending update)

### 2.2 Class/Interface Implementation

**Core Interfaces:**
- `IntelligencePort` (from `app/intelligence/port.py`) (Pending implementation in OpenrRouterAdapter)

**Adapter Implementation:**
- `OpenRouterAdapter` in `app/intelligence/adapters/openrouter.py`:
  - Uses async HTTP client (`httpx`) for API calls 
  - Implements all required methods from `IntelligencePort` 
  - Includes proper error handling and logging 
  - Uses Pydantic models for data processing 

### 2.3 Configuration Changes

**Environment Variables:**
- `AI_PROVIDER` (default: "gemini") (Pending add to .env.example)
- `OPENROUTER_API_KEY` (Pending add to .env.example)

**Supported Providers:**
- "gemini" (default)
- "openrouter" (new)

### 2.4 Architecture Compliance

- Follows Hexagonal Architecture pattern  
- Maintains separation between core logic and adapters 
- Uses proper naming conventions:
  - `PascalCase` for classes (`OpenRouterAdapter`) 
  - `snake_case` for functions/methods 
  - `UPPER_SNAKE_CASE` for constants 

## 3. Implementation Checklist

[x] ✅ Create `app/intelligence/adapters/openrouter.py` with proper implementation
[x] ✅ Update `app/intelligence/adapters/__init__.py` to include new adapter
[x] ✅ Modify `app/intelligence/factory.py` to support 'openrouter' provider
[x] ✅ Add `OPENROUTER_API_KEY` to `.env.example`
[x] ✅ Set `AI_PROVIDER` to 'openrouter' for testing
[x] ✅ Refactor direct AI model instantiations to use `get_intelligence_service()`

## 4. Quality Assurance

- [ ] ✅ PEP8 compliance validation
- [ ] ✅ Type hinting verification
- [ ] ✅ Async I/O usage confirmation
- [ ] ✅ Proper resource management with async context managers
- [ ] ✅ Logging level validation (INFO, WARNING, ERROR, CRITICAL)
- [ ] ✅ Test coverage verification