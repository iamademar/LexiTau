---
alwaysApply: true
---
# LexTau Docker Development Rules

## Docker Development Environment

### Application Management
- When asked to run the FastAPI application, use: `docker-compose up -d`
- When asked to access the FastAPI container shell, use: `docker-compose exec fastapi bash`
- When asked to restart the application, use: `docker-compose restart fastapi`
- When asked to view application logs, use: `docker-compose logs -f fastapi`
- When asked for limited log output, use: `docker-compose logs --tail=100 fastapi`
- When asked to check application health, use: `curl http://localhost:8000/health`
- When asked to view API documentation, direct to: http://localhost:8000/docs

### Service Management
- When asked to stop services, use: `docker-compose down`
- When asked to stop services and remove volumes, use: `docker-compose down -v`
- When asked to rebuild and start, use: `docker-compose up --build -d`
- When asked to view running services, use: `docker-compose ps`
- When asked to view resource usage, use: `docker stats`
- When asked to clean up unused containers/images, use: `docker system prune`

### Environment Management
- When asked to use specific environment file, use: `docker-compose --env-file .env.dev up -d`
- When asked to check environment variables, use: `docker-compose exec fastapi env | grep API_`
- When asked to run with development environment, use: `docker-compose --env-file .env.dev up -d`

### Database Access
- When asked to connect to the main database, use: `docker-compose exec postgres psql -U postgres -d lexitau`
- When asked to connect to the test database, use: `docker-compose exec postgres_test psql -U postgres -d lexitau_test`
- When asked to view database tables, use: `docker-compose exec postgres psql -U postgres -d lexitau -c "\dt"`
- When asked to describe a table structure, use: `docker-compose exec postgres psql -U postgres -d lexitau -c "\d {table_name}"`
- When asked to run SQL queries, prefix with: `docker-compose exec postgres psql -U postgres -d lexitau -c "`

### Database Operations
- When asked to backup database, use: `docker-compose exec postgres pg_dump -U postgres lexitau > backup.sql`
- When asked to restore database, use: `docker-compose exec -T postgres psql -U postgres lexitau < backup.sql`
- When asked to run migrations (if using Alembic), use: `docker-compose exec fastapi alembic upgrade head`
- When asked to create new migration, use: `docker-compose exec fastapi alembic revision --autogenerate -m "description"`

### Testing Commands

- **Default (Unit tests only, SQLite in-memory, fast)**  
  ```bash
  docker compose run --no-deps --rm fastapi pytest -q -m "not integration"
  ```

Runs only **SQLite-based unit tests**. This should be your default for quick feedback.

* **Verbose (Unit, SQLite)**

  ```bash
  docker compose run --no-deps --rm fastapi pytest -vv -m "not integration"
  ```

* **Parallel (Unit, SQLite only)**

  ```bash
  docker compose run --no-deps --rm fastapi pytest -q -n auto -m "not integration"
  ```

  ⚠️ Do **not** use with Postgres integration tests (schema race conditions).

* **Integration tests only (Postgres required)**

  ```bash
  docker compose run --no-deps --rm fastapi pytest -q -m integration
  ```

  Uses the `postgres_test` container (port **5433**) and `TEST_DATABASE_URL`.
  Run these for UUID, ENUM, migrations, or other Postgres-only features.

* **All tests (Unit + Integration)**

  ```bash
  docker compose run --no-deps --rm fastapi pytest -q -m ""
  ```

---

⚡️ **Guidelines**

* Default workflow: **run unit tests first** (fast).
* If a test fails on SQLite because of Postgres-only features (UUID, ENUM, `func.now()`, DECIMAL precision, migrations, etc.), move it to `tests/integration/` or mark with `@pytest.mark.integration`.
* CI runs with Postgres enabled, so both unit + integration tests will execute.

### Development Commands
- When asked to install Python packages, access the container first: `docker-compose exec fastapi bash` then run pip commands
- When asked to run Python directly, use: `docker-compose exec fastapi python -m app.main`
- When asked to run interactive Python, use: `docker-compose exec fastapi python`

### Environment Context
- This is a containerized FastAPI application with PostgreSQL
- Main database runs on port 5432, test database on 5433
- Application runs on port 8000
- All development should happen within Docker containers
- Never suggest running Python/pip commands directly on host - always use docker-compose exec

