# Workana Bot MongoDB Persistence Layer Specification

## 1. Database Architecture & Technology Stack

### **Stack Components**
- **Driver**: `motor` (Async IOMotorClient)
- **ODM/Abstraction**: None used (raw Motor driver operations via `AsyncIOMotorDatabase` interface)
- **Client Architecture**: Singleton connection pattern with lazy initialization

### **Directory Structure** (app/database/)
```
├── mongo.py                # Core database connection & management
├── users_repository.py     # UserRepository operations
├── semaphore.py            # Project semaphore lock management
├── projects_repository.py  # Project CRUD repository
└── proposal_versions_repository.py  # Proposal version history
```

## 2. Configuration & Environment Variables

### **MongoDB Environment Variables**
```env
MONGO_URI=mongodb+srv://<auth>@workanamongodb0.qu7h0p6.mongodb.net/
MONGO_URI_LOCAL=mongodb://admin:super_password_123@mongodb:27017/
MONGO_DB_NAME=workana_bot
```

- **Connection String**: Atlas SRV-based (prod) vs local Docker URI
- **Database Name**: Fixed to `workana_bot`
- **Password Security**: Stored in `.env`, not committed to source code

## 3. Connection Lifecycle & Initialization

```
connect_to_mongo() --> establish new connection
   │
   ▼
[AsyncIOMotorClient] --> connection pooling handled by Motor
   │
   ▼
[Singleton _db] --> global in mongo.py with lazy initialization
   │
   └── close_mongo_connection() -- on shutdown
```

- **Lazy Initialization**: `get_database()` creates client on first access
- **Reconnection Strategy**: Implicit via Motor's connection pooling
- **Graceful Shutdown**: Calls `client.close()` on exit/signal

## 4. Document Schema & Modeling Strategy

### **Schema Validation**
| Collection          | Key Constraints                                 | Schema Strategy                | Notes                       |
|----------------------|--------------------------------------------------|------------------------------|-----------------------------|
| providers           | `key` (unique, required)                        | `$jsonSchema` validation     | 3 mandatory fields         |
| models              | (`model_id`, `provider_key`) compound unique    | `$jsonSchema` validation     | Business-level cardinality constraints enforced in code |
| proposal_versions   | `project_id` + `version_number` logical ordering | `$jsonSchema` validation     | 5 mandatory fields        |

### **Index Strategy**
| Collection           | Indexes                                         | Use Case                      |
|-----------------------|--------------------------------------------------|-------------------------------|
| providers`           | `key` asc (unique)                              | Fast provider lookup        |
| models               | compound `model_id`+`provider_key` (unique)     | Model selection optimization |
| proposal_versions    | 1. (`project_id`, `version_number` DESC)        | Latest version lookup       |
|                     | 2. `project_id` asc                             | Aggregation grouping        |
|                     | 3. `link_hash` asc                              | Deduplication by hash       |

## 5. Data Flow & Operational Patterns

### **Execution Pipeline**
```mermaid
graph TD
    A[Load env vars] --> B[Initialize database client]
    B --> C[Schema validation on-demand]
    C --> D[Repository method invocation]
    D --> E[Query execution with Motor]
    E --> F[Document parsing to Python objects]

    subgraph SchemaValidation
        G[Auto-create collections with JSON schema]
        G --> H[Enforce field requirements]
        G --> I[Build necessary indexes]
    end

    subgraph Repository
        J[Collection access via get_database()]
        J --> K[Cursor iteration or document transformation]
    end
```

- **Validation Enforcement**: Schemas applied at collection creation time, not on writes
- **Schema Migrations**: Manual collection recreation required for schema changes
- **Operational Pattern**: Motor cursor iteration with in-memory transformation to domain models

> All database interactions use Motor's async/await interface for non-blocking IO.