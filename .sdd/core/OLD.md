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

### 2.1 Testing Strategy
All test files are organized by domain in `tests/unit/`:
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
- **Unit tests** are in `tests/unit/` and are completely isolated with no network I/O.
- **Integration tests** are in `tests/integration/` and require `MONGO_URI` to be set (automatically skipped otherwise).
- Tests are organized to match the domain structure of `app/` for clear code/test alignment.