# backend/app/routers/analysis.py
from __future__ import annotations

from typing import List, Tuple
import anyio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.embedding_service import embedding_service
from app.services.value_index_service import ValueLSHIndex
from app.services.schema_linking_orchestrator_service import run_sql_first_linking

# ---------
# Models
# ---------
class AnalysisRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Natural-language question to answer with SQL")

class AnalysisResponse(BaseModel):
    sql: str
    linked_fields: List[Tuple[str, str]]
    debug_variants: List[str] | None = None

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
async def run_pipeline(payload: AnalysisRequest, db: Session = Depends(get_db)):
    question = payload.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

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
            max_retry=2,  # bounded revision passes
            # the following knobs mirror your defaults:
            M=50, P=3, T=6,
            include_full_schema_cap=None,
            trim_long_to_examples=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    # NOTE: If you want variant names for debugging in the response,
    # you could optionally expose them from orchestrator.
    return AnalysisResponse(
        sql=final_sql,
        linked_fields=sorted(list(linked_fields)),
        debug_variants=None,  # keep None unless you plumb this through
    )