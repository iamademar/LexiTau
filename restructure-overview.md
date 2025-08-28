# High-Level Blueprint (What we’ll build)

1. **Adopt a Layer-Based layout** inside `backend/app/`:

   * Split monolithic files (`models.py`, possibly mixed concerns in `schemas/`, `routers/`) into layer folders: `routers/`, `models/`, `schemas/`, `services/`, `core/`, plus `dependencies.py`.
   * Keep **Alembic** as-is (only import path tweaks if needed).
   * Keep **Celery** where it is; just update imports.
   * Ensure **tests** mirror the new layout and continue passing.

2. **Compatibility guarantees**

   * No API route path changes unless explicitly stated.
   * No DB schema change from the refactor (migrations remain source of truth).
   * Incremental PRs with green tests at every step.

---

# Phase 0 — Ground Truth & Safety Nets

**Goals:** snapshot behavior, enable refactor detection, and set strict import discipline.

* [ ] Pin the current test suite to green and export coverage baseline.
* [ ] Add/confirm `pytest` runs in CI (you have a disabled GH workflow—keep local CI via `docker-compose` or enable it later).
* [ ] Introduce **import lints** (optional; e.g., `ruff` rule to prevent cross-layer imports).

**Commands**

```bash
# local
pytest -q
pytest --maxfail=1 --disable-warnings -q --cov=app --cov-report=term-missing
```

---

# Phase 1 — Create Target Folders (No Logic Moves Yet)

**Goals:** create empty layer folders + `__init__.py` so imports won’t break later.

* [ ] Create:

  ```
  backend/app/
    routers/ __init__.py
    models/  __init__.py
    schemas/ __init__.py
    services/__init__.py
    core/    (already exists)
    dependencies.py (placeholder)
  ```
* [ ] Leave original files in place. Tests still green.

---

# Phase 2 — Split Pydantic Schemas by Resource

**Goals:** move schema classes from `app/schemas/*.py` into resource files (`user.py`, `item.py`, `document.py`, etc.) without changing names.

* [ ] Keep public import surface identical via `app.schemas.__init__`.
* [ ] Update internal imports in routers/services accordingly.

**Checks:** `pytest` stays green.

---

# Phase 3 — Extract ORM Models to `app/models/`

**Goals:** split `app/models.py` into resource modules:

* `app/models/user.py`, `business.py`, `document.py`, `extracted_field.py`, `line_item.py`, `field_correction.py`, `client.py`, `project.py`, `category.py`, etc. (reflect Alembic models present).
* Keep `app/models/__init__.py` re-exporting common names for compatibility.

**Notes:** Do **not** touch Alembic versions; they refer to DB tables, not Python import paths used at runtime.

**Checks:** run tests and a quick DB spin-up for import sanity.

---

# Phase 4 — Normalize Routers per Resource

**Goals:** each resource’s endpoints live in its own router module:

* `app/routers/auth.py` (already exists)
* `app/routers/documents.py` (already exists)
* If you expect users/items endpoints later, scaffold `users.py`, `items.py` (can be stubs for now).

**main.py wiring**

* Import routers from `app.routers.*`
* Include with versioned prefixes if desired (keep current paths to avoid breaking clients).

---

# Phase 5 — Service Layer Hardening

**Goals:** keep **all** business logic out of routers:

* Keep `app/services/azure_form_recognizer.py`, `blob.py`, `field_normalizer.py` where they are.
* If any router contains business logic, move it into `app/services/{resource}_service.py`.
* Make services depend on **interfaces** (function signatures), not on router objects.

**Checks:** unit tests for services (mocks for Azure/Firebase/etc.) already exist—ensure they still pass.

---

# Phase 6 — Dependencies Module

**Goals:** centralize `Depends(...)` factories:

* Move `get_db` (currently in `app/db.py`) re-exports into `app/dependencies.py`, or keep `db.py` and expose facades in `dependencies.py`.
* Centralize `auth` dependencies (e.g., `get_current_user`) behind `dependencies.py`, reusing existing logic in `app/auth.py`.

**Outcome:** routers import from `app.dependencies` only.

---

# Phase 7 — Core Settings/DB/Security

**Goals:** confirm:

* `app/core/settings.py` remains the single source for config (you already use it for Celery and Azure).
* Split `app/db.py` into `app/core/database.py` **only if** it’s purely infra. If `db.py` is tightly coupled to model metadata, keep it and merely re-export.

**Outcome:** `app/core/` contains infra (settings, database, security), `app/dependencies.py` provides DI glue.

---

# Phase 8 — Tests Layout & Coverage

**Goals:** mirror resources:

```
backend/tests/
  test_auth.py
  test_documents.py
  test_field_normalizer.py
  ... (already present)
```

