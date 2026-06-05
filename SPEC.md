# SOFTWARE DESIGN DOCUMENT (SDD) - WORKANA BOT

## 1. SYSTEM OBJECTIVE

### 1.1 Purpose Statement
The primary objective of **Workana Bot** is to comprehensively and resiliently automate the prospecting lifecycle on the Workana platform. This includes the uninterrupted discovery of new development projects, their cognitive evaluation using Artificial Intelligence, and the automated generation of highly customized proposals for system administrators, optimizing response times and maximizing award opportunities.

### 1.2 High-Level Technical Objectives
*   **Non-Invasive Automation:** Implement an automated ingestion pipeline (Scraper) capable of handling dynamic rendering and complex interactivity on SPA (Single Page Applications) platforms.
*   **Decoupled Cognitive Evaluation:** Classify and estimate the technical and commercial viability of each collected project using advanced Natural Language Processing (LLM) models through an isolated cognitive engine.
*   **Secure and Idempotent Persistence:** Structurally record all projects, evaluation audits, control semaphores, and proposals, ensuring transactional consistency and state traceability.
*   **Real-Time Notification and Control:** Provide a bidirectional operational console based on a Telegram bot, serving as a single channel to alert, interact, and execute business transactions.
*   **Infrastructure Isolation:** Minimize environmental dependency by ensuring a production-ready packaging through Docker containers, isolated at the network and data volume level.

---

## 2. ARCHITECTURE AND DESIGN RULES

The system is structured under the principles of **Domain-Driven Design (DDD)** and **Hexagonal Architecture (Ports and Adapters)**. No infrastructure details (frameworks, persistence libraries, external APIs) should permeate the core business logic.

```
       [External Clients/Triggers]
                    |
                    v
         +---------------------+
         |   Driving Adaptor   |  (e.g., Telegram Bot Interface)
         +---------------------+
                    |
                    v
         +---------------------+
         |     Inbound Port    |  (Abstract Base Interfaces)
         +---------------------+
                    |
                    v
    =================================
    ||       APPLICATION CORE      ||  (Pure Business & Domain Logic)
    =================================
                    |
                    v
         +---------------------+
         |    Outbound Port    |  (Abstract Infrastructure Interfaces)
         +---------------------+
                    |
                    v
         +---------------------+
         |   Driven Adaptor    |  (e.g., Motor Repository, Playwright Scraper)
         +---------------------+
                    |
                    v
       [External Databases / APIs]
```

### 2.1 Dependency Inversion Principle (DIP) and Isolation
1.  **Abstraction at the Boundaries:** Higher-level modules (`scraper`, `intelligence`, `database`) must interact solely through abstract contracts (Ports). Concrete adapters (e.g., Playwright, Gemini SDK, Motor) are injected at runtime.
2.  **Zero Infrastructure Leakage:** Data types or exceptions specific to external adapters must never cross their module boundaries without prior translation. The scraper must convert DOM elements or Playwright selectors into primitive Python types or purely semantic Pydantic models before sending them to the application core.
3.  **Horizontal Module Isolation:** An adapter is strictly prohibited from interacting directly with another adapter (e.g., the scraper must not perform direct database writes). All communication is coordinated through the core application layer.

### 2.2 Project Topology and Directory Structure
The file hierarchy is strictly defined to support the hexagonal segregation of responsibilities:

```
.
├── app/                           # Main Application Monolith
│   ├── bots/                      # Primary Adapters / Drivers (Telegram routing, commands, and states)
│   ├── config/                    # Configuration Engine: Immutable environment variable validation
│   ├── database/                  # Data Infrastructure: Secondary adapters, repositories, and semaphore control
│   ├── intelligence/              # Cognitive Engine: LLM adapters and integrations
│   │   └── prompts/               # Versioned Jinja2 templates for prompt engineering
│   └── scraper/                   # Ingestion Engine: Web scraping adapters (Playwright, bs4)
│       └── adaptors/              # Concrete implementations (workana, dummy test suites)
├── migrations/                    # Database Schema and Seed Data Management (Synchronous, PyMongo)
│   └── scripts/                   # Self-managed idempotent migration scripts
├── scripts/                       # Maintenance, utilities, and auxiliary operational scripts
├── tests/                         # Automated test suites (unit and integration)
├── .env.example                   # Declarative schema definition of environment variables
├── docker-compose.yml             # Local service infrastructure orchestration (App, MongoDB)
└── requirements.txt               # Ecosystem dependency registration and pinning
```

