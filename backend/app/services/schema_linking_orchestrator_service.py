# backend/app/services/schema_linking_orchestrator_service.py
from __future__ import annotations
from typing import List, Tuple, Set, Dict, Any, Protocol
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.prompt_variants_service import (
    FiveVariants,
    PromptVariant,
    TableCtx,
    ColumnCtx,
    _render_context_block,
    build_five_prompt_variants,
    SYSTEM_RULES
)
from app.services.extractor_fields_and_literals_service import extract_fields_and_literals
from app.services.value_index_service import ValueLSHIndex

class LLMClient(Protocol):
    async def chat(self, messages: List[Dict[str, str]]) -> str: ...

def _augment_tables_with_fields(tables: List[TableCtx],
                                add_fields: Set[Tuple[str, str]],
                                trim_long_to_examples: bool = True) -> List[TableCtx]:
    """
    Add (table,col) pairs into the existing TableCtx list if not present.
    We don't fetch new summaries here; we only inject the pairs so the LLM sees them in the schema.
    If you prefer, you can fetch summaries from DB for added fields before rendering.
    """
    # Index existing
    idx: Dict[str, Dict[str, ColumnCtx]] = {}
    for t in tables:
        idx[t.name] = {c.name: c for c in t.columns}

    for (tname, cname) in add_fields:
        if tname not in idx:
            # create a stub table with a generated alias
            alias = (tname[:2].lower() or "t")
            tables.append(TableCtx(name=tname, alias=alias, columns=[ColumnCtx(name=cname, short_summary="", long_summary="", english_description="")]))
            idx[tname] = {cname: tables[-1].columns[0]}
        elif cname not in idx[tname]:
            # add a stub column
            for t in tables:
                if t.name == tname:
                    t.columns.append(ColumnCtx(name=cname, short_summary="", long_summary="", english_description=""))
                    idx[tname][cname] = t.columns[-1]
                    break
    return tables

def _make_revision_messages(base_messages: List[Dict[str, str]],
                            old_sql: str,
                            added_fields: Set[Tuple[str, str]],
                            missing_literals: List[str]) -> List[Dict[str, str]]:
    # Replace the assistant context with an augmented context that includes the added fields
    sys_msg = base_messages[0]
    ctx_msg = base_messages[1]
    user_msg = base_messages[2]

    # The ctx text we constructed originally lists tables/columns.
    # We'll append a tiny "AUGMENT" section the LLM can see.
    aug = "\nAUGMENTED FIELDS (contain missing literals):\n" + "\n".join(
        f"- {t}.{c}" for (t, c) in sorted(added_fields)
    )
    revised_ctx = ctx_msg["content"].replace("CONTEXT END", aug + "\n\nCONTEXT END")

    # The user message asks for revision, shows missing literals and old SQL
    revision_user = (
        "Revise the SQL so that each of these literals appears in a field that actually contains it.\n\n"
        "Missing literals:\n" + "".join(f"- {l}\n" for l in missing_literals) +
        "\nPrevious SQL:\n" + old_sql + "\n\nOutput SQL only."
    )

    return [
        {"role": "system", "content": sys_msg["content"]},
        {"role": "assistant", "content": revised_ctx},
        {"role": "user", "content": revision_user},
    ]

async def run_sql_first_linking(
    *,
    db: Session,
    question: str,
    llm: LLMClient,
    embedding_service: Any,
    value_index: ValueLSHIndex,
    max_retry: int = 2,
    # Focused schema knobs (paper-aligned defaults)
    M: int = 50,
    P: int = 3,
    T: int = 6,
    include_full_schema_cap: int | None = None,
    trim_long_to_examples: bool = True,
) -> tuple[str, Set[Tuple[str, str]]]:
    """
    The main SQL-first schema linking orchestrator.

    1. Build five prompt variants
    2. For each variant: generate SQL → extract fields & literals → map literals via value index → revise if needed
    3. Union fields across all variants
    4. Generate final SQL with focused context
    """
    # 1) Build five prompt variants
    five = await build_five_prompt_variants(
        db=db,
        question=question,
        embedding_service=embedding_service,
        M=M,
        P=P,
        T=T,
        include_full_schema_cap=include_full_schema_cap,
        trim_long_to_examples=trim_long_to_examples,
    )

    linked_fields: Set[Tuple[str, str]] = set()

    # 2) For each variant: SQL generation with optional revision loop
    for variant in five.variants:
        messages = variant.messages
        sql = await llm.chat(messages)  # initial SQL (SQL only)

        tries = 0
        while True:
            fieldsQ, litsQ = extract_fields_and_literals(sql)

            # Map literals via value LSH → candidate (table,col)
            missing, litFieldsQ = [], set()
            for lit in litsQ:
                candidates = value_index.lookup_literal(lit)  # List[(table, column)]
                if candidates and not any(cf in fieldsQ for cf in candidates):
                    missing.append(lit)
                    litFieldsQ.update(candidates)

            if litFieldsQ and tries < max_retry:
                tries += 1
                # Augment the schema for this variant with the candidate fields and ask for a revision
                # (We don't mutate the original objects; we augment the rendered context in-place.)
                aug_msgs = _make_revision_messages(
                    base_messages=messages,
                    old_sql=sql,
                    added_fields=litFieldsQ,
                    missing_literals=missing,
                )
                sql = await llm.chat(aug_msgs)
                continue

            linked_fields |= fieldsQ
            break

    # 3) Final SQL: render a compact context from unioned fields (short for all; long only for a few)
    final_ctx_text = _render_final_context_from_union(db, linked_fields)
    final_messages = [
        {"role": "system", "content": SYSTEM_RULES},
        {"role": "assistant", "content": final_ctx_text},
        {"role": "user", "content": f"Question:\n{question}"},
    ]
    final_sql = await llm.chat(final_messages)
    return final_sql, linked_fields

def _render_final_context_from_union(db: Session, fields: Set[Tuple[str, str]]) -> str:
    """
    Build a compact context out of the unioned fields:
      - For every (table,col) include the short summary.
      - Include long summaries only for a small shortlist (e.g., 1–3 per table) to guide literals.
    """
    if not fields:
        return "CONTEXT START\nDATABASE DIALECT: PostgreSQL\nCONTEXT END"

    # Build parameter dict for the query
    params = {}
    value_clauses = []
    for i, (t, c) in enumerate(fields):
        t_param = f"t{i}"
        c_param = f"c{i}"
        params[t_param] = t
        params[c_param] = c
        value_clauses.append(f"(:{t_param}, :{c_param})")

    values_clause = ", ".join(value_clauses)

    rows = db.execute(text(f"""
        SELECT table_name, column_name, short_summary, long_summary, english_description, top_k_values
        FROM column_profiles
        WHERE (table_name, column_name) IN (
            VALUES {values_clause}
        )
    """), params).mappings().all()

    # Group by table
    by_table: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_table.setdefault(r["table_name"], []).append(dict(r))

    tables: List[TableCtx] = []
    used_aliases: set[str] = set()
    for tname, cols in by_table.items():
        alias = (tname[:2].lower() or "t")
        if alias in used_aliases:
            i = 1
            while f"{alias}{i}" in used_aliases:
                i += 1
            alias = f"{alias}{i}"
        used_aliases.add(alias)

        # choose a few columns to carry long summaries
        long_picks = set([cols[0]["column_name"]])  # naive: first per table
        tcols: List[ColumnCtx] = []
        for r in cols:
            long_text = (r["long_summary"] or "") if r["column_name"] in long_picks else ""
            tcols.append(ColumnCtx(
                name=r["column_name"],
                short_summary=r["short_summary"] or "",
                long_summary=long_text,
                english_description=r.get("english_description") or "",
            ))
        tables.append(TableCtx(name=tname, alias=alias, columns=tcols))

    # Minimal + long-for-shortlist context
    return _render_context_block(tables=tables, profile_kind="maximal")
