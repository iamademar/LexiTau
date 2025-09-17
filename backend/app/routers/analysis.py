# backend/app/routers/analysis.py
from __future__ import annotations

from typing import List, Tuple
import anyio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text
from openai import AsyncOpenAI

from app.db import get_db
from app.auth import get_current_user
from app.models.user import User
from app.services.embedding_service import embedding_service
from app.services.value_index_service import ValueLSHIndex
from app.services.schema_linking_orchestrator_service import run_sql_first_linking
from app.services.openai_llm_service import OpenAILLMService
from app.core.settings import get_settings

# ---------
# SQL Safety & Normalization
# ---------
def _normalize_params(sql: str) -> str:
    """Normalize SQLGlot's $business_id to SQLAlchemy's :business_id."""
    return sql.replace("$business_id", ":business_id")

def _is_safe_select(sql: str) -> bool:
    """Ensure only SELECT queries are allowed for safety."""
    s = sql.strip().lower()
    # Check if it starts with SELECT
    if not s.startswith("select"):
        return False

    # Check for dangerous SQL commands at word boundaries
    import re
    dangerous_patterns = [
        r'\binsert\b', r'\bupdate\b', r'\bdelete\b',
        r'\bdrop\b', r'\balter\b', r'\bcreate\b', r'\btruncate\b'
    ]

    return not any(re.search(pattern, s) for pattern in dangerous_patterns)

def execute_readonly_sql(db: Session, sql: str, params: dict = None) -> List[Tuple]:
    """Safely execute SQL in read-only mode and return results."""
    try:
        # Set safety constraints: timeout and read-only mode
        db.execute(text("SET LOCAL statement_timeout = 5000"))  # 5 seconds
        db.execute(text("SET LOCAL default_transaction_read_only = on"))

        # Execute the query
        result = db.execute(text(sql), params or {})
        return [tuple(row) for row in result.fetchall()]
    except Exception as e:
        return [("Error executing SQL", str(e))]

async def format_results_with_llm(question: str, sql: str, raw_results: List[Tuple]) -> str:
    """Format raw DB results into natural language using LLM."""
    settings = get_settings()

    if not settings.openai_api_key:
        return f"Raw results: {raw_results}"

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        llm = OpenAILLMService(client=client, model="gpt-4o-mini", temperature=0.0)

        prompt = f"""
You are an assistant helping to format database query results into natural language.

Original user question: "{question}"
SQL query executed: {sql}
Raw database results: {raw_results}

Please format these database results into a clear, natural language response.

Guidelines:
- If showing clients, list them clearly
- Use bullet points or numbered lists for multiple items
- Make it conversational and helpful
- If there are no results, explain that clearly
- If there's an error, explain it in user-friendly terms

Provide a clear, helpful response:
"""

        response = await llm.chat([
            {"role": "system", "content": "You are a helpful assistant that formats database results into natural language."},
            {"role": "user", "content": prompt}
        ])
        return response
    except Exception as e:
        return f"I found the following results but couldn't format them nicely: {raw_results}"

# ---------
# Models
# ---------
class AnalysisRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Natural-language question to answer with SQL")

class AnalysisResponse(BaseModel):
    answer: str
    sql: str
    linked_fields: List[Tuple[str, str]] | None = None

# ----------------------------
# LLM client (SQL-only return)
# ----------------------------
class OpenAIClient:
    """
    Minimal async wrapper that returns SQL-only strings.
    If your OpenAI client is sync, we run it in a worker thread.
    """
    def __init__(self, client, model: str = "gpt-4o-mini", temperature: float = 0.0, max_tokens: int | None = None):
        self.client = client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def chat(self, messages: list[dict]) -> str:
        # OpenAI python SDK call is synchronous; run it without blocking the event loop
        def _call():
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                **({} if self.max_tokens is None else {"max_tokens": self.max_tokens}),
            )
            return resp.choices[0].message.content.strip()

        return await anyio.to_thread.run_sync(_call)

# ----------------------------
# Global (warmed) ValueLSHIndex
# ----------------------------
_vindex: ValueLSHIndex | None = None

def get_value_index(db: Session) -> ValueLSHIndex:
    """
    Build once, then reuse. You can add a TTL or rebuild hook if your column_profiles change.
    """
    global _vindex
    if _vindex is None or not _vindex.is_built():
        idx = ValueLSHIndex(threshold=0.4, num_perm=128, k=4)
        idx.build_from_db(db)  # builds from column_profiles (top_k_values / distinct_sample)
        _vindex = idx
    return _vindex

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.post("/run", response_model=AnalysisResponse)
async def run_pipeline(
    payload: AnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = payload.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    # Validate tenant
    business_id = getattr(current_user, "business_id", None)
    if not isinstance(business_id, int) or business_id <= 0:
        raise HTTPException(status_code=403, detail="Missing or invalid tenant (business_id)")

    # Warm/reuse the value index (LSH over per-column MinHashes)
    vindex = get_value_index(db)

    # Plug in your OpenAI client
    try:
        from openai import OpenAI
        llm = OpenAIClient(OpenAI(), model="gpt-4o-mini", temperature=0.0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM init failed: {e}")

    # The orchestrator runs:
    #  1) build five variants
    #  2) per-variant: generate SQL → extract fields/literals → map literals via value index → revise if needed
    #  3) union linked fields
    #  4) generate final SQL
    try:
        final_sql, linked_fields = await run_sql_first_linking(
            db=db,
            question=question,
            llm=llm,
            embedding_service=embedding_service,
            value_index=vindex,
            business_id=business_id,
            max_retry=2,  # bounded revision passes
            # the following knobs mirror your defaults:
            M=50, P=3, T=6,
            include_full_schema_cap=None,
            trim_long_to_examples=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    # Execute the SQL safely with tenant scoping
    try:
        # Normalize SQLGlot parameters to SQLAlchemy format
        sql_exec = _normalize_params(final_sql)

        # Ensure only SELECT queries are allowed
        if not _is_safe_select(sql_exec):
            raise HTTPException(status_code=400, detail="Only SELECT queries allowed")

        # Execute SQL safely
        raw_results = execute_readonly_sql(db, sql_exec, {"business_id": business_id})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SQL execution failed: {e}")

    # Format results with LLM
    try:
        formatted_answer = await format_results_with_llm(question, final_sql, raw_results)
    except Exception as e:
        formatted_answer = f"I found the following results but couldn't format them nicely: {raw_results}"

    return AnalysisResponse(
        answer=formatted_answer,
        sql=final_sql,
        linked_fields=sorted(list(linked_fields)),
    )