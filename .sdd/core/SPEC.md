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

The system follows **Hexagonal Architecture (Ports & Adapters)** and **Domain-Driven Design (DDD)** principles, with explicit separation between core business logic and infrastructure:



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

### 2.1 Testing Strategy
All test files are organized by domain in `tests/unit/` and `tests/integration/`:
- **Unit tests** are in `tests/unit/` and are completely isolated with no network I/O.
- **Integration tests** are in `tests/integration/` and require `MONGO_URI` to be set (automatically skipped otherwise).
- Tests are organized to match the domain structure of `app/` for clear code/test alignment.

---

## 3. COMPOSITE SYSTEM INDEX

### 3.1 ARCHITECTURAL OVERVIEW MATRIX

The system operates through decoupled layers orchestrated by `.env` configuration. This mermaid diagram shows the global runtime structure:

```mermaid
graph LR
    subgraph Environmental Gateway
        ENV[.env Configuration] --> DB
        ENV --> IA
        ENV --> TGB
        ENV --> API
    end
    subgraph Runtime Execution
        DB -->|Persistence
        IA -->|Cognitive
        TGB -->|Automation
        API -->|Endpoints
        API -->|Orchestration
    end
```

### 3.2 COMPONENT INDEX & BRIEFINGS

- **DATABASE & PERSISTENCE (`.sdd/core/specs/DATABASE.md`)**
    Async MongoDB architecture using `motor` with transactional schema validation. Contains connection lifecycle management and document indexing strategies for projects, semaphores, and proposal versioning.

- **INTELLIGENCE & COGNITION (`.sdd/core/specs/INTELLIGENCE.md`)**
    Hexagonal architecture implementation for LLM integration. Uses database-driven port resolution to isolate Gemini and OpenRouter adapters. Enforces model selection patterns through `models` collection metadata.

- **TELEGRAM AUTOMATION (`.sdd/core/specs/TELEGRAM-BOTS.md`)**
    Telegram bot architecture with circuit breaker middleware. Implements project processing automation through command handlers, semaphores, and state-aware message routing integrated with database operations.

- **API SERVICES LAYER (`.sdd/core/specs/API.md`)**
    FastAPI endpoint architecture with OAuth2 authentication and model validation. Defines CRUD operations for projects, proposals, and model provider management through MongoDB persistence.

- **QUALITY ASSURANCE (`.sdd/core/specs/TESTING.md`)**
    Dual testing strategy: unit tests in `tests/unit/` with full dependency mocking, and integration tests in `tests/integration/` with real MongoDB operations validating document schema compliance.

### 3.3 ENVIRONMENTAL CONFIGURATION MATRIX

| Module         | Required Environment Variables                            | Operational Impact                          |
|----------------|------------------------------------------------------------|----------------------------------------------|
| Persistence    | `MONGO_URI`, `MONGO_URI_LOCAL`                             | Database connection & collection validation  |
| Intelligence   | `GEMINI_API_KEY`, `OPENROUTER_API_KEY`                     | LLM authentication & model execution         |
| Telegram       | `TELEGRAM_BOT_TOKEN`, `MY_TELEGRAM_ID`                     | Bot registration & admin authentication      |
| API Layer      | `SECRET_KEY`, `ALGORITHM`, `CORS_ORIGINS`                  | Authentication & security middleware         |
| Testing        | `MONGO_URI` (integration suite)                            | Database availability for validation tests   |

All configurations are sourced from `.env` and validated at application startup to ensure runtime consistency.