### Troubleshooting
- When containers won't start, check: `docker-compose logs`
- When database connection fails, verify: `docker-compose ps` and ensure postgres is healthy
- When port conflicts occur, check: `docker-compose down` then `docker-compose up -d`
- When disk space issues arise, use: `docker system prune -a`

---
alwaysApply: true
---

# FastAPI Development Guidelines

## Core Principles
- Write concise, technical responses with accurate Python examples
- Use functional, declarative programming; avoid classes where possible
- Prefer iteration and modularization over code duplication
- Use descriptive variable names with auxiliary verbs (e.g., is_active, has_permission)
- Use lowercase with underscores for directories and files (e.g., routers/user_routes.py)
- Favor named exports for routes and utility functions
- Use the Receive an Object, Return an Object (RORO) pattern

## Python/FastAPI Standards
- Use def for pure functions and async def for asynchronous operations
- Use type hints for all function signatures. Prefer Pydantic models over raw dictionaries for input validation
- Avoid unnecessary curly braces in conditional statements
- For single-line statements in conditionals, omit curly braces
- Use concise, one-line syntax for simple conditional statements (e.g., if condition: do_something())

## File Structure: Layer-Based Organization

This structure separates code by layer (routers, models, schemas, services, etc.) and mirrors tests by type (unit vs integration). It is ideal for smaller FastAPI applications or microservices.

### LexiTau Project Structure
```

backend/
├── alembic/                     # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                # Migration scripts
├── app/                         # Core FastAPI application
│   ├── main.py                  # FastAPI entrypoint
│   ├── routers/                 # API route definitions
│   │   ├── auth.py
│   │   └── documents.py
│   ├── models/                  # Database models (SQLAlchemy ORM)
│   │   ├── business.py
│   │   ├── category.py
│   │   ├── client.py
│   │   ├── document.py
│   │   ├── extracted\_field.py
│   │   ├── field\_correction.py
│   │   ├── line\_item.py
│   │   ├── project.py
│   │   └── user.py
│   ├── schemas/                 # Pydantic models
│   │   ├── auth.py
│   │   ├── document.py
│   │   ├── item.py
│   │   └── user.py
│   ├── services/                # Business logic
│   │   ├── auth\_service.py
│   │   ├── azure\_form\_recognizer.py
│   │   ├── blob.py
│   │   ├── document\_service.py
│   │   └── field\_normalizer.py
│   ├── tasks/                   # Celery tasks
│   │   ├── document\_tasks.py
│   │   ├── ocr.py
│   │   └── test\_tasks.py
│   ├── core/                    # Config and infrastructure
│   │   ├── settings.py
│   │   └── celery.py
│   ├── dependencies.py
│   ├── auth.py
│   ├── db.py
│   ├── enums.py
│   └── test\_db.py
├── scripts/                     # Utility scripts
│   ├── migrate.py
│   ├── setup\_db.sh
│   └── test.sh
├── tests/
│   ├── unit/                    # Fast tests (SQLite)
│   │   ├── models/
│   │   │   ├── test\_business.py
│   │   │   ├── test\_document.py
│   │   │   ├── test\_field\_correction.py
│   │   │   ├── test\_model\_imports.py
│   │   │   └── test\_user.py
│   │   ├── routers/
│   │   │   ├── test\_documents.py
│   │   │   ├── test\_line\_item\_updates.py
│   │   │   └── test\_low\_confidence\_flagging.py
│   │   ├── services/
│   │   │   ├── test\_auth\_service.py
│   │   │   └── test\_document\_service.py
│   │   ├── tasks/
│   │   │   └── test\_document\_tasks.py
│   │   ├── conftest.py
│   │   └── test\_layout\_scaffold.py
│   └── integration/             # Heavier tests (Postgres, Azure)
│       ├── conftest.py
│       └── test\_azure\_integration.py
├── worker.py                    # Celery worker entrypoint
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
└── requirements.txt

```