* Keep test names/paths; update imports if needed.
* Add new tests for any newly split modules (e.g., `models/` imports).

**Checks:** coverage shouldn’t regress.

---

# Phase 9 — Celery & Tasks

**Goals:** after split:

* Ensure `celery_app` imports still resolve (`app.core.celery` depends on `app.core.settings`).
* If tasks import models/services, update paths.

**Checks:** `pytest -k test_tasks` and any task unit tests.

---

# Phase 10 — Docker/Compose & Alembic Sanity

**Goals:** imports still resolve in containers, migration commands still work.

**Checks**

```bash
docker-compose up -d
docker-compose exec fastapi pytest -q
docker-compose exec fastapi alembic upgrade head
```

---

## Iterative Chunks → Micro-Steps (Right-Sized)

Each chunk below is sized to be merged independently with tests green.

### Chunk A — Scaffolding (no logic moves)

1. Create folders/files (`routers/`, `models/`, `schemas/`, `services/`, `dependencies.py`) with `__init__.py`.
2. Add a smoke test importing each new package.
3. Run tests.

### Chunk B — Schemas split

1. Move auth schemas into `schemas/auth.py` (already there), then add `schemas/user.py`, `schemas/item.py` stubs.
2. Export via `schemas/__init__.py`.
3. Adjust imports in routers/services.
4. Run tests.

### Chunk C — Models split (safe subset first)

1. Move `User`, `Business` to `models/user.py` and `models/business.py`.
2. Update import sites (`auth.py`, tests).
3. Run tests.
4. Move `Document` to `models/document.py` (UUID + enums reflected by Alembic).
5. Update import sites (`routers/documents.py`, services).
6. Run tests.
7. Move the remaining models (`ExtractedField`, `LineItem`, `FieldCorrection`, `Client`, `Project`, `Category`) to files named after them.
8. Update imports & run tests.

### Chunk D — Dependencies consolidation

1. Add `dependencies.py` with `get_db` re-export & auth helpers (wrapping existing functions).
2. Point routers to `dependencies`.
3. Run tests.

### Chunk E — Router cleanup

1. Ensure routers import only `schemas`, `services`, `dependencies`.
2. Move any lingering logic into `services`.
3. Run tests.

### Chunk F — Core tidy

1. If desired, move `db.py` → `core/database.py` (optional).
2. Update imports in `dependencies.py` & tests.
3. Run tests.

### Chunk G — Celery/task import check

1. Run task unit tests; fix imports.
2. Quick manual task call in REPL if useful.
3. Run tests.

### Chunk H — Docs & CI

1. Update `CLAUDE.MD` with new file structure and dev notes.
2. (Optional) Enable CI workflow or keep local.

---

# Concrete File Map (Before → After)

* `app/models.py` → `app/models/{user,business,document,extracted_field,line_item,field_correction,client,project,category}.py`
* `app/db.py` → keep (or `app/core/database.py`), re-export in `dependencies.py`
* `app/auth.py` → keep; expose `get_current_user` via `dependencies.py` for routers
* `app/routers/*` → keep and add more as needed (`users.py`, `items.py`)
* `app/schemas/*` → split per resource (`user.py`, `item.py`, already have `auth.py`, `document.py`)
* `app/services/*` → keep; add `{user_service.py,item_service.py}` as needed
* `app/core/*` → keep (`settings.py`, `celery.py`, add `database.py` if you move `db`)

---

# Prompts for a Code-Gen LLM (Test-Driven, Sequenced)

Use these **one at a time**, committing after each. Each ends with tests.

## Prompt 1 — Create Layer Folders & Stubs

```
You are working in a FastAPI repo under backend/app. 
Goal: scaffold a Layer-Based structure without moving logic.

Tasks:
1) Create folders: routers, models, schemas, services — each with __init__.py.
2) Create app/dependencies.py with a placeholder function:
   def ping() -> str: return "ok"
3) Add a minimal test file tests/test_layout_scaffold.py that imports:
   - app.routers, app.models, app.schemas, app.services, app.dependencies
   and asserts app.dependencies.ping() == "ok".

Do not modify any existing logic files. Ensure tests pass.
```

## Prompt 2 — Split Schemas by Resource (non-breaking)

```
Goal: split Pydantic schemas by resource while keeping public API stable.

Tasks:
1) Create app/schemas/user.py and app/schemas/item.py with minimal placeholder classes:
   - class UserBase(BaseModel): email: EmailStr
   - class ItemBase(BaseModel): name: str
2) In app/schemas/__init__.py, re-export needed classes from auth.py, document.py, user.py, item.py.
3) Update any imports in routers/services to import from app.schemas (package), not per-file paths.
4) Add tests asserting from app.schemas import UserBase, ItemBase works.

Run tests.
```

## Prompt 3 — Move User & Business models first

