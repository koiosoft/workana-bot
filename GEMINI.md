# GEMINI.md: Architectural Blueprints & Engineering Standards
## Workana Bot — Core Specification & Development Guidelines

This document establishes the authoritative technical standards, architectural patterns, and engineering practices for the **Workana Bot** ecosystem. Designed for a Senior/Principal Architecture context, it provides strict operational guardrails to maintain decoupling, systemic resilience, data integrity, and strict separation of concerns.

---

## 🤖 1. Enterprise Technology Stack

The infrastructure is strictly decoupled and container-first, engineered to support asynchronous concurrency and transactional safety at the data layer.

* **Runtime Environment:** Python 3.11+ (Strict type-hinting required).
* **Application Orchestration:** Docker & Docker Compose (Multi-container isolated networks for app and storage layers).
* **Orchestration & Command Interface:** `python-telegram-bot` (Asynchronous event-loop driven framework for Telegram API routing).
* **Database Engine:** MongoDB 8.0 (Local high-performance Docker instance matching production topology).
* **Data Access Drivers:**
    * **Application Layer:** `motor` (Non-blocking, asynchronous driver matching the asyncio event loop).
    * **Data Migration Layer:** `pymongo` (Synchronous driver utilized exclusively for atomic, stateful schema transitions).
* **Cognitive & LLM Orchestration:** Google Gemini API integrated natively via the enterprise `google-genai` SDK.
* **Data Ingestion Pipeline (Scraper):** `Playwright` for headless browser automation and JS-heavy rendering, paired with `BeautifulSoup4` for high-speed in-memory DOM parsing.
* **Dependency Lifecycle:** Package tracking via `pip` pinned strictly inside `app/requirements.txt`.

---

## 🏗️ 2. Architectural Paradigm: Ports & Adaptors (Hexagonal)

The system relies on a **Hexagonal Architecture** to enforce a domain-centric model isolated from external side-effects. The application core must remain completely ignorant of framework, driver, and external API specifics.

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

### Architectural Mandates:
1.  **Dependency Inversion Principle (DIP):** Modules (`scraper`, `intelligence`, `database`) must define strict abstract base classes (Ports). Concrete implementations (Adaptors) must inherit from these ports.
2.  **Zero Leakage:** Domain entities and business routing rules must never import or leak infrastructure details (e.g., a scraping function must never leak a Playwright locator type; it must map data to a pure domain Primitive or Pydantic model before returning).
3.  **Cross-Module Isolation:** High-level architectural layers (`intelligence` vs `scraper`) are prohibited from directly communicating. They interact purely via orchestrated application-level services.

---

## 📂 3. System Directory Topology

```
.
├── app/                           # Main Application Monolith
│   ├── bots/                      # Interface Layer: Driving Adaptors (Telegram routing, commands, state machines)
│   ├── config/                    # Configuration Engine: Immutable environment parsing & validation
│   ├── database/                  # Data Access Infrastructure: Driven adaptors, repositories, connection lifecycles
│   ├── intelligence/              # Cognitive Engine: LLM integrations, operational prompt engineering
│   │   └── prompts/               # Version-controlled prompt payloads
│   └── scraper/                   # Data Ingestion Engine: Web scraping infrastructure
│       └── adaptors/              # Concrete targets (e.g., workana, dummy test suites)
├── migrations/                    # Stateful Database Schema & Data Migrations
│   └── scripts/                   # Idempotent migration scripts (versioned by ISO-8601 timestamp prefix)
├── .env.example                   # Declarative blueprint of all mandatory system variables
├── docker-compose.yml             # Local Multi-Service Stack Orchestration
└── requirements.txt               # Pinned Dependency Ledger
```

---

## ✍️ 4. Clean Code Standards & Engineering Style

### 4.1 Type Safety & Static Analysis
* **Explicit Type Hinting:** All callable interfaces (functions, methods, coroutines) must feature fully qualified type signatures for both arguments and return values. Use structural subtyping (`Protocol`) where applicable.
* **Style Uniformity:** Strict compliance with **PEP 8**. Automated enforcement via `black` code formatter and `isort` for import organization.

