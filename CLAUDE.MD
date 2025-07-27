---
alwaysApply: true
---
# LexTau Docker Development Rules

## Application Access
- When asked to run the FastAPI application, use: `docker-compose up -d`
- When asked to access the FastAPI container shell, use: `docker-compose exec fastapi bash`
- When asked to restart the application, use: `docker-compose restart fastapi`
- When asked to view application logs, use: `docker-compose logs -f fastapi`

## Database Access
- When asked to connect to the main database, use: `docker-compose exec postgres psql -U postgres -d lexextract`
- When asked to connect to the test database, use: `docker-compose exec postgres_test psql -U postgres -d lexextract_test`
- When asked to view database tables, use: `docker-compose exec postgres psql -U postgres -d lexextract -c "\dt"`
- When asked to describe a table structure, use: `docker-compose exec postgres psql -U postgres -d lexextract -c "\d {table_name}"`
- When asked to run SQL queries, prefix with: `docker-compose exec postgres psql -U postgres -d lexextract -c "`

## Testing
- When asked to run tests, use: `docker-compose exec fastapi pytest`
- When asked to run specific test files, use: `docker-compose exec fastapi pytest {test_file_path}`
- When asked to run tests with coverage, use: `docker-compose exec fastapi pytest --cov=app`

## Development Commands
- When asked to install Python packages, access the container first: `docker-compose exec fastapi bash` then run pip commands
- When asked to check application health, use: `curl http://localhost:8000/health`
- When asked to view API documentation, direct to: http://localhost:8000/docs


## Service Management
- When asked to stop services, use: `docker-compose down`
- When asked to rebuild and start, use: `docker-compose up --build -d`
- When asked to view running services, use: `docker-compose ps`
- When asked to view resource usage, use: `docker stats`

## Database Operations
- When asked to backup database, use: `docker-compose exec postgres pg_dump -U postgres lexextract > backup.sql`
- When asked to restore database, use: `docker-compose exec -T postgres psql -U postgres lexextract < backup.sql`

## Environment Context
- This is a containerized FastAPI application with PostgreSQL
- Main database runs on port 5432, test database on 5433
- Application runs on port 8000
- All development should happen within Docker containers
- Never suggest running Python/pip commands directly on host - always use docker-compose exec

---
alwaysApply: false
---


  You are an expert in Python, FastAPI, and scalable API development.
  
  Key Principles
  - Write concise, technical responses with accurate Python examples.
  - Use functional, declarative programming; avoid classes where possible.
  - Prefer iteration and modularization over code duplication.
  - Use descriptive variable names with auxiliary verbs (e.g., is_active, has_permission).
  - Use lowercase with underscores for directories and files (e.g., routers/user_routes.py).
  - Favor named exports for routes and utility functions.
  - Use the Receive an Object, Return an Object (RORO) pattern.
  
  Python/FastAPI
  - Use def for pure functions and async def for asynchronous operations.
  - Use type hints for all function signatures. Prefer Pydantic models over raw dictionaries for input validation.
  - File structure: exported router, sub-routes, utilities, static content, types (models, schemas).
  - Avoid unnecessary curly braces in conditional statements.
  - For single-line statements in conditionals, omit curly braces.
  - Use concise, one-line syntax for simple conditional statements (e.g., if condition: do_something()).
  
  Error Handling and Validation
  - Prioritize error handling and edge cases:
    - Handle errors and edge cases at the beginning of functions.
    - Use early returns for error conditions to avoid deeply nested if statements.
    - Place the happy path last in the function for improved readability.
    - Avoid unnecessary else statements; use the if-return pattern instead.
    - Use guard clauses to handle preconditions and invalid states early.
    - Implement proper error logging and user-friendly error messages.
    - Use custom error types or error factories for consistent error handling.
  
  Dependencies
  - FastAPI
  - Pydantic v2
  - Async database libraries like asyncpg or aiomysql
  - SQLAlchemy 2.0 (if using ORM features)
  
  FastAPI-Specific Guidelines
  - Use functional components (plain functions) and Pydantic models for input validation and response schemas.
  - Use declarative route definitions with clear return type annotations.
  - Use def for synchronous operations and async def for asynchronous ones.
  - Minimize @app.on_event("startup") and @app.on_event("shutdown"); prefer lifespan context managers for managing startup and shutdown events.
  - Use middleware for logging, error monitoring, and performance optimization.
  - Optimize for performance using async functions for I/O-bound tasks, caching strategies, and lazy loading.
  - Use HTTPException for expected errors and model them as specific HTTP responses.
  - Use middleware for handling unexpected errors, logging, and error monitoring.
  - Use Pydantic's BaseModel for consistent input/output validation and response schemas.
  
  Performance Optimization
  - Minimize blocking I/O operations; use asynchronous operations for all database calls and external API requests.
  - Implement caching for static and frequently accessed data using tools like Redis or in-memory stores.
  - Optimize data serialization and deserialization with Pydantic.
  - Use lazy loading techniques for large datasets and substantial API responses.
  
  Key Conventions
  1. Rely on FastAPI’s dependency injection system for managing state and shared resources.
  2. Prioritize API performance metrics (response time, latency, throughput).
  3. Limit blocking operations in routes:
     - Favor asynchronous and non-blocking flows.
     - Use dedicated async functions for database and external API operations.
     - Structure routes and dependencies clearly to optimize readability and maintainability.
  
  Refer to FastAPI documentation for Data Models, Path Operations, and Middleware for best practices.
  
  You are an expert in Python, FastAPI, and scalable API development.
  
  Key Principles
  - Write concise, technical responses with accurate Python examples.
  - Use functional, declarative programming; avoid classes where possible.
  - Prefer iteration and modularization over code duplication.
  - Use descriptive variable names with auxiliary verbs (e.g., is_active, has_permission).
  - Use lowercase with underscores for directories and files (e.g., routers/user_routes.py).
  - Favor named exports for routes and utility functions.
  - Use the Receive an Object, Return an Object (RORO) pattern.
  
  Python/FastAPI
  - Use def for pure functions and async def for asynchronous operations.
  - Use type hints for all function signatures. Prefer Pydantic models over raw dictionaries for input validation.
  - File structure: exported router, sub-routes, utilities, static content, types (models, schemas).
  - Avoid unnecessary curly braces in conditional statements.
  - For single-line statements in conditionals, omit curly braces.
  - Use concise, one-line syntax for simple conditional statements (e.g., if condition: do_something()).
  
  Error Handling and Validation
  - Prioritize error handling and edge cases:
    - Handle errors and edge cases at the beginning of functions.
    - Use early returns for error conditions to avoid deeply nested if statements.
    - Place the happy path last in the function for improved readability.
    - Avoid unnecessary else statements; use the if-return pattern instead.
    - Use guard clauses to handle preconditions and invalid states early.
    - Implement proper error logging and user-friendly error messages.
    - Use custom error types or error factories for consistent error handling.
  
  Dependencies
  - FastAPI
  - Pydantic v2
  - Async database libraries like asyncpg or aiomysql
  - SQLAlchemy 2.0 (if using ORM features)
  
  FastAPI-Specific Guidelines
  - Use functional components (plain functions) and Pydantic models for input validation and response schemas.
  - Use declarative route definitions with clear return type annotations.
  - Use def for synchronous operations and async def for asynchronous ones.
  - Minimize @app.on_event("startup") and @app.on_event("shutdown"); prefer lifespan context managers for managing startup and shutdown events.
  - Use middleware for logging, error monitoring, and performance optimization.
  - Optimize for performance using async functions for I/O-bound tasks, caching strategies, and lazy loading.
  - Use HTTPException for expected errors and model them as specific HTTP responses.
  - Use middleware for handling unexpected errors, logging, and error monitoring.
  - Use Pydantic's BaseModel for consistent input/output validation and response schemas.
  
  Performance Optimization
  - Minimize blocking I/O operations; use asynchronous operations for all database calls and external API requests.
  - Implement caching for static and frequently accessed data using tools like Redis or in-memory stores.
  - Optimize data serialization and deserialization with Pydantic.
  - Use lazy loading techniques for large datasets and substantial API responses.
  
  Key Conventions
  1. Rely on FastAPI’s dependency injection system for managing state and shared resources.
  2. Prioritize API performance metrics (response time, latency, throughput).
  3. Limit blocking operations in routes:
     - Favor asynchronous and non-blocking flows.
     - Use dedicated async functions for database and external API operations.
     - Structure routes and dependencies clearly to optimize readability and maintainability.
  
  Refer to FastAPI documentation for Data Models, Path Operations, and Middleware for best practices.
  
  ---
