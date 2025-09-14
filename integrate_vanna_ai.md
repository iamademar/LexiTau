# Vanna AI Integration Spec (FastAPI, v0.7.9)

This is a complete, hand-off spec for integrating **Vanna AI v0.7.9** into your FastAPI API.

---

## 0) Snapshot of Key Decisions

* **Vanna**: `vanna==0.7.9`, `from vanna.remote import VannaDefault`, **no training**.
* **Execution**: Reuse **sync** SQLAlchemy engine: `app.db.engine`. All queries go through our pool + policy guards.
* **Endpoint**: `POST /vanna/analysis` (visible in OpenAPI, no versioning, no feature gates).
* **Tenant**: **Server-side** derivation (`current_user.active_business_id`). Client **must not** send `business_id`.
* **Policies**: strict allow-list, per-alias tenant filter, function deny-list, disallow set ops/LATERAL/recursive CTEs.
* **SELECT**\*: auto-expand with aliasing rules + exclusions (star-only).
* **ORDER BY**: smart heuristic with conservative fallbacks.
* **Timeouts & GUCs**: statement timeout, read-only transaction, search\_path, lock/idle timeouts.
* **Errors**: 403 for guard denials; 504 timeout; 500 other DB; optional “always-200” toggle. **Prod sanitizes** messages.
* **Audit**: `vanna_audit` row for every call; keep forever for now.
* **Serialization**: JSON-safe (Decimal→string, TIMESTAMP→ISO-UTC Z, big BIGINT→string, etc.).
* **Tests**: Postgres integration suite + opt-in **real Vanna smoke**; no artificial 500 test.
* **No** pagination/caching/rate-limits/schema endpoint/RLS/role overrides.

---

## 1) Dependencies

```
vanna==0.7.9
sqlglot>=25,<26
```

---

## 2) Settings (env / `app/core/settings.py`)

```python
# Required
VANNA_MODEL = "my_model"
VANNA_API_KEY = ""  # set in env

# Allow-list
VANNA_ALLOWED_SCHEMAS = ["public"]
VANNA_ALLOWED_TABLES = [
  "public.documents","public.line_items","public.extracted_fields",
  "public.clients","public.projects","public.categories",
]

# Tenant scope symmetry
VANNA_TENANT_COLUMN = "business_id"
VANNA_TENANT_PARAM  = "business_id"

# Defaults
VANNA_DEFAULT_TIMEOUT_S = 5
VANNA_DEFAULT_ROW_LIMIT = 500
VANNA_WORK_MEM = None  # e.g. "64MB"

# SELECT * expansion
VANNA_EXPAND_SELECT_STAR = True
VANNA_EXPAND_EXCLUDE_TYPES = ["bytea"]
VANNA_EXPAND_EXCLUDE_NAME_PATTERNS = ["password","secret","api[_-]?key","token"]

# Per-table excludes (affect SELECT * only; explicit selects still allowed)
VANNA_EXPAND_EXCLUDE_COLUMNS = [
  "public.users.password_hash",
  "public.documents.file_url",
  "public.users.email",
  "public.extracted_fields.value",
  "public.field_corrections.original_value",
  "public.field_corrections.corrected_value",
  "public.line_items.description",
]

# Tenant per alias (all allowed tables are required)
VANNA_TENANT_ENFORCE_PER_TABLE = True
VANNA_TENANT_REQUIRED_TABLES = [
  "public.documents","public.line_items","public.extracted_fields",
  "public.clients","public.projects","public.categories",
]

# Function deny-list (case-insensitive regex)
VANNA_FUNCTION_DENYLIST = [
  r"^pg_sleep(?:_for|_until)?$",
  r"^dblink.*$",
  r"^pg_(?:read|read_binary|write|stat)_file$",
  r"^pg_ls_dir$",
  r"^pg_logdir_ls$",
  r"^lo_.*$",
  r"^pg_terminate_backend$",
  r"^pg_cancel_backend$",
  r"^pg_reload_conf$",
  r"^pg_rotate_logfile$",
  r"^set_config$",
  r"^pg_advisory_(?:xact_)?lock$",
  r"^pg_try_advisory_(?:xact_)?lock$",
  r"^pg_promote$",
  r"^pg_checkpoint$",
  r"^pg_stat_reset.*$",
]

# Auditing & error mapping
VANNA_AUDIT_ENABLED = True
VANNA_AUDIT_REDACT  = False
VANNA_ALWAYS_200_ON_ERRORS = False

# Environment (drives error sanitization)
ENVIRONMENT = "dev"  # "prod" or "production" → sanitized messages
```