```
Goal: start splitting ORM models safely.

Tasks:
1) Move User and Business SQLAlchemy models from app/models.py into:
   - app/models/user.py (User)
   - app/models/business.py (Business)
2) In app/models/__init__.py, re-export User and Business.
3) Update import sites that reference app.models.User/Business to the package alias (from app import models; models.User).
4) Add tests in tests/test_models.py to import and instantiate User/Business with minimal fields (no DB commit).
5) Run tests and fix import paths until green.
```

## Prompt 4 — Move Document model

```
Goal: move Document ORM model.

Tasks:
1) Move Document model into app/models/document.py.
2) Re-export Document in app/models/__init__.py.
3) Update routers/services that reference Document to use package alias.
4) Add a minimal test that creates a Document instance with required enum fields consistent with Alembic types.
5) Run tests.
```

## Prompt 5 — Move remaining models

```
Goal: move remaining ORM models to separate modules:
- ExtractedField, LineItem, FieldCorrection, Client, Project, Category

Tasks:
1) Create files in app/models for each model and move class definitions.
2) Re-export all in app/models/__init__.py.
3) Update import sites.
4) Add a smoke test that imports each moved model and checks __name__.

Run tests.
```

## Prompt 6 — Centralize dependencies

```
Goal: centralize DI helpers.

Tasks:
1) In app/dependencies.py, add:
   - from app.db import get_db as get_db_session   # or from app.core.database if moved
   - from app.routers.auth import get_current_user  # or from app.auth if that’s where it lives
   and re-expose them as get_db and get_current_user.

2) Update routers to import from app.dependencies:
   from app.dependencies import get_db, get_current_user

3) Add tests hitting an authenticated endpoint using TestClient to ensure token flow still works.

Run tests.
```

## Prompt 7 — Router cleanup (service boundary)

```
Goal: keep routers thin.

Tasks:
1) Inspect app/routers/*.py for any business logic; create services/{resource}_service.py to hold it.
2) Move logic and have routers call service functions.
3) Add/adjust unit tests for moved functions in services.
4) Run tests.
```

## Prompt 8 — Optional: move db.py → core/database.py

```
Goal: infra under core.

Tasks:
1) Move app/db.py to app/core/database.py (if desired).
2) Update app/dependencies.py to import get_db from core.database.
3) Update import sites.
4) Run all tests.

If this causes friction with tests or fixtures, revert and keep app/db.py (but still re-export via dependencies).
```

## Prompt 9 — Celery and tasks import verification

```
Goal: ensure Celery tasks import paths are still valid.

Tasks:
1) Run unit tests that touch app.tasks (e.g., test_tasks.add/multiply).
2) Fix import paths in tasks if needed.
3) Add one test that calls add.delay(2,3) but mock Celery app to avoid broker dependency.

Run tests.
```

## Prompt 10 — Docs & CI polish

```
Goal: documentation.

Tasks:
1) Update CLAUDE.MD: include the Layer-Based file tree and brief "where things live".
2) (Optional) Enable .github/workflows/ci.yml by renaming from ci.yml.disabled and validate it locally if possible.

No code changes; just docs. Ensure repo still green.
```

---

## Test Strategy (each PR)

* **Unit tests:** models import/instantiate, schemas import, routers endpoints (via `TestClient`), services with mocks (Azure DI already mocked in your tests).
* **Mutation point:** after each move, run `pytest -q`. If something breaks, it’s likely an import path—fix and re-run.
* **No DB changes:** Alembic stays untouched; we’re only rearranging Python modules.

---

## Final Target Tree (adapted to your repo)

```
backend/
└── app/
    ├── main.py
    ├── routers/
    │   ├── __init__.py
    │   ├── auth.py
    │   └── documents.py
    ├── models/
    │   ├── __init__.py
    │   ├── user.py
    │   ├── business.py
    │   ├── document.py
    │   ├── extracted_field.py
    │   ├── line_item.py
    │   ├── field_correction.py
    │   ├── client.py
    │   └── project.py
    ├── schemas/
    │   ├── __init__.py
    │   ├── auth.py
    │   ├── user.py
    │   ├── item.py
    │   └── document.py
    ├── services/
    │   ├── __init__.py
    │   ├── azure_form_recognizer.py
    │   ├── field_normalizer.py
    │   ├── blob.py
    │   └── document_service.py   # as needed
    ├── core/
    │   ├── __init__.py
    │   ├── settings.py
    │   ├── celery.py
    │   ├── database.py           # (optional move of db.py)
    │   └── security.py           # (if/when you add)
    ├── dependencies.py
    ├── auth.py                   # can remain, with deps re-exported
    ├── db.py                     # keep or move to core/
    ├── enums.py
    └── tasks/
        ├── __init__.py
        ├── document_tasks.py
        └── test_tasks.py
```

