"""Pydantic schemas for Vanna AI analysis endpoints."""
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any, Union
from uuid import UUID


class VannaAnalysisRequest(BaseModel):
    """Request for Vanna analysis endpoint."""
    question: Optional[str] = Field(None, description="Natural language question to convert to SQL")
    sql: Optional[str] = Field(None, description="Raw SQL query to execute")
    trace: Optional[bool] = Field(False, description="Include execution metadata in response")

    @model_validator(mode='after')
    def validate_exactly_one_of_question_or_sql(self):
        """Ensure exactly one of question or sql is provided."""
        question_provided = self.question is not None
        sql_provided = self.sql is not None

        if question_provided and sql_provided:
            raise ValueError("Provide either 'question' or 'sql', not both")

        if not question_provided and not sql_provided:
            raise ValueError("Either 'question' or 'sql' must be provided")

        return self


class ColumnMetadata(BaseModel):
    """Metadata for a single column."""
    name: str = Field(..., description="Column name")
    db_type: str = Field(..., description="Database type")
    py_type: str = Field(..., description="Python type")
    nullable: bool = Field(..., description="Whether column allows null values")
    serialized_as: str = Field(..., description="Type after JSON serialization")


class VannaAnalysisResponseData(BaseModel):
    """Data section of Vanna analysis response."""
    sql: str = Field(..., description="Final SQL query that was executed")
    columns: List[str] = Field(..., description="Column names")
    rows: List[List[Any]] = Field(..., description="Query result rows")
    row_count: int = Field(..., description="Number of rows returned")
    truncated: bool = Field(..., description="Whether results were truncated")
    execution_ms: int = Field(..., description="Query execution time in milliseconds")

    # Optional trace fields
    trace_id: Optional[str] = Field(None, description="Trace identifier")
    guard_flags: Optional[Dict[str, Any]] = Field(None, description="Guard processing flags")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Query processing metadata")
    meta: Optional[Dict[str, List[ColumnMetadata]]] = Field(None, description="Column metadata when trace=true")


class VannaAnalysisResponse(BaseModel):
    """Response from Vanna analysis endpoint."""
    ok: bool = Field(..., description="Whether the request was successful")
    data: Optional[VannaAnalysisResponseData] = Field(None, description="Analysis results")
    error: Optional[str] = Field(None, description="Error message if ok=false")
    error_type: Optional[str] = Field(None, description="Error type classification")


class VannaErrorResponse(BaseModel):
    """Error response format."""
    ok: bool = Field(False, description="Always false for error responses")
    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Error type classification")