> **.env** must define `VANNA_MODEL` & `VANNA_API_KEY`. Others have sensible defaults.

---

## 3) Service: `app/services/vanna_service.py`

### 3.1 Vanna bootstrap + controlled execution

* Instantiate once and reuse.
* **Wire `VN.run_sql` to our guarded executor** (for any Vanna-internal calls). The wrapper **requires** a `business_id` in params; if absent, it raises (avoids unscoped execution outside the `/vanna/analysis` flow).

Pseudocode:

```python
from vanna.remote import VannaDefault
from app.db import engine as ENGINE
from app.core.settings import get_settings
# ... import guards & executor defined below ...

def get_vanna() -> VannaDefault:
    st = get_settings()
    vn = VannaDefault(model=st.VANNA_MODEL, api_key=st.VANNA_API_KEY)

    # Guarded run_sql for any Vanna-initiated executions (rare today, but safe)
    def _vn_run_sql(sql: str, params: dict | None = None):
        params = params or {}
        # Enforce tenant param presence (do NOT silently inject here)
        if st.VANNA_TENANT_PARAM not in params:
            raise RuntimeError("business_id is required for VN.run_sql")
        # We assume SQL is already guarded upstream; still use safe GUCs/timeout defaults
        _, rows, *_ = guarded_run_sql(
            ENGINE, sql, params,
            timeout_s=st.VANNA_DEFAULT_TIMEOUT_S,
            work_mem=st.VANNA_WORK_MEM,
        )
        return rows  # Vanna typically expects rows-only
    vn.run_sql = _vn_run_sql

    return vn

VN = get_vanna()
```

> **Note**: The main endpoint already applies all guards & injects tenant param. The `VN.run_sql` hook is defensive for any library-internal eval.

### 3.2 Guarding & rewriting

* **Parse with sqlglot** (Postgres dialect).
* **Reject** non-SELECT, set ops, LATERAL, WITH RECURSIVE.
* **Allow-list** schemas/tables.
* **Auto-expand SELECT**\*:

  * Aliasing **B**: `<alias>_<column>` if alias present; else `<table>_<column>`.
  * Exclude `bytea`, sensitive name patterns, and configured FQ columns.
  * Auto-quote only source identifiers when reserved/unsafe; aliases are unquoted, `lower_snake_case`.
* **Function deny-list** (regex, case-insensitive).
* **Tenant**:

  * Require global presence of `business_id = :business_id`.
  * **Per-alias**: each allowed table alias must include `<alias>.business_id = :business_id` in WHERE or JOIN ON.
* **ORDER BY** (only if missing):

  * With **GROUP BY** → `ORDER BY <first group expr> ASC`.
  * With **DISTINCT** → `ORDER BY 1 ASC`.
  * Else, pick first tenant-bearing alias and try: `created_at DESC`, `issued_on DESC`, `updated_at DESC`, `date DESC`, `id ASC`. If none exist → `ORDER BY 1 ASC`.
* **LIMIT** (only if missing): inject `row_limit + 1` to detect truncation.

### 3.3 Executor safety

Every run uses:

```
SET TRANSACTION READ ONLY;
SET LOCAL search_path = 'public';
SET LOCAL lock_timeout = '1s';
SET LOCAL idle_in_transaction_session_timeout = '5s';
SET LOCAL statement_timeout = '<timeout_ms>';
[SET LOCAL work_mem = '<size>'];
```

### 3.4 Serialization & column metadata

* **Cell serialization**:

  * Decimal/Numeric → string
  * Bigint > 2^53−1 → string
  * Timestamptz → ISO-8601 UTC (`Z`)
  * Date → `YYYY-MM-DD`
  * UUID → string
  * JSON/Array → native JSON / list
  * Null → null

* **`meta.columns` when `trace=true`**:

  * `name` (cursor column name)
  * `db_type` (best-effort via `pg_type` OID lookup; may be null)
  * `py_type` (first non-null raw value in the returned page)
  * `nullable` (true if any null in the returned page)
  * `serialized_as` (string/number/iso-8601-utc/date/array/object/null)

---

## 4) Router: `app/routers/vanna.py`

### 4.1 Mount

```python
from app.routers import vanna as vanna_router
app.include_router(vanna_router.router)  # prefix /vanna, visible in /docs
```

### 4.2 Contract

#### Request (exactly one of `question` | `sql`)

```json
{
  "question": "string",
  "sql": "string",
  "params": { "named_param": "value" },  // server injects "business_id"
  "row_limit": 500,
  "timeout_s": 5,
  "dry_run": false,
  "trace": false,
  "hints": ["optional schema hints the caller wants VN to consider"]
}
```

