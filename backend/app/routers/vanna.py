"""Vanna AI router for SQL analysis endpoints."""
import uuid
import time
import logging
import traceback
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import ValidationError

from ..db import get_db
from ..auth import get_current_user
from ..models.user import User
from ..schemas.vanna import (
    VannaAnalysisRequest,
    VannaAnalysisResponse,
    VannaAnalysisResponseData,
    VannaErrorResponse,
    ColumnMetadata
)
from ..services.vanna_service import (
    guard_and_rewrite_sql,
    guarded_run_sql,
    serialize_cell,
    build_columns_meta,
    GuardError
)
from ..db import engine as ENGINE

router = APIRouter(prefix="/vanna", tags=["vanna"])
logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """Exception for SQL execution errors."""
    pass


class TimeoutError(Exception):
    """Exception for SQL timeout errors."""
    pass


class GenerationError(Exception):
    """Exception for SQL generation errors."""
    pass


def sanitize_error_message(error: Exception) -> str:
    """Sanitize error messages for production."""
    # In production, we might want to sanitize or redact sensitive information
    # For now, return the original message but could be enhanced
    return str(error)


@router.post("/analysis")
async def analyze_sql(
    request_data: VannaAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    http_request: Request = None
):
    """
    Analyze and execute SQL queries via Vanna AI.

    Supports two modes:
    1. question: Natural language question converted to SQL
    2. sql: Raw SQL query execution

    Returns execution results with optional trace metadata.
    """
    trace_id = str(uuid.uuid4())

    try:
        # Get business_id from authenticated user
        business_id = current_user.business_id
        user_id = current_user.id

        # Check if client attempted to pass business_id in request params
        # This is a security check - business_id should come from auth context only
        if http_request and http_request.query_params.get('business_id'):
            logger.warning(f"Client attempted to override business_id. trace_id={trace_id} user_id={user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="business_id parameter not allowed - derived from authentication context"
            )

        # For now, we only handle the SQL path as specified
        if request_data.question is not None:
            # Question path would require Vanna AI integration
            # Not implemented in this phase
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Question-based analysis not yet implemented"
            )

        # SQL execution path
        sql = request_data.sql
        logger.info(f"Processing SQL analysis. trace_id={trace_id} user_id={user_id} business_id={business_id}")

        # Guard and rewrite SQL
        try:
            final_sql, guard_flags, metadata = guard_and_rewrite_sql(
                sql, business_id, engine=ENGINE
            )
        except GuardError as e:
            logger.warning(f"Guard error. trace_id={trace_id} error={e}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=sanitize_error_message(e)
            )
        except Exception as e:
            logger.error(f"Unexpected guard error. trace_id={trace_id} error={e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SQL validation failed"
            )

        # Prefix SQL with trace comment
        trace_comment = f"/* vanna trace_id={trace_id} user_id={user_id} business_id={business_id} */"
        final_sql_with_trace = f"{trace_comment}\n{final_sql}"

        # Execute SQL with guarded runner
        start_time = time.time()
        try:
            columns, rows, row_count, truncated, execution_ms, description = guarded_run_sql(
                ENGINE,
                final_sql_with_trace,
                {"business_id": business_id},
                timeout_s=5,  # Default timeout
                row_limit=500  # Default row limit for truncation detection
            )
        except TimeoutError as e:
            logger.error(f"SQL timeout. trace_id={trace_id} error={e}")
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail="Query execution timeout"
            )
        except ExecutionError as e:
            logger.error(f"SQL execution error. trace_id={trace_id} error={e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=sanitize_error_message(e)
            )
        except Exception as e:
            logger.error(f"Unexpected execution error. trace_id={trace_id} error={e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Query execution failed"
            )

        # Apply serialization to rows
        serialized_rows = []
        for row in rows:
            serialized_row = [serialize_cell(cell) for cell in row]
            serialized_rows.append(serialized_row)

        # Build response data
        response_data = VannaAnalysisResponseData(
            sql=final_sql,  # Return the final SQL without trace comment
            columns=columns,
            rows=serialized_rows,
            row_count=row_count,
            truncated=truncated,
            execution_ms=execution_ms
        )

        # Add trace information if requested
        if request_data.trace:
            response_data.trace_id = trace_id
            response_data.guard_flags = guard_flags
            response_data.metadata = metadata

            # Build column metadata
            try:
                column_meta = build_columns_meta(ENGINE, columns, rows, description)
                column_meta_objects = [ColumnMetadata(**meta) for meta in column_meta]
                response_data.meta = {"columns": column_meta_objects}
            except Exception as e:
                logger.warning(f"Failed to build column metadata. trace_id={trace_id} error={e}")
                # Continue without metadata - it's optional

        logger.info(f"SQL analysis completed successfully. trace_id={trace_id} rows={row_count} truncated={truncated}")

        return VannaAnalysisResponse(
            ok=True,
            data=response_data
        )

    except ValidationError as e:
        logger.warning(f"Validation error. trace_id={trace_id} error={e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Request validation failed"
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like authentication failures)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in SQL analysis. trace_id={trace_id} error={e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )