# LexiTau — Text-to-SQL with Safety, Explainability, and Multi-Tenancy

LexiTau turns natural-language questions about tenant data into **read-only SQL** with clear explanations. It combines schema profiling, metadata-aware linking, and a policy layer that blocks unsafe statements before execution.

> Where does LexiTau comes from? Lexi = lexical, tau means number in Te Reo Māori.

🎥 **Project overview & demo:**

<p align="center">
  <a href="https://www.youtube.com/watch?v=Mhi9dbzRowg">
    <img src="https://img.youtube.com/vi/Mhi9dbzRowg/hqdefault.jpg" alt="Demo video">
  </a>
</p>

---

## What this project demonstrates ✅

* 🧱 **T2SQL pipeline design**: Profiling → metadata → schema linking → SQL draft → safety checks → execution → narrative explanation.
* 🧾 **Document/OCR ingestion**: Invoice/receipt parsing, line-items, confidence scores, normalization into tenant-scoped tables.
* 🏢 **Multi-tenant isolation**: Per-tenant auth + silos, per-tenant embeddings for semantic search.
* 🛡️ **Safety/guardrails**: Read-only SQL; table/column allowlists; optional row-filters; parameterized literals; clear, actionable errors.
* 🔍 **Explainability**: “Show SQL” + “Why this answer?” lineage and concise tables/charts.
* 🧪 **Testing approach**: Pytest (unit/integration) + Playwright (UX flows); explicit test inventory for auth, OCR adapters, and SQL safety.

---

## Core algorithms & components 🧩

### tl;dr ✨

Profile the DB → link the question to the right columns → draft SQL with self-checks → pass strict safety checks → return results **with** a clear explanation.

**1) Profiling → Metadata (“learn the database first”) 🧭**
Before answering questions, the system scans your tables to understand them:

* 🔢 Counts distinct values, detects common formats (dates, currencies), and typical ranges.
* 🗒️ Writes short, plain-English summaries for each column (a mini data dictionary).
* 🧮 Saves embeddings of those summaries so the planner can “find” the right columns later.

*What it looks like:*
“`invoices.total_amount` — currency, typically 5–5000; `paid` is boolean; `created_at` is a date.”
These summaries guide the model away from guesswork.

---

**2) Schema linking → SQL draft 🔗➡️🧾**
Given a natural-language question, the system figures out *which* tables/columns are relevant and drafts a SQL query:

* 🧠 Maps phrases like “unpaid invoices last quarter” → `invoices.paid = false`, date filter on `created_at`, group by customer.
* ✅ **Self-checks** joins/filters/literals against real data (e.g., does `paid` exist? is the date column actually a date?).

*What it looks like:*
Question → *“Which customers have unpaid invoices from Q2?”*
Draft SQL (simplified):

```sql
SELECT c.name, COUNT(*) AS invoice_count, SUM(i.total_amount) AS amount_due
FROM invoices i
JOIN customers c ON c.id = i.customer_id
WHERE i.paid = FALSE AND i.created_at BETWEEN '2025-04-01' AND '2025-06-30'
GROUP BY c.name
ORDER BY amount_due DESC;
```

If a column or join is wrong, the self-check catches it before execution. ✅

---

**3) Safety layer (policy engine) 🛡️**
All queries pass through guardrails **before** they hit the database:

* 🚫 **Read-only only**: blocks any DML/DDL (no `INSERT/UPDATE/DELETE/ALTER/DROP`).
* ✅ **Allowlists**: only approved tables/columns are accessible.
* 🧩 **Row-level filters**: tenant and permission scopes are injected automatically.
* 🔐 **Parameterized literals**: user inputs are bound safely (no string concatenation).
* 📣 Returns a clear error when a rule blocks something (so users learn what’s allowed).

*What it looks like:*

* Blocks: `DROP TABLE invoices;` → “Mutation statements are not allowed.”
* Enforces: automatically adds `WHERE tenant_id = :current_tenant_id` to every query.

---

**4) Explainability 🕵️‍♂️**
Every answer comes with:

* 📝 A short **narrative** (“Top 10 customers by unpaid total in Q2, read-only view”).
* 📊 A compact **table or chart**.
* 🧾 **Show SQL** (exact query run).
* 🧬 **Why this answer?** (high-level plan + IDs/hashes so results can be reproduced).

*What it looks like:*

* Narrative: “Found 127 unpaid invoices in Q2 2025; 63 customers affected. Showing top 10 by amount due.”
* Links/buttons: **Show SQL** · **Why this answer?**

---

## Research context & design choices 📚🔬

Two threads shaped the design:

* **[BIRD (BI benchmark)](https://arxiv.org/pdf/2305.03111)** pushed treating NL→SQL as a *real-database* problem—multiple domains, wide schemas, messy names—demanding stronger **schema understanding** and **robust joins/filters** (not prompt-only shortcuts).
* **[Automatic Metadata Extraction for Text-to-SQL (Shkapenyuk et al., 2025)](https://arxiv.org/abs/2505.19988)** emphasized that *knowing what’s in the DB* narrows the NL↔SQL gap; LexiTau adopted “**learn the database language**” → “**link questions to columns**,” then added production constraints: **safety** and **explanations**.

Concretely, LexiTau implements a four-stage pipeline:

1. 🧭 **Learn the DB language (profiling → metadata)**: build a plain-English data dictionary from column stats.
2. 🔗 **Schema link & draft SQL**: map NL intent to tables/columns; self-check joins/filters/literals against real data.
3. 🛡️ **Policy-guarded, read-only execution**: allowlists, optional row-filters, parameterized literals; clear error if a rule blocks.
4. 🔎 **Explainability**: short narrative + compact table/chart; “Show SQL / Why this answer?” lineage.

This evolved from a pure OSS prototype to a **hybrid** approach (Azure Form Recognizer + Azure OpenAI) for reliability while preserving the research spirit—tied together with **safety**, **explainability**, and **tenant isolation**. ⚙️

### Where the papers show up in the codebase 🗂️

**A. “Learn the database language” → Profiling + metadata + embeddings 🧭**

* Schema profiling script creates English descriptions + embeddings and upserts profiles used by the planner.
* Server-side models hold `english_description`, summaries, and `vector_embedding`—the **metadata surface** the planner consumes.

**B. “Link questions to columns” → Orchestration + value/column similarity 🔗**

* Linking flow selects candidate tables/columns from profiled metadata before planning SQL (paper Step 2).

**C. Safety & multitenancy (additions beyond the paper) 🛡️🏢**

* Read-only policy; tenant predicate injection into FROM/JOIN/WHERE; DML/DDL blocking; **fallback binds**—all covered by unit tests.

**D. Explainability (addition beyond the paper) 🔍**

* Frontend exposes **narratives + tables/charts** and **Show SQL / Why this answer?** UI.

**E. OCR ingestion (real BI workloads) 🧾**

* Azure OCR adapters + document tasks normalize into tenant-scoped tables that NL→SQL queries.

---

## Technology stack 🔧

* **Backend**: FastAPI, PostgreSQL (+pgvector), SQLAlchemy, Celery/Redis, JWT auth.
* **Frontend**: Next.js/React (App Router) with chat, documents, dashboard routes and shadcn/ui components.
* **Dev/Infra**: Docker Compose, Alembic migrations.

---

## Repo map 🗺️

```
backend/
  alembic/versions/...       # migrations (businesses, users, documents…)
frontend/
  src/app/(app)/
    chat/                    # chat UI (NL→SQL)
    documents/               # upload + review + normalized fields/line-items
    dashboard/               # post-login summary
  components/ui              # shadcn components
  components/assistant-ui    # chat rendering
docker-compose.yml
```