#### Response (success)

```json
{
  "ok": true,
  "sql": "final guarded SQL",
  "columns": ["..."],
  "rows": [[...]],
  "row_count": 123,
  "truncated": true,
  "execution_ms": 142,
  "trace_id": "uuid",
  "trace": {
    "guards": ["star_expanded","tenant_per_alias_ok","order_by_created_at","limit_injected"],
    "star": { "star_expanded": true, "excluded": {"public.documents": ["file_url"]} }
  },
  "warnings": ["Result truncated to 500 rows"],
  "meta": {
    "columns": [
      {"name":"documents_id","db_type":"int8","py_type":"int","nullable":false,"serialized_as":"number"}
    ]
  }
}
```

#### Response (error)

```json
{
  "ok": false,
  "error": {
    "type": "GuardError | GenerationError | TimeoutError | ExecutionError",
    "message": "sanitized in prod; raw in non-prod",
    "details": { "violations": ["missing_tenant_scope_for_alias:d"] }
  },
  "sql": "guarded SQL if generation succeeded",
  "trace_id": "uuid"
}
```

### 4.3 Status mapping

* **403** Guard/policy denials (incl. client trying to pass `business_id`)
* **422** Validation (e.g., both `question` and `sql`)
* **400** Malformed JSON
* **504** Timeout (Postgres `statement_timeout`)
* **500** Other DB/generation failures
* Optional: **200** for all errors if `VANNA_ALWAYS_200_ON_ERRORS=true` (body still `"ok": false`)

### 4.4 Behavior notes

* If `question` is provided, we call `VN.generate_sql(question, hints=...)`, then guard + (optionally) execute. No training involved.
* Before execution we prefix a **noop SQL comment** for DB log correlation:

  ```
  /* vanna trace_id=<uuid> user_id=<uid> business_id=<bid> */
  ```
* The endpoint **injects `business_id`** into params (from auth context). If client supplies it, we return **403** with a `GuardError`.
* `dry_run=true` returns guarded SQL and metadata **without executing**.
* `trace=true` adds guard notes, star info, and `meta.columns`.

---

## 5) Auditing

### 5.1 Table & indexes

```sql
CREATE TABLE IF NOT EXISTS vanna_audit (
  id                     BIGSERIAL PRIMARY KEY,
  request_id             UUID            NOT NULL,
  user_id                BIGINT          NOT NULL,
  business_id            BIGINT          NOT NULL,
  vanna_model            TEXT            NOT NULL,
  question               TEXT            NOT NULL,
  sql                    TEXT,
  executed               BOOLEAN         NOT NULL DEFAULT FALSE,
  http_status            INT             NOT NULL,
  ok                     BOOLEAN         NOT NULL,
  error_type             TEXT,
  error_message          TEXT,
  row_limit_applied      INT,
  statement_timeout_ms   INT,
  row_count              INT,
  guard_flags            JSONB,
  meta                   JSONB,
  started_at             TIMESTAMPTZ     NOT NULL DEFAULT now(),
  finished_at            TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_vanna_audit_biz_time   ON vanna_audit (business_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_vanna_audit_user_time  ON vanna_audit (user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_vanna_audit_ok         ON vanna_audit (ok);
CREATE INDEX IF NOT EXISTS idx_vanna_audit_http_status ON vanna_audit (http_status);
```

### 5.2 What we write

* `request_id` (also returned as `trace_id`)
* `user_id`, `business_id`, `vanna_model`
* `question`, `sql` (final guarded; **without** the log comment prefix)
* `executed` (false for dry-run/guard failures)
* `http_status`, `ok`, `error_type`
* `error_message` (always **raw**; sanitized only for client if prod)
* `row_limit_applied`, `statement_timeout_ms`, `row_count`
* `guard_flags` (notes, star exclusions, tenant checks)
* `meta` (route flags like dry\_run/trace)
* `started_at`, `finished_at`
  **Retention**: keep forever (for now).

---

## 6) Tests

### 6.1 Integration suite (Postgres)

* Location: `tests/integration/`
* Uses your `postgres_test` Docker DB (seed fixture with `business_id=1` and a few rows for `business_id=2`).
* Covers:

  * Guard denials: cross-schema, missing tenant, **per-alias** tenant
  * `SELECT *` expansion (aliasing + exclusions)
  * Function deny-list
  * SQL feature policy: CTE ✅, **no** recursive/LATERAL/set ops
  * Serialization + `meta.columns` when `trace=true`
  * Status mapping (403/504/500) and audit row creation