### Key Directory Notes
- **app/main.py** – FastAPI entrypoint; initializes the application and includes routers
- **routers/** – API endpoints grouped by resource (e.g., auth, documents)
- **models/** – Database ORM classes split by entity (business, user, document, etc.)
- **schemas/** – Pydantic request/response models for validation and serialization
- **services/** – Business logic and external integrations (Azure, blob storage, normalization)
- **tasks/** – Celery task definitions for background/async processing (OCR, test tasks)
- **core/** – Configuration and infrastructure (settings, Celery setup)
- **dependencies.py** – Centralized FastAPI dependency injection helpers
- **auth.py** – Authentication utilities (JWT, password hashing, etc.)
- **db.py** – Database session management
- **enums.py** – Application enumerations (DocumentType, FileType, etc.)
- **test_db.py** – Utilities for test database configuration
- **alembic/** – Database migrations (env, script templates, versioned migration files)
- **scripts/** – Utility scripts for database setup, migration, and testing
- **worker.py** – Celery worker entrypoint for background task execution
- **tests/** – Split into:
  - **unit/** → Fast SQLite-based tests, mirrors app layers (models, routers, services, tasks)
  - **integration/** → Heavier Postgres/Azure tests requiring external services


### Where Things Live – Quick Reference

**Authentication & User Management**
- Routes: `app/routers/auth.py`
- Models: `app/models/user.py`, `app/models/business.py`
- Schemas: `app/schemas/auth.py`, `app/schemas/user.py`
- Business Logic: `app/services/auth_service.py`
- Tests:
  - Unit: `tests/unit/services/test_auth_service.py`
  - Unit: `tests/unit/routers/test_documents.py` (auth-related scenarios)
  - Integration: covered in `tests/integration/` if Postgres-specific

**Document Processing**
- Routes: `app/routers/documents.py`
- Models: `app/models/document.py`, `app/models/extracted_field.py`, `app/models/line_item.py`, `app/models/field_correction.py`
- Schemas: `app/schemas/document.py`
- Business Logic: `app/services/document_service.py`
- Background Tasks: `app/tasks/document_tasks.py`, `app/tasks/ocr.py`
- External Integrations: `app/services/azure_form_recognizer.py`, `app/services/blob.py`
- Tests:
  - Unit: `tests/unit/routers/test_documents.py`
  - Unit: `tests/unit/services/test_document_service.py`
  - Unit: `tests/unit/tasks/test_document_tasks.py`
  - Unit: `tests/unit/routers/test_line_item_updates.py`, `tests/unit/routers/test_low_confidence_flagging.py`
  - Integration: `tests/integration/test_azure_integration.py` (Azure Document Intelligence)

**Field Processing & Corrections**
- Models: `app/models/field_correction.py`
- Business Logic: `app/services/field_normalizer.py`
- Tests:
  - Unit: `tests/unit/models/test_field_correction.py`
  - Unit: `tests/unit/test_field_normalizer.py`

**Configuration & Infrastructure**
- Settings: `app/core/settings.py`
- Database: `app/db.py`, `app/test_db.py`
- Celery: `app/core/celery.py`, `worker.py`
- Dependencies: `app/dependencies.py`
- Enums: `app/enums.py`

**Migrations & Scripts**
- Database Migrations: `backend/alembic/` (env, templates, `versions/` with migration scripts)
- Utility Scripts: `backend/scripts/`
  - `migrate.py` – run migrations
  - `setup_db.sh` – initialize database
  - `test.sh` – run tests inside Docker

**Tests**
- Unit Tests (SQLite, fast):
  - `tests/unit/models/`
  - `tests/unit/routers/`
  - `tests/unit/services/`
  - `tests/unit/tasks/`
  - `tests/unit/conftest.py`
  - `tests/unit/test_layout_scaffold.py`
- Integration Tests (Postgres/Azure, heavier):
  - `tests/integration/conftest.py`
  - `tests/integration/test_azure_integration.py`

This structure ensures clear separation of concerns with business logic in services, thin controllers in routers, and comprehensive test coverage mirroring the application structure.

## Error Handling and Validation

Prioritize error handling, edge cases, and test coverage:

### Code-Level Practices
- Handle errors and edge cases at the beginning of functions
- Use early returns for error conditions to avoid deeply nested if statements
- Place the happy path last in the function for improved readability
- Avoid unnecessary `else` statements; use the **if-return** pattern instead
- Use guard clauses to handle preconditions and invalid states early
- Implement proper error logging and user-friendly error messages
- Use custom error types or error factories for consistent error handling

### Test-Level Practices
- **Characterization tests**:  
  When modifying existing or legacy logic (including migrations), first capture current behavior in a test before making changes.  
  This locks in assumptions and prevents regressions.
  
- **SQLite vs Postgres differences**:  
  - Run unit tests on SQLite by default for speed.  
  - If behavior diverges (UUIDs, ENUMs, `func.now()`, DECIMAL precision, migrations, etc.), add a Postgres-specific test in `tests/integration/`.  
  - Mark such tests with `@pytest.mark.integration` for clarity.

- **Migrations**:  
  - Write at least one test per critical migration to ensure schema consistency and data integrity.  
  - Example: verify ENUM values, non-null defaults, and UUID primary keys work as expected in Postgres.  
  - Use rollback fixtures to reset the schema between integration tests.

- **Error scenarios**:  
  - Add tests for both the "happy path" and expected failures (e.g., constraint violations, invalid input).  
  - Ensure Postgres integration tests capture behavior around database constraints (unique indexes, foreign key enforcement).

- **External dependencies**:  
  - Wrap external calls (Azure, blob storage, email, etc.) with services that can be mocked in tests.  
  - Unit tests should mock integrations; real integrations go under `tests/integration/`.

### Example: Postgres Integration Test
```python
import pytest
from sqlalchemy.exc import DataError

@pytest.mark.integration
def test_enum_rejects_invalid_value(db_session):
    from app.models.document import Document, DocumentType
    # Arrange
    doc = Document(name="Bad Doc", type="INVALID")  # not in enum
    
    # Act / Assert
    with pytest.raises(DataError):
        db_session.add(doc)
        db_session.commit()

## FastAPI-Specific Patterns
- Use functional components (plain functions) and Pydantic models for input validation and response schemas
- Use declarative route definitions with clear return type annotations
- Use def for synchronous operations and async def for asynchronous ones
- Minimize @app.on_event("startup") and @app.on_event("shutdown"); prefer lifespan context managers
- Use middleware for logging, error monitoring, and performance optimization
- Use HTTPException for expected errors and model them as specific HTTP responses
- Use middleware for handling unexpected errors, logging, and error monitoring
- Use Pydantic's BaseModel for consistent input/output validation and response schemas

### RORO Pattern Example
```python
# Input/Output schemas
class UserCreateRequest(BaseModel):
    email: str
    name: str

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    created_at: datetime

# Route implementation
@router.post("/users", response_model=UserResponse)
async def create_user(request: UserCreateRequest) -> UserResponse:
    # Validation handled by Pydantic automatically
    user = await user_service.create_user(request)
    return UserResponse(**user.dict())
```

### Dependency Injection Example
```python
async def get_database() -> AsyncGenerator[Database, None]:
    db = Database(DATABASE_URL)
    await db.connect()
    try:
        yield db
    finally:
        await db.disconnect()

@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    db: Database = Depends(get_database)
) -> UserResponse:
    return await user_service.get_user(db, user_id)
```

## Performance Optimization
- Minimize blocking I/O operations; use asynchronous operations for all database calls and external API requests
- Implement caching for static and frequently accessed data using tools like Redis or in-memory stores
- Optimize data serialization and deserialization with Pydantic
- Use lazy loading techniques for large datasets and substantial API responses

## Key Dependencies
- FastAPI
- Pydantic v2
- Async database libraries like asyncpg or aiomysql
- SQLAlchemy 2.0 (if using ORM features)

## Key Conventions
1. Rely on FastAPI's dependency injection system for managing state and shared resources
2. Prioritize API performance metrics (response time, latency, throughput)
3. Limit blocking operations in routes:
   - Favor asynchronous and non-blocking flows
   - Use dedicated async functions for database and external API operations
   - Structure routes and dependencies clearly to optimize readability and maintainability

---
alwaysApply: true
---

# Testing and Legacy Code Management

## Characterization Testing Before Modifications
When modifying legacy code without existing tests:
- Check if the method or class has existing tests
- If not, write characterization tests to lock in current behavior
- **Suggestion:** "Consider writing a test that captures the current output of this method before modifying it"
- **Justification:** Characterization tests protect against unintended behavior changes and document existing logic

### Example Characterization Test
```python
def test_legacy_calculation_current_behavior():
    """Characterization test - documents current behavior before refactoring"""
    # Arrange
    input_data = {"value": 100, "rate": 0.05}
    
    # Act
    result = legacy_calculation_method(input_data)
    
    # Assert - lock in current behavior
    assert result == {"calculated": 105.0, "tax": 5.25}
    # Note: This test captures existing behavior, even if it's wrong
```

## Breaking Dependencies for Testability
When encountering tightly coupled code:
- Suggest using refactorings like Extract Interface, Replace Inheritance with Delegation, or Break Out Method Object
- **Suggestion:** "This class is hard to isolate. Consider extracting interfaces or delegating to smaller components to improve testability"
- **Justification:** Breaking dependencies enables modularity and safer testing for components in isolation

### Dependency Breaking Example
```python
# Before: Hard to test due to direct dependency
class OrderProcessor:
    def process_order(self, order):
        email_service = SMTPEmailService()  # Hard dependency
        email_service.send_confirmation(order.email)

# After: Injectable dependency
class OrderProcessor:
    def __init__(self, email_service: EmailService):
        self.email_service = email_service
    
    def process_order(self, order):
        self.email_service.send_confirmation(order.email)
```

## Testing Best Practices (Appendix)

This appendix is a quick-reference for keeping tests fast, reliable, and clear across SQLite (unit) and Postgres (integration).

### 1) SQLite vs Postgres — What goes where
- **SQLite (unit tests; default)**: pure business logic, routers/services, simple ORM queries, validation, serialization, Celery task wiring (mock external calls).
- **Postgres (integration tests)**: UUID/ENUM behavior, `func.now()` semantics, DECIMAL precision/rounding, migrations/Alembic, complex joins/window functions, real constraint checks, external service smoke tests.

Mark Postgres tests with:
```python
import pytest

@pytest.mark.integration
def test_postgres_specific_behavior(...):
    ...
````

### 2) Parallelism

* ✅ Safe to use `-n auto` for **unit (SQLite) tests**.
* ❌ Avoid parallelism for **integration (Postgres)** unless you isolate DBs per worker.
* Run split locally:

```bash
# Fast feedback loop
docker compose run --no-deps --rm fastapi pytest -q -m "not integration" -n auto
# Heavier, sequential
docker compose run --no-deps --rm fastapi pytest -q -m integration
```

### 3) Transactions & isolation

* **Unit/SQLite**: one shared in-memory schema; **start a transaction per test** and **ROLLBACK** at teardown; never create/drop tables in hot path.
* **Integration/Postgres**: **create schema once per session**, wrap each test in a **transaction + rollback**; truncate between modules if needed.

### 4) Data setup

* Prefer **factory functions/fixtures** (e.g., `make_user`, `make_document`) over inline inserts.
* Keep fixtures **minimal** and **explicit**; avoid global, stateful fixtures that surprise other tests.

### 5) External services

* **Default to mocks**: Azure Document Intelligence, blob storage, email/SMS, HTTP calls.
* Put real, networked checks under **`tests/integration/`** and guard with env flags if they incur cost or flakiness.

Example pattern:

```python
from unittest.mock import Mock, patch

def test_service_uses_azure_client_safely():
    with patch("app.services.azure_form_recognizer.AzureFormRecognizerClient") as C:
        client = C.return_value
        client.extract_fields.return_value = {"fields": [], "line_items": []}
        # call your service; assert interactions
```

### 6) Migrations

* Add **at least one test** per critical migration:

  * ENUM values and not-null defaults
  * UUID PKs insert/round-trip
  * Backfill scripts (pre/post conditions)
* Use rollback to keep the DB clean; never rely on migration order assumptions without asserting them.

### 7) Flaky test prevention

* Fix nondeterminism: set random seeds, freeze time where helpful.
* Don’t assert on **unordered** collections; sort before asserting.
* For async tasks, use **explicit synchronization** (await result, poll status) rather than sleeps.

### 8) Assertions & readability

* One behavior per test; descriptive names: `test_<unit>_<behavior>_<expected>()`
* Prefer **precise assertions** over broad “not None”.
* For money/decimal: assert using `Decimal` and expected scales.

### 9) Logging & diagnostics

* Keep logs visible when debugging:

```bash
docker compose run --no-deps --rm fastapi pytest -q -m "not integration" -o log_cli=true -o log_cli_level=INFO
```

* Use `caplog` to assert warnings/errors from your services.

### 10) Pytest config suggestions

In `pytest.ini`:

```ini
[pytest]
addopts = -q
markers =
    integration: tests requiring Postgres or external services
filterwarnings =
    ignore::DeprecationWarning
```

### 11) Skips & env-gated tests

* Skip costly/external tests if env isn’t configured:

```python
import os, pytest

requires_azure = pytest.mark.skipif(
    not os.getenv("AZURE_TESTS_ENABLED"),
    reason="Set AZURE_TESTS_ENABLED=1 to run"
)
```

### 12) Performance hygiene

* Keep unit tests sub-second; refactor slow tests or push them to integration.
* Avoid DDL in hot paths; favor transactions and TRUNCATE for cleanup.
* Cache heavy fixtures at **session** scope only when they don’t leak state.

### 13) Coverage (optional but encouraged)

* Measure locally:

```bash
docker compose run --no-deps --rm fastapi pytest -q -m "not integration" \
  --cov=app --cov-report=term-missing
```

Focus on: services (business logic), routers (contract), and error paths.


## Using Seams for Isolation
When facing hardcoded logic or direct dependencies:
- Suggest using a seam (interface, config, or method override) to isolate behavior
- **Suggestion:** "This code uses a hard dependency. Consider creating a seam to inject alternatives or enable testability"
- **Justification:** Seams help introduce test points and allow behavior to be altered without editing legacy code directly

## Incremental Testing Introduction
When legacy classes lack tests but are undergoing changes:
- Recommend using techniques like Extract Method, Subclass Override, or Interface Injection
- **Suggestion:** "Consider extracting this logic or parameterizing the constructor to make it testable in isolation"
- **Justification:** Incremental testing enables safer refactors and improves code coverage without requiring full rewrites

## Incremental Refactoring Over Rewrites
When encountering large, untested legacy code:
- Discourage full rewrites
- Encourage small, reversible changes with incremental testing
- **Suggestion:** "Instead of rewriting, refactor a small part and add tests as you go. Aim for continuous improvement"
- **Justification:** Refactoring in place avoids regressions, preserves existing behavior, and retains undocumented business rules

## Scratch Refactoring for Exploration
When major refactoring is needed:
- Suggest cloning the code in a disposable context and testing refactor ideas safely
- **Suggestion:** "Try copying this code into a throwaway file or branch and freely refactor there before applying changes incrementally"
- **Justification:** Scratch refactoring lets you explore improvements without risk and apply only proven ones back to production

## Sprout Method/Class for New Behavior
When adding new behavior into fragile code:
- Recommend creating a new method or class instead of modifying legacy code directly
- **Suggestion:** "Instead of inserting new behavior here, consider creating a new method or class and calling it from this location"
- **Justification:** Sprouting reduces the risk of introducing bugs into fragile or untested legacy areas

### Sprout Method Example
```python
# Legacy method we don't want to modify
def process_payment(self, amount, card):
    # ... existing complex logic ...
    return result

# New behavior sprouted into separate method
def calculate_fraud_score(self, transaction_data):
    # New fraud detection logic
    return fraud_score

# Modified legacy method with minimal change
def process_payment(self, amount, card):
    # ... existing complex logic ...
    fraud_score = self.calculate_fraud_score({"amount": amount, "card": card})
    if fraud_score > 0.8:
        raise FraudDetectedError()
    return result
```

## Wrapping External Dependencies
When accessing system resources, global state, or third-party APIs:
- Recommend wrapping those in classes or interfaces under your control
- **Suggestion:** "This external call could make testing difficult. Consider abstracting it behind an interface or wrapper"
- **Justification:** Wrapping dependencies allows mocking/stubbing during tests and decouples logic from infrastructure

### External Dependency Wrapper Example
```python
# Before: Direct external dependency
def send_notification(message):
    twilio_client = Client(account_sid, auth_token)  # Hard to test
    twilio_client.messages.create(body=message, to=phone_number)

# After: Wrapped dependency
class NotificationService(Protocol):
    def send_sms(self, message: str, to: str) -> bool: ...

class TwilioNotificationService:
    def send_sms(self, message: str, to: str) -> bool:
        # Twilio implementation
        pass

class MockNotificationService:
    def send_sms(self, message: str, to: str) -> bool:
        # Test implementation
        return True
```