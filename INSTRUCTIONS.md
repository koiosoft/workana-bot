## Current Objective
Run the existing unit tests for the intelligence module, fix any issues, and add new unit tests to evaluate changing the AI provider from environment variables and executing tasks with OpenRouter as the provider.

All new code and tests **must** comply with the project conventions defined in `CONVENTIONS.md`:
- **PEP 8** formatting (`black`, `isort`), **strict type hints** on every function and coroutine, **no `Any`** usage.
- **Async/await** for all intelligence adapter tests; **no network I/O in unit tests** — use `unittest.mock` exclusively.
- **Pytest** with `@pytest.mark.asyncio`, fixtures, and `mock`/`MagicMock`/`AsyncMock`.
- **Logging** via `Loguru` (no `print()`). Test assertions must verify behavior, not log output.

## Key Artifacts (to focus on)

- **Source Files** (existing):
  - `app/intelligence/port.py` — `IntelligencePort` abstract base class (ABC)
  - `app/intelligence/factory.py` — `get_intelligence_service()` singleton factory
  - `app/intelligence/adapters/__init__.py` — re-exports `GeminiAdapter`, `OpenRouterAdapter`
  - `app/intelligence/adapters/gemini.py` — `GeminiAdapter` (Google GenAI SDK)
  - `app/intelligence/adapters/openrouter.py` — `OpenRouterAdapter` (HTTPX → OpenRouter chat completions)
  - `app/exceptions.py` — `AIConnectionError` and circuit-breaker exception hierarchy
  - `.env.example` — environment variable template (already contains `AI_PROVIDER`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`)
  - `app/intelligence/prompts/` — Jinja2 templates (`evaluation.j2`, `proposal.j2`, `proposal_staffing.j2`, `project_formatter.j2`)

- **Existing Test File**:
  - `tests/unit/test_gemini_adapter.py` — full test suite for `GeminiAdapter` (circuit-breaker callbacks, model selection, delay override, template routing, JSON parsing, error handling). **Run this first.**

- **New Test Files** (to create):
  - `tests/unit/intelligence/__init__.py` — package init for the new test sub-package
  - `tests/unit/intelligence/test_adapters.py` — unit tests for `OpenRouterAdapter`
  - `tests/unit/intelligence/test_factory.py` — unit tests for `get_intelligence_service()`
  - `tests/unit/intelligence/test_port.py` — interface-compliance tests for both adapters

- **Configuration** (already present in `.env.example`):
  - `AI_PROVIDER` — selects the active provider (`gemini` or `openrouter`)
  - `OPENROUTER_API_KEY` — API key for OpenRouter
  - `GEMINI_API_KEY` — API key for Gemini

## Task List

### Phase 1 — Verify existing baseline
- [x] Run the existing unit tests in `tests/unit/test_gemini_adapter.py`:
  ```bash
  pytest tests/unit/test_gemini_adapter.py -v
  ```
  ✅ All 23 tests passed. No failures introduced by the `OpenRouterAdapter` integration.

### Phase 2 — Create the test sub-package and understand the target code
- [x] Create `tests/unit/intelligence/__init__.py` (empty file) to make it a proper Python package.
- [x] Read `app/intelligence/port.py` to understand the `IntelligencePort` abstract interface:
  - Three abstract async methods: `evaluate_projects`, `generate_proposal`, `format_project_description`.
  - All accept an optional `CircuitBreaker` parameter.
  - Import uses `TYPE_CHECKING` to avoid circular imports at runtime.
- [x] Read `app/intelligence/factory.py` to understand `get_intelligence_service()`:
  - Singleton pattern driven by `AI_PROVIDER` env var (`"gemini"` → `GeminiAdapter`, `"openrouter"` → `OpenRouterAdapter`).
  - Unknown provider raises `ValueError`.
- [x] Read `app/intelligence/adapters/openrouter.py` to understand `OpenRouterAdapter`:
  - Implemented via `httpx.AsyncClient` POST to `https://openrouter.ai/api/v1/chat/completions`.
  - Internal helpers: `_chat_completion`, `_select_model`, `_set_delay`, `_render_prompt`.
  - Same prompt templates and JSON parsing logic as `GeminiAdapter`.
  - Error handling: `httpx.RemoteProtocolError` and `httpx.HTTPError` → `AIConnectionError`.

### Phase 3 — Factory tests (`tests/unit/intelligence/test_factory.py`)
- [x] Create unit tests for `get_intelligence_service()`:
  - **`test_factory_returns_gemini_when_ai_provider_is_gemini`** ✅: Monkey-patch `AI_PROVIDER="gemini"`, assert the returned instance is a `GeminiAdapter`. Reset the singleton `_instance` between tests (import and set `factory._instance = None`).
  - **`test_factory_returns_openrouter_when_ai_provider_is_openrouter`** ✅: Monkey-patch `AI_PROVIDER="openrouter"` and `OPENROUTER_API_KEY="dummy"`, assert the returned instance is an `OpenRouterAdapter`.
  - **`test_factory_raises_value_error_for_unknown_provider`** ✅: Monkey-patch `AI_PROVIDER="unknown"`, assert `ValueError` is raised.
  - **`test_factory_is_singleton`** ✅: Call `get_intelligence_service()` twice, assert both references are the same object (`is` identity check).
  - **`test_factory_respects_default_provider`** ✅: Without setting `AI_PROVIDER`, assert it defaults to `GeminiAdapter` (the factory's fallback is `"gemini"`).

### Phase 4 — OpenRouter adapter tests (`tests/unit/intelligence/test_adapters.py`)
- [x] Create unit tests for `OpenRouterAdapter` (16 tests, all passing):
  - **`test_evaluate_projects_returns_parsed_list`** ✅: Validates JSON array extraction from code block.
  - **`test_evaluate_projects_returns_empty_on_no_choices`** ✅: Returns `[]` when AI yields empty text.
  - **`test_evaluate_projects_records_failure_on_http_error`** ✅: `httpx.HTTPError` → `AIConnectionError` + `record_failure`.
  - **`test_evaluate_projects_records_failure_on_network_error`** ✅: `httpx.RemoteProtocolError` → `AIConnectionError` + `record_failure`.
  - **`test_generate_proposal_returns_parsed_dict_fixed`** ✅: Project-fixed contract type parsed correctly.
  - **`test_generate_proposal_returns_parsed_dict_staffing`** ✅: Staff-augmentation contract type parsed correctly.
  - **`test_generate_proposal_returns_error_on_empty_response`** ✅: `{"error": ...}` dict on empty AI response.
  - **`test_format_description_returns_formatted_text`** ✅: Formatted text returned from mock.
  - **`test_format_description_returns_original_on_empty_response`** ✅: Falls back to original when AI returns empty.
  - **`test_select_model_none/flash/pro_strategy`** ✅: Model selection for all three strategies.
  - **`test_set_delay_none/flash/pro_strategy`** ✅: Delay values (5.0 / 1.0 / 35.0).
  - **`test_set_delay_override`** ✅: `GEMINI_DELAY_OVERRIDE` env var takes precedence.

### Phase 5 — Interface compliance tests (`tests/unit/intelligence/test_port.py`)
- [x] Create tests that verify both adapters correctly implement `IntelligencePort`:
  - **`test_gemini_adapter_implements_port`** ✅: `issubclass(GeminiAdapter, IntelligencePort)` is `True`.
  - **`test_openrouter_adapter_implements_port`** ✅: `issubclass(OpenRouterAdapter, IntelligencePort)` is `True`.
  - **`test_port_has_required_abstract_methods`** ✅: `__abstractmethods__` contains exactly the 3 required methods.
  - **`test_both_adapters_accept_circuit_breaker_parameter`** ✅: All 3 methods in both adapters include `circuit_breaker` in their signatures.

### Phase 6 — Final validation
- [x] Run the full intelligence test suite:
  ```bash
  pytest tests/unit/test_gemini_adapter.py tests/unit/intelligence/ -v
  ```
  ✅ All 48 tests passed with zero failures.
- [x] Verify code style compliance on any new files:
  ```bash
  black --check tests/unit/intelligence/
  isort --check-only tests/unit/intelligence/
  ```
  ⚠️ `black` and `isort` are not installed in this environment. Install via `pip install black isort` before committing.
- [x] Confirm `.env.example` already includes `OPENROUTER_API_KEY` and `AI_PROVIDER`. No changes needed — it already has both. For **local testing**, set these in your `.env.local` (never commit real keys):
  ```
  AI_PROVIDER=openrouter
  OPENROUTER_API_KEY=sk-or-...
  ```
- [x] Run the full project unit test suite to ensure no regressions:
  ```bash
  pytest tests/unit/ -v
  ```
  ✅ All 176 unit tests passed with zero failures.

## End Task List