description: When about to change legacy code without tests, write characterization tests first to lock in current behavior.
globs: 
alwaysApply: false
---
# Title: Characterization Testing Before Modifications

## When modifying legacy code...
- Check if the method or class has existing tests.
- If not, recommend writing characterization tests to lock in current behavior.

## Suggestion:
"Consider writing a test that captures the current output of this method before modifying it."

## Justification:
Characterization tests protect against unintended behavior changes and document existing logic, especially when no tests exist.

---
description: When encountering tightly coupled code—apply refactorings (extract interfaces, delegation) to break dependencies.
globs: 
alwaysApply: false
---
# Title: Break Dependencies to Enable Unit Testing

## When tightly coupled or hard-to-test code is found...
- Suggest using refactorings like Extract Interface, Replace Inheritance with Delegation, or Break Out Method Object.

## Suggestion:
"This class is hard to isolate. Consider extracting interfaces or delegating to smaller components to improve testability."

## Justification:
Breaking dependencies enables modularity and safer testing for components in isolation.

---
description: When facing hardcoded logic or direct dependencies—introduce a seam to decouple and enable isolated testing.
globs: 
alwaysApply: false
---
# Title: Use Seams to Isolate Behavior for Testing

## When direct dependencies or hardcoded logic are detected...
- Suggest using a seam (e.g., interface, config, or method override) to isolate behavior.

## Suggestion:
"This code uses a hard dependency. Consider creating a seam to inject alternatives or enable testability."

## Justification:
Seams help introduce test points and allow behavior to be altered without editing the legacy code directly.

---
description: When modifying untested classes—use indirection (extract methods, subclass) to add tests incrementally.
globs: 
alwaysApply: false
---
# Title: Introduce Tests Incrementally Using Indirection Techniques

## When legacy classes lack tests but are undergoing changes...
- Recommend using techniques like Extract Method, Subclass Override, or Interface Injection.

## Suggestion:
"Consider extracting this logic or parameterizing the constructor to make it testable in isolation."

## Justification:
Incremental testing enables safer refactors and improves code coverage without requiring full rewrites.

---
description: 
globs: 
alwaysApply: false
---
# Title: Refactor Incrementally, Avoid Full Rewrites

## When encountering large, untested legacy code...
- Discourage full rewrites.
- Encourage small, reversible changes with incremental testing.

## Suggestion:
"Instead of rewriting, refactor a small part and add tests as you go. Aim for continuous improvement."

## Justification:
Refactoring in place avoids regressions, preserves existing behavior, and retains undocumented business rules.

---
description: When planning a major refactor—suggest a throwaway branch/file to safely experiment before merging changes.
globs: 
alwaysApply: false
---
# Title: Use Scratch Refactoring for Risk-Free Exploration

## When major refactoring is needed...
- Suggest cloning the code in a disposable context and testing refactor ideas safely.

## Suggestion:
"Try copying this code into a throwaway file or branch and freely refactor there before applying changes incrementally."

## Justification:
Scratch refactoring lets you explore improvements without risk and apply only the proven ones back into the production branch.

---
description: When adding new behavior into fragile code—sprout a new method/class instead of editing existing code.
globs: 
alwaysApply: false
---
# Title: Sprout Method or Class for New Behavior

## When new logic is introduced into legacy code...
- Recommend creating a new method or class instead of modifying the legacy code directly.

## Suggestion:
"Instead of inserting new behavior here, consider creating a new method or class and calling it from this location."

## Justification:
Sprouting reduces the risk of introducing bugs into fragile or untested legacy areas.

---
description: When legacy code calls out to globals or third-party APIs—wrap those calls behind an interface for mocking.
globs: 
alwaysApply: false
---
# Title: Wrap External Dependencies for Testability

## When accessing system resources, global state, or third-party APIs...
- Recommend wrapping those in classes or interfaces under your control.

## Suggestion:
"This external call could make testing difficult. Consider abstracting it behind an interface or wrapper."

## Justification:
Wrapping dependencies allows mocking/stubbing during tests and decouples logic from infrastructure.
