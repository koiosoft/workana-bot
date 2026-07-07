## Current Objective
Resolve the test failures in the `test_adapters.py` and `test_gemini_adapter.py` files related to model selection and configuration in the AI adapter implementations.

## Task List
- [x] **Error in tests/unit/intelligence/test_adapters.py:299**
  - **Error:** AssertionError: assert 'qwen/qwen3-14b' == 'db-default'
  - **Context:** The `_select_model` method in `OpenRouterAdapter` is not using the expected model override when the strategy is set to 'none'.
  - **Action Required:** Inspect the `_select_model` method in the `OpenRouterAdapter` class to verify how it selects the model when the strategy is 'none'. Ensure that it correctly falls back to the `_standard_model_override` if provided. If the fallback logic is incorrect, adjust the method to use the overridden model as expected during testing.

- [x] **Error in tests/unit/intelligence/test_gemini_adapter.py:151**
  - **Error:** AssertionError: assert 'models/gemma-4-31b-it' == 'models/gemini-2.5-flash'
  - **Context:** The `format_project_description` method in `GeminiAdapter` is using an incorrect model when the default strategy is applied.
  - **Action Required:** Review the `set_gemini_model` method in the `GeminiAdapter` class to confirm that it correctly selects the `STANDARD_MODEL` when the strategy is not explicitly set. Ensure that the model ID used for formatting is consistent with the `STANDARD_MODEL` constant, and that any overrides or defaults are applied correctly during the method's execution.