# Workana Bot - Automated Proposal Generator

## 🛠 Features
- **AI Provider Flexibility**  
  Now supports both Gemini and OpenRouter as AI providers via `AI_PROVIDER` env var.
- **Resilient Automation Architecture**
  - Hexagonal architecture with clear separation of concerns
  - Async/await throughout for non-blocking operations
  - Comprehensive test coverage with:
    - Unit tests in `tests/unit/` organized by domain (api, bots, database, intelligence, scraper)
    - Integration tests in `tests/integration/` with conditional execution based on `MONGO_URI`