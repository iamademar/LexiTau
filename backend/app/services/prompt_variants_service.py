# backend/app/services/prompt_variants.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Tuple, Callable, Optional
from collections import defaultdict
import re
import time
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

# If you already have this in your repo, import that instead:
# from app.services.embedding_service import embedding_service
# For clarity we expect an object with: await embedding_service.generate_embedding(text: str) -> List[float]
EmbeddingServiceProtocol = Any  # duck-typed

logger = logging.getLogger(__name__)

# -------------------------
# Public API
# -------------------------

SchemaKind = Literal["focused", "full"]
ProfileKind = Literal["minimal", "maximal", "full_profile"]

@dataclass
class ColumnCtx:
    name: str
    short_summary: str | None
    long_summary: str | None
    english_description: str | None

@dataclass
class TableCtx:
    name: str
    alias: str
    columns: List[ColumnCtx]

@dataclass
class PromptVariant:
    name: str  # e.g., "focused_minimal"
    schema_kind: SchemaKind
    profile_kind: ProfileKind
    messages: List[Dict[str, str]]   # OpenAI-style [{"role","content"},...]
    context_preview: Dict[str, Any]  # for debugging/telemetry (focused tables, etc.)

@dataclass
class FiveVariants:
    question: str
    variants: List[PromptVariant]

# NEW: one raw LLM response per variant
@dataclass
class VariantLLMResponse:
    name: str
    schema_kind: SchemaKind
    profile_kind: ProfileKind
    response: Any            # raw OpenAI SDK response object
    latency_ms: int
    context_preview: Dict[str, Any]

# NEW: final return shape when also calling the LLM
@dataclass
class FiveLLMResponses:
    question: str
    results: List[VariantLLMResponse]


SYSTEM_RULES = """You are an expert data analyst who writes safe, correct PostgreSQL.
Rules:
- Read-only: SELECT queries only. Never write DDL/DML (no CREATE/INSERT/UPDATE/DELETE/TRUNCATE).
- Use only the tables and columns provided in CONTEXT. If something is not in CONTEXT, do not use it.
- Qualify columns with table aliases. Use explicit JOINs.
- Choose literals that match the column formats/examples in LONG SUMMARIES (e.g., 'YYYY-YYYY', ISO dates).
- Prefer standard SQL; avoid vendor-specific functions unless necessary for PostgreSQL.
- If multiple interpretations are possible, choose the most likely reading from the given CONTEXT.
- Output SQL only. No explanations, comments, or markdown.

Schema integrity:
- projects.id is INT
- documents.id is UUID
- documents.project_id (INT) references projects.id
- line_items.document_id (UUID) references documents.id
- Never join projects.id = documents.id
- Always join projects.id = documents.project_id

Document types:
- documents.document_type is an ENUM with only two valid values: 'INVOICE' and 'RECEIPT'
- If user asks about invoices, always use 'INVOICE' (not 'INV')
- If user asks about receipts, always use 'RECEIPT' (not 'REC' or 'RCPT'

Tenant scoping:
- Always filter every query with `business_id = $business_id`
- Never hard-code tenant IDs like `business_id = 1`
"""

