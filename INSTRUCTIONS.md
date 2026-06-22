## Current Objective
Integrate OpenRouter as an alternative AI model provider alongside GEMINI, ensuring that the application can seamlessly switch between the two providers using configuration.

## Key Artifacts (to focus on)
- **Files**:
  - `app/intelligence/port.py`
  - `app/intelligence/adapters/gemini.py`
  - `app/intelligence/adapters/__init__.py`
  - `app/intelligence/factory.py`
  - `app/intelligence/adapters/openrouter.py` (new file)
  - `.env` (or equivalent configuration file)
- **Classes/Interfaces**:
  - `IntelligencePort` (from `app/intelligence/port.py`)
  - `GeminiAdapter` (from `app/intelligence/adapters/gemini.py`)
  - `OpenRouterAdapter` (to be created in `app/intelligence/adapters/openrouter.py`)
- **Configuration**:
  - `AI_PROVIDER` (environment variable to specify the AI provider)
  - `OPENROUTER_API_KEY` (environment variable for OpenRouter API key)

## Task List
- [ ] Read `app/intelligence/port.py` to understand the `IntelligencePort` interface, then create `app/intelligence/adapters/openrouter.py` with an `OpenRouterAdapter` class that implements the `IntelligencePort` interface.
- [ ] Examine `app/intelligence/adapters/gemini.py` to understand how the `GeminiAdapter` class is structured and interacts with the `IntelligencePort` interface, then implement similar functionality in the `OpenRouterAdapter` class.
- [ ] Modify `app/intelligence/adapters/__init__.py` to include the new `OpenRouterAdapter` class.
- [ ] Examine `app/intelligence/factory.py` and modify the `get_intelligence_service` function to include the 'openrouter' provider, ensuring that the correct adapter is instantiated based on the `AI_PROVIDER` environment variable.
- [ ] Update the `.env` file to include the `OPENROUTER_API_KEY` environment variable and set the `AI_PROVIDER` environment variable to 'openrouter' for testing.
- [ ] Refactor any parts of the application that directly instantiate AI models to use the `get_intelligence_service` function from `app/intelligence/factory.py` to obtain the appropriate adapter based on the configured model.

## End Task List