* Transaction-per-test via quick truncate+reseed
* Timeout simulation via `generate_series(...)` + very low `timeout_s`

### 6.2 Real Vanna “smoke” (opt-in)

* `tests/integration/test_vanna_smoke.py`
* Skipped unless:

  ```
  VANNA_API_KEY=<test-key>
  VANNA_SMOKE=1
  ```
* Calls `VN.generate_sql(...)` and asserts non-empty SQL (connectivity sanity).

### 6.3 How to run

```bash
docker compose up -d postgres_test redis
pytest tests/integration -q
# Optional smoke:
export VANNA_API_KEY=... && export VANNA_SMOKE=1
pytest tests/integration/test_vanna_smoke.py -q
```

---

## 7) Runbook

1. **Install deps**

```bash
pip install vanna==0.7.9 sqlglot>=25,<26
```

2. **Configure env**

* Set `VANNA_MODEL`, `VANNA_API_KEY`.
* Optionally tweak guard settings above.

3. **DB migration**

```bash
alembic revision -m "add vanna_audit"
# paste the DDL above into the migration
alembic upgrade head
```

4. **Wire router**

```python
from app.routers import vanna as vanna_router
app.include_router(vanna_router.router)
```

5. **Run the stack** (per CLAUDE.MD), open `http://localhost:8000/docs`.

6. **Examples**

* Explicit SQL:

```bash
curl -X POST http://localhost:8000/vanna/analysis \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer <jwt>' \
  -d '{"sql":"SELECT d.id FROM public.documents d WHERE d.business_id=:business_id ORDER BY 1 LIMIT 10"}'
```

* NL question:

```bash
curl -X POST http://localhost:8000/vanna/analysis \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer <jwt>' \
  -d '{"question":"List documents in the last 7 days"}'
```

---

## 8) Non-Goals (now)

No schema endpoint, caching, rate limits, pagination, feature gating, OpenAPI hiding, RLS, role-based overrides, or auto-run migrations. No extra observability beyond audit (you can add Prometheus later).

---

### Implementation Notes & Gotchas

* **VN.run\_sql wrapper**: It’s intentionally strict—if a caller forgets to pass `business_id`, it raises. The main endpoint always injects `business_id` before execution; keep it that way.
* **Per-table excludes**: Apply only to `SELECT *` expansion; explicit columns are **allowed** (as specified).
* **Sanitized errors**: In `prod`, client messages are short; **audit** always stores the raw DB/generation error text.
* **Heuristic ORDER BY**: Only inject when missing. Conservatively uses group expr or safe fallbacks to avoid invalid SQL in aggregates.

## Architecture & Modules

## 

- **Service layer:** `app/services/vanna_service.py`
    - Vanna bootstrap (`VannaDefault`, v0.7.9) using env.
    - Guard & rewrite pipeline (sqlglot):
        - Non-SELECT rejection
        - Feature policy (allow: non-recursive CTE, subqueries, aggs, window fns, casts/CASE; deny: set ops, LATERAL, WITH RECURSIVE)
        - Function deny-list (regex, case-insensitive; includes pg_sleep, dblink, file/LO, backend control, advisory locks, promote/checkpoint, pg_stat_reset*, set_config)
        - Schema/table allow-list (public + specific tables)
        - `SELECT *` expansion:
            - Alias style **B**: `<alias>_<column>` else `<table>_<column>`
            - Exclude `bytea`, sensitive name patterns, and per-table FQ excludes
            - Explicit selection of excluded columns is allowed
        - Tenant enforcement:
            - global presence of `business_id = :business_id`
            - **per-alias** `<alias>.business_id = :business_id`
        - ORDER BY heuristic (only if missing): group expr ASC (if GROUP BY), else DISTINCT→1 ASC, else try created_at/issued_on/updated_at/date/id, fallback 1 ASC
        - LIMIT injection (`row_limit + 1`) for truncation detection
    - Guarded executor with safety GUCs (READ ONLY, search_path public, lock/idle timeouts, statement_timeout, optional work_mem)
    - JSON-safe serializer
    - `meta.columns` builder (when `trace=true`)
    - Defensive `VN.run_sql` wrapper that requires `business_id` param
- **API router:** `app/routers/vanna.py`
    - `POST /vanna/analysis`: accepts `question` **or** `sql`; derives server-side `business_id`; dry-run option; `trace` option; produces consistent response payload; status mapping; prod sanitization
    - Executes SQL with prefixed comment `/* vanna trace_id=… user_id=… business_id=… */`
- **Audit:** `vanna_audit` table + write path. Keep forever for now.
- **Tests:** Postgres integration + optional real Vanna smoke test.