# --------------------------------------------------------------------------------------
# High-level entrypoint that calls OpenAI once per variant and returns RAW responses
# --------------------------------------------------------------------------------------
async def generate_raw_responses_for_five_variants(
    *,
    db: Session,
    question: str,
    embedding_service: EmbeddingServiceProtocol,
    llm_client: Any,                     # e.g., AsyncOpenAI()
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
    max_tokens: int = 800,
    # Focused schema knobs (paper-aligned defaults)
    M: int = 50,
    P: int = 3,
    T: int = 6,
    include_full_schema_cap: int | None = None,
    trim_long_to_examples: bool = True,
    # Optional callback to persist each raw result (sync is fine here)
    save_result: Optional[Callable[[VariantLLMResponse], None]] = None,
) -> FiveLLMResponses:
    """
    1) Build the five prompt variants
    2) For each variant, call OpenAI once
    3) Optionally persist each raw response via save_result(...)
    4) Return all five RAW responses (no SQL extraction)
    """
    prompt_bundle = await build_five_prompt_variants(
        db=db,
        question=question,
        embedding_service=embedding_service,
        M=M, P=P, T=T,
        include_full_schema_cap=include_full_schema_cap,
        trim_long_to_examples=trim_long_to_examples,
    )

    out: List[VariantLLMResponse] = []

    for v in prompt_bundle.variants:
        t0 = time.time()
        resp = await llm_client.chat.completions.create(
            model=model,
            messages=v.messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = int((time.time() - t0) * 1000)

        if resp.choices and resp.choices[0].message:
            content = resp.choices[0].message.content

        vr = VariantLLMResponse(
            name=v.name,
            schema_kind=v.schema_kind,
            profile_kind=v.profile_kind,
            response=resp,  # RAW OpenAI response object
            latency_ms=latency_ms,
            context_preview=v.context_preview,
        )

        if save_result:
            try:
                save_result(vr)
            except Exception:
                # Don't block if saving fails
                pass

        out.append(vr)

    return FiveLLMResponses(question=question, results=out)

# -------------------------
# Prompt builder (unchanged)
# -------------------------

async def build_five_prompt_variants(
    *,
    db: Session,
    question: str,
    embedding_service: EmbeddingServiceProtocol,
    # Focused schema knobs (paper-aligned defaults)
    M: int = 50,     # initial columns from vector search
    P: int = 3,      # max cols per table
    T: int = 6,      # max tables
    include_full_schema_cap: int | None = None,  # optional safety cap for "full" variants
    trim_long_to_examples: bool = True,          # keep long summaries concise (format + examples)
) -> FiveVariants:
    """
    Returns five OpenAI-ready prompt variants for the given question.
    """
    # 1) Focused schema via semantic search on short_summary embedding (pgvector)
    q_emb = await _embed_question(embedding_service, question)
    focused_tables = _focused_schema_from_vector_search(
        db=db,
        q_emb=q_emb,
        question=question,
        M=M,
        P=P,
        T=T,
        trim_long_to_examples=trim_long_to_examples,
    )

    # 2) Full schema (optionally capped)
    full_tables = _full_schema(db, cap_tables=include_full_schema_cap, trim_long_to_examples=trim_long_to_examples)

    # 3) Render the five contexts and messages
    variants: List[PromptVariant] = []
    combos: List[Tuple[SchemaKind, ProfileKind]] = [
        ("focused", "minimal"),
        ("focused", "maximal"),
        ("full",    "minimal"),
        ("full",    "maximal"),
        ("focused", "full_profile"),
    ]

    for schema_kind, profile_kind in combos:
        tables = focused_tables if schema_kind == "focused" else full_tables
        context_text = _render_context_block(tables=tables, profile_kind=profile_kind)

        messages = [
            {"role": "system", "content": SYSTEM_RULES},
            {"role": "assistant", "content": context_text},
            {"role": "user", "content": f"Question:\n{question}"},
        ]

        name = f"{schema_kind}_{profile_kind}"
        variants.append(
            PromptVariant(
                name=name,
                schema_kind=schema_kind,
                profile_kind=profile_kind,
                messages=messages,
                context_preview={
                    "table_count": len(tables),
                    "tables": [
                        {
                            "name": t.name,
                            "alias": t.alias,
                            "columns": [c.name for c in t.columns],
                        }
                        for t in tables
                    ],
                },
            )
        )

    # Log the generated prompt variants
    logger.info("-------------------------- Generated prompt variants ----------------------------")
    for variant in variants:
        logger.info(f"Generated prompt variant '{variant.name}':")
        for i, message in enumerate(variant.messages):
            logger.info(f"  Message {i+1} ({message['role']}): {message['content'][:200]}{'...' if len(message['content']) > 200 else ''}")
    logger.info("-------------------------- Generated prompt variants ----------------------------")
    return FiveVariants(question=question, variants=variants)

# -------------------------
# Focused & full schema assembly
# -------------------------

async def _embed_question(embedding_service: EmbeddingServiceProtocol, text_q: str) -> List[float]:
    emb = await embedding_service.generate_embedding(text_q)
    if not emb:
        raise ValueError("Failed to generate embedding for question")
    return emb

def _focused_schema_from_vector_search(
    *,
    db: Session,
    q_emb: List[float],
    question: str,
    M: int,
    P: int,
    T: int,
    trim_long_to_examples: bool,
) -> List[TableCtx]:
    """
    Focused schema = top-M semantic matches on short_summary (+) literal-aware bump
    using top_k_values substring search. Then cap to P cols/table and T tables.
    """
    # --- 1) Top-M columns by vector similarity (pgvector <->) ---
    vector_str = "[" + ",".join(map(str, q_emb)) + "]"
    sql_query = f"""
        SELECT id, database_name, table_name, column_name,
               short_summary, long_summary, english_description,
               top_k_values
        FROM column_profiles
        WHERE vector_embedding IS NOT NULL
        ORDER BY vector_embedding <-> '{vector_str}'::vector
        LIMIT :m
    """
    rows = db.execute(text(sql_query), {"m": M}).mappings().all()

    by_table: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)

    # Track explicit ranks to avoid list.index() on dict copies (bug fix).
    ranked_rows: List[Dict[str, Any]] = []
    for rank, r in enumerate(rows):
        d = dict(r)
        d["_rank"] = rank
        d["_literal_hit"] = False
        ranked_rows.append(d)
        key = (d["database_name"], d["table_name"])
        by_table[key].append(d)

    # --- 2) Literal-aware bump: pull columns whose top_k_values match literals ---
    literals = _extract_literals(question)
    lit_by_table = _literal_columns(db, literals, limit_per_lit=20) if literals else {}

    literal_tables: set[Tuple[str, str]] = set()
    for key, cols in lit_by_table.items():
        literal_tables.add(key)
        for d in cols:
            d = dict(d)
            d.setdefault("_rank", 10**9)      # large rank for stable ordering
            d["_literal_hit"] = True
            by_table[key].append(d)

    # --- 3) Choose up to T tables (prioritize literal-hit tables, then min _rank) ---
    def table_sort_key(k: Tuple[str, str]) -> Tuple[bool, int]:
        best_rank = min(d.get("_rank", 10**9) for d in by_table[k]) if by_table[k] else 10**9
        return (k not in literal_tables, best_rank)

    ordered_table_keys = sorted(by_table.keys(), key=table_sort_key)[:T]

    # --- 4) Build TableCtx/ColumnCtx with P-column cap per table (prefer literal hits, then rank) ---
    tables: List[TableCtx] = []
    used_aliases: set[str] = set()

    for db_tbl in ordered_table_keys:
        _, tname = db_tbl
        alias = _make_alias(tname, used_aliases)
        used_aliases.add(alias)

        # Sort columns for this table: literal-hit first, then by rank
        cols_all = by_table[db_tbl]
        cols_sorted = sorted(cols_all, key=lambda d: (not d.get("_literal_hit", False), d.get("_rank", 10**9)))

        # Deduplicate by column_name while preserving order, then take top P
        seen_cols: set[str] = set()
        picked: List[Dict[str, Any]] = []
        for d in cols_sorted:
            colname = d["column_name"]
            if colname in seen_cols:
                continue
            seen_cols.add(colname)
            picked.append(d)
            if len(picked) >= P:
                break

        cols_ctx: List[ColumnCtx] = []
        for r in picked:
            long_sum = _maybe_trim_long(r.get("long_summary"), r.get("top_k_values")) if trim_long_to_examples else r.get("long_summary")
            cols_ctx.append(
                ColumnCtx(
                    name=r["column_name"],
                    short_summary=r.get("short_summary"),
                    long_summary=long_sum,
                    english_description=r.get("english_description"),
                )
            )

        tables.append(TableCtx(name=tname, alias=alias, columns=cols_ctx))

    return tables

def _full_schema(
    db: Session,
    cap_tables: int | None,
    trim_long_to_examples: bool,
) -> List[TableCtx]:
    rows = db.execute(
        text(
            """
            SELECT database_name, table_name, column_name,
                   short_summary, long_summary, english_description,
                   top_k_values
            FROM column_profiles
            ORDER BY database_name, table_name, column_name
            """
        )
    ).mappings().all()

    by_table: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = (r["database_name"], r["table_name"])
        by_table[key].append(dict(r))

    table_keys = list(by_table.keys())
    if cap_tables is not None:
        table_keys = table_keys[:cap_tables]

    tables: List[TableCtx] = []
    used_aliases: set[str] = set()

    for db_tbl in table_keys:
        _, tname = db_tbl
        alias = _make_alias(tname, used_aliases)
        used_aliases.add(alias)

        cols: List[ColumnCtx] = []
        for r in by_table[db_tbl]:
            long_sum = _maybe_trim_long(r.get("long_summary"), r.get("top_k_values")) if trim_long_to_examples else r.get("long_summary")
            cols.append(
                ColumnCtx(
                    name=r["column_name"],
                    short_summary=r.get("short_summary"),
                    long_summary=long_sum,
                    english_description=r.get("english_description"),
                )
            )
        tables.append(TableCtx(name=tname, alias=alias, columns=cols))

    return tables

def _maybe_trim_long(long_summary: str | None, top_k_values: Any) -> str | None:
    """Trim long summaries to keep tokens under control: keep format + up to 3 top values."""
    if not long_summary:
        return None
    examples = []
    if isinstance(top_k_values, list):
        for kv in top_k_values[:3]:
            if isinstance(kv, dict) and "value" in kv:
                examples.append(str(kv["value"]))
            else:
                examples.append(str(kv))
    if examples:
        return f"{long_summary}\nCommon values include: {', '.join(examples[:3])}."
    return long_summary

def _make_alias(table_name: str, used: set[str]) -> str:
    """Generate a short, unique alias like f, fr, fr1 ..."""
    base = "".join([c for c in table_name if c.isalnum()])[:2].lower() or "t"
    if base not in used:
        return base
    i = 1
    while f"{base}{i}" in used:
        i += 1
    return f"{base}{i}"

# -------------------------
# Literal extraction & lookup
# -------------------------

_LITERAL_PATTERNS = [
    re.compile(r"\b\d{4}-\d{4}\b"),             # academic year like 2020-2021
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),       # ISO date YYYY-MM-DD
    re.compile(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b"),  # numbers with thousands/decimals
    re.compile(r"[‘'“\"]([^’'”\"]+)[’'”\"]"),   # quoted strings
]

def _extract_literals(q: str) -> List[str]:
    lits: set[str] = set()
    for pat in _LITERAL_PATTERNS:
        for m in pat.finditer(q):
            val = m.group(1) if pat is _LITERAL_PATTERNS[3] else m.group(0)
            val = val.strip()
            if val:
                lits.add(val)
    return list(lits)

def _literal_columns(
    db: Session,
    literals: List[str],
    limit_per_lit: int = 20,
) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    """
    Heuristic: find columns whose top_k_values contain the literal (ILIKE).
    Returns rows grouped by (database_name, table_name). Each row is a dict suitable to merge.
    """
    if not literals:
        return {}

    results: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)

    for lit in literals:
        rows = db.execute(
            text(
                """
                SELECT database_name, table_name, column_name,
                       short_summary, long_summary, english_description, top_k_values
                FROM column_profiles
                WHERE top_k_values IS NOT NULL
                  AND (
                    -- Case 1: top_k_values is a JSON array
                    (jsonb_typeof(top_k_values::jsonb) = 'array' AND EXISTS (
                        SELECT 1
                        FROM jsonb_array_elements(top_k_values::jsonb) AS kv
                        WHERE (kv->>'value') ILIKE :needle
                           OR kv::text ILIKE :needle
                    ))
                    OR
                    -- Case 2: top_k_values is a scalar/string
                    (jsonb_typeof(top_k_values::jsonb) != 'array' AND top_k_values::text ILIKE :needle)
                  )
                LIMIT :lim
                """
            ),
            {"needle": f"%{lit}%", "lim": limit_per_lit},
        ).mappings().all()

        for r in rows:
            key = (r["database_name"], r["table_name"])
            results[key].append(dict(r))

    return results

# -------------------------
# Context rendering
# -------------------------

def _render_context_block(*, tables: List[TableCtx], profile_kind: ProfileKind) -> str:
    """
    Renders the assistant-context block that precedes the user message.
    - minimal:   lists columns with SHORT summaries only
    - maximal:   lists columns with SHORT summaries + separate LONG section for all listed columns
    - full_profile: lists columns with SHORT summaries + FULL PROFILE (english + long)
    """
    lines: List[str] = []
    lines.append("CONTEXT START\n")
    lines.append("DATABASE DIALECT: PostgreSQL\n")
    lines.append("TABLES & COLUMNS")
    for t in tables:
        lines.append(f"Table {t.name} AS {t.alias}")
        for c in t.columns:
            short = c.short_summary or ""
            lines.append(f"  - {t.alias}.{c.name}: {short}")

    if profile_kind in ("maximal", "full_profile"):
        lines.append("\n" + ("LONG SUMMARIES" if profile_kind == "maximal" else "FULL PROFILE (SME + long)") )
        for t in tables:
            for c in t.columns:
                if profile_kind == "maximal":
                    long_text = c.long_summary or ""
                    lines.append(f"- {t.alias}.{c.name}:\n  {long_text}")
                else:
                    parts = []
                    if c.english_description:
                        parts.append(c.english_description)
                    if c.long_summary:
                        parts.append(c.long_summary)
                    combined = "\n  ".join(parts) if parts else ""
                    lines.append(f"- {t.alias}.{c.name}:\n  {combined}")

    lines += [
        "\nHINTS",
        "- Use only the tables/columns above.",
        "- Literal formats must match LONG SUMMARIES (e.g., 'YYYY-YYYY' for academic years).",
        "- If a filter literal is needed, prefer values that appear in the examples.",
        "\nCONTEXT END",
    ]
    return "\n".join(lines)