### 2.3 Concurrency and Critical Resource Management
*   **Resource Release Guarantee:** Any resource that manages concurrency or exclusive access (like the processing semaphore) must be encapsulated in an asynchronous context manager (`async with`). This measure is mandatory to ensure that, even in the event of unexpected failures or unhandled exceptions during an operation, the resource is released correctly, preventing deadlocks in the system.

---

## 3. DATA DESIGN AND PERSISTENCE

### 3.1 Differentiated Engines and Drivers
The system implements polyglot persistence at the driver level to optimize execution cycles:
*   **Application Environment (Asynchronous):** Uses `motor` (based on `asyncio`) for all bot queries and writes, ensuring the event loop is not blocked during I/O operations.
*   **Migration Environment (Synchronous):** Uses `pymongo` to ensure atomic, step-by-step control, ensuring that schema alterations do not suffer from race conditions.

### 3.2 Schema Evolution: Migration System
Any modification to MongoDB collections and indexes must be executed through the custom migration framework located in `migrations/`. **Direct manual modifications are strictly prohibited in any environment.**

*   **Idempotency and Versioning:** Each migration is a Python script versioned by date (`vYYYYMMDD_NN_...`). Its repeated execution must result in the exact same final state in the database without generating inconsistencies.
*   **Atomic Operations (`ResilientBulkWriter`):** The use of raw modification commands is prohibited. The `ResilientBulkWriter` API (`writer`) must be used within scripts, which guarantees the atomicity of data operations through a Write-Ahead Logging (WAL) strategy.
*   **CLI for Management:** The creation, execution, and rollback of migrations are managed via a command-line interface (`python3 migrations/main.py`), allowing explicit control over the database lifecycle:
    *   `--create "description"`: Generates a new migration template.
    *   `--migrate`: Applies all pending migrations.
    *   `--rollback`: Reverts the last applied migration.
*   **Smart Rollback:** A migration's `up()` method defines data and infrastructure changes. The rollback of **data** is automatic thanks to the `ResilientBulkWriter`. The `down()` method is reserved exclusively for reversing **infrastructure** changes (e.g., deleting an index).

---

## 4. TESTING STRATEGY

The project adopts a multi-level testing strategy managed with `pytest` to ensure code quality and stability. Development dependencies are managed in `requirements-dev.txt`.

### 4.1 Unit Tests (`tests/unit/`)
*   **Philosophy:** They test business logic components in complete isolation, using mocks to simulate external dependencies (databases, AI APIs, etc.). They form the base of the testing pyramid and execute quickly.
*   **Scope:**
    *   Project classification and processing logic.
    *   Validation of proposal template selection.
    *   Formatting and construction of messages for Telegram.
    *   Repository behavior (with a mocked database).
    *   **Critical Error Handling:** System resilience is explicitly validated, including automatic retries on network failures, correct activation of the `Circuit Breaker`, and release of the concurrency semaphore in case of an error.

### 4.2 Integration Tests (`tests/integration/`)
*   **Philosophy:** They verify the correct collaboration between various system components. They require a real instance of external services, mainly a MongoDB database.
*   **Scope:**
    *   Correct creation of database indexes upon application startup.
    *   End-to-end data flows (e.g., from receiving a project to storing it with a specific `contract_type`).
    *   Validation of the structural integrity of data saved in the database.
*   **Conditional Execution:** These tests are automatically skipped if a database connection string (`MONGODB_URI`) is not provided, allowing the rest of the suite to run in environments without services.

### 4.3 Suite Execution
The test suite can be run with granularity from the project root:
*   **All tests:** `pytest tests/ -v`
*   **Unit tests only:** `pytest tests/unit/ -v`
*   **Generate coverage report:** `pytest tests/ --cov=app --cov-report=html`

---

## 5. UTILITY SCRIPTS (`scripts/`)

The `scripts/` directory contains operational and diagnostic tools to facilitate system development, configuration, and maintenance.

*   `check_projects.py`: A diagnostic script that connects to MongoDB and reports the current status of projects in the processing pipeline. It allows checking how many projects are analyzed, how many have a sufficient AI score, and how many are ready for the next stage.
*   `extract_session.py`: Operational utility executed manually by the developer in non-headless mode to handle initial authentication and dump the session cookies into `state.json`. *Note: Excluded from production runtime.*
*   `test_bot_session.py`: Smoke-test script executed manually to verify that the generated `state.json` successfully authenticates a headless browser instance before deploying the main application.
*   `get-gemini-images.py`: A utility to interact with the Google Gemini API. It lists all available AI models for the configured API key, allowing the developer to verify the connection and know the names of the models they can use.

---

## 6. INGESTION AND OPERATIONAL COMPONENTS

