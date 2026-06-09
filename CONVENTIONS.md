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

## 3. ARCHITECTURAL BOUNDARIES & CODESPACE ISOLATION

*   **Pure Application Core:** The application's core domain logic must remain pure and isolated. It must not contain any imports from infrastructure-specific libraries (e.g., `motor`, `playwright`, `beautifulsoup4`, `telegram`). The core should only depend on pure Python types, Pydantic models, and the abstract ports it defines.
*   **Abstract Ports:** Inbound and Outbound Ports must be defined as abstract base classes (`abc.ABC`) with `@abc.abstractmethod` decorators. These ports form the strict, technology-agnostic contracts that the application core uses to interact with the outside world.
*   **Adapter Encapsulation:** Driven Adapters (e.g., for the database or scraper) are responsible for implementing the contracts defined by the ports. They must completely encapsulate all infrastructure-specific details and error handling. For instance, a Playwright adapter must catch exceptions like `TimeoutError` and translate them into domain-specific exceptions defined by the port, or return a Pydantic model with `None` values. Data returned from an adapter to the core must *always* be a primitive Python type or a domain Pydantic model.

## 4. DEFENSIVE WEB PARSING & ERROR HANDLING

*   **Defensive Parsing:** Code that interacts with HTML/XML must never assume the existence of an element. Always use non-failing methods (e.g., `soup.find()`) and perform an explicit `if element:` check before attempting to access its attributes (e.g., `.text`, `['href']`). This prevents `AttributeError` exceptions from crashing the parsing process.
*   **No Silent Failures:** Empty `except:` or `except Exception: pass` blocks are strictly forbidden. All exceptions must be caught specifically (e.g., `except KeyError:`) and handled deliberately, which includes logging them with appropriate context and severity.
*   **Resilience Wrappers:** All external I/O calls, including network requests for scraping and calls to the Gemini API, must be wrapped in a resilience pattern. This is typically handled by application-level services that implement Circuit Breakers or exponential backoff retry logic to gracefully manage transient failures.

## 5. RECOVERY WORKFLOWS & LOGGING STATE

*   **Loguru as Standard:** `Loguru` is the sole logging engine for the application. The use of `print()` is prohibited in all application modules; it is only permissible in auxiliary developer scripts inside `scripts/`.
*   **Rigorous Log Levels:**
    *   `INFO`: For tracing key lifecycle events and successful state transitions (e.g., "Bot initialized," "Processing 5 new projects," "Proposal sent successfully").
    *   `WARNING`: For handled, recoverable anomalies that do not disrupt a workflow but are noteworthy (e.g., "Project URL returned a 404, skipping," "Retrying Gemini API call, 2/3").
    *   `ERROR`: For failures within a specific workflow that prevent its completion but do not compromise the entire application (e.g., "Failed to parse project after 3 retries," "Database write failed for project_id=123").
    *   `CRITICAL`: For system-wide, unrecoverable failures requiring immediate human intervention. When the scraper's session expires (`state.json` is invalid), it must log a `CRITICAL` error message instructing the operator to run `scripts/extract_session.py` and then gracefully terminate the affected task.

## 6. TESTING STRATEGY IMPLEMENTATION (TEST-DRIVEN DEVELOPMENT)

*   **Pytest Framework:** All tests are written using the `pytest` framework and its ecosystem.
*   **Unit Tests (`tests/unit/`):** Must be fully isolated and self-contained. They must not perform any network I/O.
    *   Scraper parsing logic must be tested by passing locally stored HTML content from a `tests/fixtures/` directory.
    *   Application core services must be tested by providing mock implementations of the Ports they depend on.
*   **Integration Tests (`tests/integration/`):** Designed to test the "glue" between the application and real infrastructure (e.g., a database connection).
    *   These tests are permitted to connect to local services, such as a Dockerized MongoDB instance.
    *   They must be decorated with `@pytest.mark.skipif(not os.getenv("MONGO_URI"), reason="MONGO_URI not set")` to ensure they are automatically skipped in environments where the required services are not available.
