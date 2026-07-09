# ✅ Testing Architecture Specification

## Testing Stack & Framework Architecture

- **Primary Framework**: `pytest`
- **Unit Testing Isolation**: `unittest.mock` (implicit via test implementation)
- **Test Directory Scope**:
  - `tests/unit/` - Isolated tests with full dependency mocks (database, network, LLM services)
  - `tests/integration/` - Real service execution with MongoDB and system boundary validation

## Test Environment & Fixture Management

**Environment Requirements**:
- MongoDB connection via `MONGO_URI` environment variable (integration tests depend on this)
- `PYTHONPATH` must include project root (`export PYTHONPATH="${PYTHONPATH}:$(pwd)"`)

**Fixture Strategy**:
- Auto-discovered fixtures via default pytest behavior
- Database setup/teardown isolation in integration tests
- Tests skip gracefully when MongoDB is unavailable

## Unit Testing Strategy (`tests/unit/`)

**Scope & Isolation**:
- Mocked all external systems (LLM API, repos, network services)
- Focused on core logic components:
  - Contract type detection logic
  - Template selection validation
  - Error handling workflows (retries, circuit breaker)
  - Telegram message formatting

**Nomenclature Patterns**:
- File naming: `test_<component>.py`
- Class-based organization: `Test<Feature><Scenario>` (e.g. `TestProcessProjectsErrorHandling`)
- Method-level granularity for retry scenarios

## Integration Testing Strategy (`tests/integration/`)

**Validated Flows**:
- File system boundary checks (existence validation)
- MongoDB schema compliance:
  - Index structure verification
  - Document contract-type mapping
- End-to-end data flow validation through core components

**State Management**:
- Requires real MongoDB instance (no embedded test DBs)
- Explicit database dependency declaration in test setup
- Test isolation enforced through document-level operations

## Execution Workflow & Guidelines

**CLI Commands**:
| Command | Purpose |
|---------|---------|
| `pytest tests/` | Full test suite (unit + integration) |
| `pytest tests/unit/` | Fast-path unit tests only |
| `pytest tests/integration/` | Production-equivalent integration tests |
| `--cov=app` | Enable code coverage analysis |

**CI/CD Integration**:
- Requires virtual environment activation (`venv/bin/activate`)
- Python path must include project root directory
- Integration tests require MongoDB availability on target infrastructure