### 6.1 Resilient Ingestion (Scraper)
*   **Rendering Strategy:** The production adapter (`workana.py`) uses Playwright in headless mode to bypass protections and dynamically render JavaScript content.
*   **High-Performance Parser:** In-memory DOM structuring is delegated to BeautifulSoup4 for its CPU efficiency.
*   **Defensive Selectors and Robust Parsing:** Data extraction must use defensive CSS selectors that do not fail if an attribute changes. The extracted data must be validated and parsed into Pydantic models that use optional types (`Optional[...]`) and default values to prevent minor changes in the source website's DOM from causing fatal errors.
*   **Session Management & Resilience:** Cookies and session identifiers are loaded from a pre-existing `state.json` file to avoid costly re-authentications that trigger security alerts. If this session state is found to be expired or invalid during runtime, the automation must abort execution gracefully, raising a critical log/notification that instructs the user to manually regenerate the state using `scripts/extract_session.py` and validate it via `scripts/test_bot_session.py`.

### 6.2 Cognitive Architecture (Intelligence)
*   **SDK Integration:** Direct use of the official Google `google-genai` SDK for processing with Gemini.
*   **Prompt Containment:** AI prompts are structured outside the Python code in `.j2` (Jinja2) files under `app/intelligence/prompts/` to allow for clean iteration and versioning of prompt engineering.
*   **Dynamic Path Resolution:** Loading of `.j2` templates must be done using dynamic and robust paths, based on the location of the file that loads them (e.g., `pathlib.Path(__file__).parent`). The use of hardcoded relative or absolute paths is prohibited to avoid execution failures in different contexts.

### 6.3 Operational Channel (Telegram Bot)
*   **Extreme Asynchrony:** Implemented using `python-telegram-bot` in its fully asynchronous mode to scale simultaneously with calls to the Scraper and database.
*   **Connection Resilience:** Implementation of Circuit Breakers and exponential backoff in command handlers to prevent cascading failures if external APIs fail temporarily.

---

## 7. CODING AND QUALITY STANDARDS

### 7.1 Code Quality and Style
*   **Strict Typing:** Every function, method, or coroutine signature must fully define the input and output data types using Python type annotations (`typing`, `Pydantic`).
*   **Uniform Style:** Absolute compliance with **PEP 8**, automated formatting with `black`, and import sorting with `isort`.
*   **Value-Driven Comments:** Do not duplicate implicit logic. Code comments explain the **why** behind optimization decisions or complex invariants.

### 7.2 Professional Logging
*   All informational or tracing output is centralized through `Loguru`.
*   The use of generic `print()` calls is strictly forbidden.
*   Logs must be rigorously categorized by criticality: `INFO` for regular system flow, `WARNING` for controlled atypical events, `ERROR`/`CRITICAL` for failures that compromise data integrity or halt execution.

### 7.3 Documentation Cycle and Definition of Done (DoD)
*   **Documentation Cycle:** Any alteration to the API, environment variables, or architecture must atomically impact `README.md` and this `SPEC.md` specification.
*   **Definition of Done (DoD):** No functionality will be considered complete until its unit tests in `tests/unit/` achieve acceptable coverage and pass successfully.

---

## 8. RESTRICTIONS AND SECURITY

*   **Secret Isolation:** The highest priority configuration variable is defined locally in a `.env.local` file excluded from git. The `.env.example` file acts solely as a structural contract with no real credentials exposed.
*   **Dependency Control:** The `requirements.txt` and `requirements-dev.txt` files define the fixed dependencies. No additional modules should be imported without a prior security analysis and corresponding approval.
*   **System Security:** Since the application interacts with the local file system and browser automations, every command in production must operate in a restricted or containerized manner.

---

## 9. IMPLEMENTATION CHECKLIST (SDD)

### Milestone 1: Infrastructure and Database
- [x] Configure immutable environment with `app/config/` and `.env.example`.
- [x] Implement the synchronous migration CLI and `ResilientBulkWriter`.
- [x] Initialize the asynchronous connection with `motor` in `app/database/`.

### Milestone 2: Ingestion Engine (Scraper)
- [x] Implement the `workana.py` adapter with Playwright + BS4.
- [x] Map scraping output to pure Pydantic models.
- [x] **Session Lifecycle Handling:** Implement defensive error handling such that if authentication fails or the session expires, the pipeline halts gracefully with a clear instruction prompting the user to manually execute `extract_session.py` and validate it via `test_bot_session.py` before restarting.test_bot_session.py` before restarting.

### Milestone 3: Cognitive Engine and Operational Channel
- [x] Integrate `google-genai` and prompt loading from `.j2` templates.
- [x] Implement the asynchronous Telegram bot with its Circuit Breakers.
