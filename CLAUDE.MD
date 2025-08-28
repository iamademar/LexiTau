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
- When asked to connect to the main database, use: `docker-compose exec postgres psql -U postgres -d lexextract`
- When asked to connect to the test database, use: `docker-compose exec postgres_test psql -U postgres -d lexextract_test`
- When asked to view database tables, use: `docker-compose exec postgres psql -U postgres -d lexextract -c "\dt"`
- When asked to describe a table structure, use: `docker-compose exec postgres psql -U postgres -d lexextract -c "\d {table_name}"`
- When asked to run SQL queries, prefix with: `docker-compose exec postgres psql -U postgres -d lexextract -c "`

### Database Operations
- When asked to backup database, use: `docker-compose exec postgres pg_dump -U postgres lexextract > backup.sql`
- When asked to restore database, use: `docker-compose exec -T postgres psql -U postgres lexextract < backup.sql`
- When asked to run migrations (if using Alembic), use: `docker-compose exec fastapi alembic upgrade head`
- When asked to create new migration, use: `docker-compose exec fastapi alembic revision --autogenerate -m "description"`

### Testing Commands
- When asked to run tests, use: `docker-compose exec fastapi pytest`
- When asked to run specific test files, use: `docker-compose exec fastapi pytest {test_file_path}`
- When asked to run tests with coverage, use: `docker-compose exec fastapi pytest --cov=app`
- When asked to run unit tests only, use: `docker-compose exec fastapi pytest tests/unit/`
- When asked to run integration tests, use: `docker-compose exec fastapi pytest tests/integration/`
- When asked to skip slow tests, use: `docker-compose exec fastapi pytest -m "not slow"`

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
This structure separates code by layer (routers, models, schemas, services, etc.) and is ideal for smaller FastAPI applications or microservices.

```
my_fastapi_project/
├── app/
│   ├── main.py                 # FastAPI entrypoint
│   ├── routers/                # API route definitions
│   │   ├── __init__.py
│   │   ├── users.py
│   │   └── items.py
│   ├── models/                 # Database models (SQLAlchemy, etc.)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── item.py
│   ├── schemas/                # Pydantic models for request/response
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── item.py
│   ├── services/               # Business logic / service layer
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   └── item_service.py
│   ├── dependencies.py         # Dependency injection helpers
│   └── core/                   # Config, settings, utils
│       ├── __init__.py
│       ├── config.py
│       ├── database.py
│       └── security.py
└── tests/
    ├── __init__.py
    ├── test_main.py
    ├── test_users.py
    └── test_items.py
```

### Key Directory Notes
- **app/main.py** - Initializes the application and includes routers
- **routers/** - Contains API endpoints grouped by resource
- **models/** - Defines database tables or ORM classes
- **schemas/** - Defines Pydantic request/response models
- **services/** - Implements business logic (e.g., user registration, item processing)
- **dependencies.py** - Shared FastAPI dependencies (DB session, auth, etc.)
- **core/** - Configuration, database setup, security utilities
- **tests/** - Mirrors routes/services for clear mapping in test coverage

This structure is recommended for smaller apps where clarity and separation of concerns are prioritized.

## Error Handling and Validation
Prioritize error handling and edge cases:
- Handle errors and edge cases at the beginning of functions
- Use early returns for error conditions to avoid deeply nested if statements
- Place the happy path last in the function for improved readability
- Avoid unnecessary else statements; use the if-return pattern instead
- Use guard clauses to handle preconditions and invalid states early
- Implement proper error logging and user-friendly error messages
- Use custom error types or error factories for consistent error handling

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
alwaysApply: false
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