### 4.2 Nomenclatures
* **Variables, Functions, Methods, Modules:** `snake_case` (e.g., `fetch_project_payload`).
* **Classes, Types, Interfaces:** `PascalCase` (e.g., `ResilientBulkWriter`).
* **Constants:** `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_ATTEMPTS`).

### 4.3 Documentation Meta-Rules
* **Intent-Driven Comments:** Comments must exclusively document **why** an invariant or non-obvious optimization exists, never *what* the syntax executes.
* **Self-Documenting Code:** Code must possess high readability through descriptive identifier names. Redundant comments (e.g., `# Loop over projects`) will fail pull-request validation.

### 4.4 High-Performance Logging Ecosystem
* **Engine:** `Loguru` is the absolute logging standard across all modules.
* **Asynchronous Contexts:** Utilize Loguru's thread-safe and async-compatible sinks.
* **Severity Routing:**
    * `INFO`: Tracing lifecycle events, core application initialization, and successful transaction boundaries.
    * `WARNING`: Recoverable faults, rate-limiting warnings, back-off execution.
    * `ERROR` / `CRITICAL`: Unhandled architectural breaks, data persistence failure, infrastructure disconnection. Exception stack traces must be captured explicitly.

---

## 🔄 5. Schema Evolution & Database Migration Engineering

Database consistency is enforced via a strict, custom micro-framework managing structural and state data changes inside MongoDB.

### 5.1 Idempotency and Architectural Contract
* Every migration script must be strictly **idempotent**. Executing a script multiple times against the same database state must yield the identical outcome without duplicate records or corrupted indexes.
* Every script must implement explicit `up()` and `down()` procedures to allow seamless forward mutation and rollback recovery.

### 5.2 Atomic Operations & Resilient Writes
* Direct manipulation of the raw MongoDB driver inside migrations is strictly **banned**.
* All data operations within `up()` or `down()` phases must utilize the `ResilientBulkWriter` API.
* The `ResilientBulkWriter` ensures all structural transformations are buffered and batched via bulk-write pipelines (`add_insert`, `add_update_one`, etc.), maximizing atomic execution behavior and providing predictable state control.

---

## 🚫 6. Hard Architectural Restrictions (Zero-Tolerance)

* **No Unsanctioned Dependencies:** Adding packages to `requirements.txt` requires an architectural evaluation. Dependencies introduce supply-chain risks and binary overhead. Discuss with the architect before installing.
* **No Raw Direct DB Modification:** Direct manual modifications of collections or indexes in live databases are forbidden. All modifications must reside within versioned migration scripts.
* **No Module Responsibility Contamination:** Under no circumstances should scraping engines compute database mutations, nor should Telegram bot handlers parse raw DOM structures. Keep concerns cleanly isolated.
* **No Secrets Inversion (Hard Safety Lock):** Production or environment configurations must never be committed to version control. The `.env.local` file takes runtime priority and is explicitly blocked by `.gitignore`. The `.env.example` file must remain perfectly clean of real-world credentials, acting purely as a structural definition schema.

---

## 🔄 6. Post-Execution & Documentation Lifecycle Protocol

Every development cycle, code generation, or structural modification executed by the AI must conclude with a mandatory documentation alignment phase. The AI must evaluate and execute the following:

### 6.1 README.md Synchronous Updates
* If any architectural change, configuration parameter (`.env.example`), directory topology alteration, or new module invocation is introduced, the AI must immediately generate the updated version or patches for the corresponding `README.md` files.
* Documentation must match the current system state precisely; code implementations and documentation state transitions are atomic.

### 6.2 GEMINI.md Evolution Prompts
* Upon completing complex refactoring, stack evolution, or structural paradigm shifts, the AI must evaluate if the boundaries defined in this `GEMINI.md` have been pressured or altered[cite: 1].
* The AI is required to proactively suggest explicit, version-controlled additions or modifications to this `GEMINI.md` to ensure the core specification remains an accurate, living blueprint of the ecosystem[cite: 1].