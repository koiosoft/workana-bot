# DEVELOPMENT AND CODING CONVENTIONS - WORKANA BOT

## 1. PYTHON LANGUAGE STANDARDS & TYPING

*   **PEP 8 Compliance:** All code must strictly adhere to PEP 8 style guidelines. The project is configured to use `black` for automated code formatting and `isort` for import sorting. Developers must run these tools before committing changes.
*   **Strict Type Hinting:** Every function, method, and coroutine signature must include explicit type hints for all arguments and return values, using the `typing` module. This is non-negotiable for code clarity and static analysis.
*   **Pydantic for Data Modeling:** Pydantic models are the standard for defining data structures, especially at architectural boundaries. This includes data returned from scraper adapters, API responses, and any data structures passed to or from the application core.
*   **Prohibition of `Any`:** The use of `typing.Any` is forbidden. It defeats the purpose of a strictly-typed codebase. In cases where a generic type is required within an abstract port, use `typing.TypeVar` or `typing.Protocol` to define structural contracts.
*   **Naming Conventions:**
    *   `snake_case`: For all variables, functions, methods, and modules (e.g., `fetch_project_data`).
    *   `PascalCase`: For all classes, Pydantic models, and type definitions (e.g., `ProjectDetails`, `ScraperPort`).
    *   `UPPER_SNAKE_CASE`: For all constants (e.g., `MAX_RETRIES`, `DEFAULT_TIMEOUT`).

## 2. ASYNCHRONOUS PROGRAMMING (ASYNCIO) RULES

*   **Non-Blocking Event Loop:** The `asyncio` event loop must never be blocked by synchronous I/O or long-running CPU-bound tasks. All I/O operations within the main application must be asynchronous.
*   **Context-Specific Execution:**
    *   **Asynchronous (`async/await`):** Mandatory for all code within the `app/` directory, including bot interactions, database queries (`motor`), web scraping (`Playwright`), and external API calls (`google-genai`).
    *   **Synchronous:** Strictly limited to offline utility scripts and the database migration engine (`migrations/`), which uses `pymongo` for controlled, atomic schema changes.
*   **Guaranteed Resource Management:** All shared or exclusive resources, such as database connections, file handles, and especially concurrency controls like `asyncio.Semaphore`, must be managed using an asynchronous context manager (`async with`). This is a critical rule to guarantee resource release even in the event of unexpected exceptions, thus preventing deadlocks and cascading failures.

## 3. TEST STRUCTURE AND REQUIREMENTS

### 3.1 Directory Structure
- **Unit tests** are organized by domain in `tests/unit/`:
  ```
tests/unit/
  ├── api/
  │   └── test_projects.py
  ├── bots/
  │   ├── test_circuit_breaker.py
  │   ├── test_telegram_handlers.py
  │   └── test_messages.py
  ├── database/
  │   ├── test_projects_repository.py
  │   └── test_semaphore_unit.py
  ├── intelligence/
  │   ├── test_adapters.py
  │   ├── test_factory.py
  │   └── test_port.py
  └── scraper/
      └── test_workana_scraper.py
  ```
- **Integration tests** are located in `tests/integration/` and require `MONGO_URI` to be set (automatically skipped otherwise).

### 3.2 Test Requirements
- Strict type hints required on all test functions and fixtures
- `pytest.mark.asyncio` for async tests
- No network I/O in unit tests - use mocks exclusively
- `black` and `isort` for code formatting (listed in `requirements-dev.md`)
- `Loguru` for all logging in test files (no `print()` allowed)