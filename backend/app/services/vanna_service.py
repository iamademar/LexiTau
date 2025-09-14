"""Vanna AI service for SQL generation and execution."""
import time
from typing import Dict, Any, List, Tuple, Optional
import re
from vanna.remote import VannaDefault
from sqlalchemy import Engine, text
import sqlglot

from app.db import engine as ENGINE
from app.core.settings import get_settings


class GuardError(Exception):
    """Exception raised when SQL fails guard policy checks."""
    pass


def _extract_referenced_tables(statement: sqlglot.expressions.Select) -> List[Tuple[str, str]]:
    """
    Extract all referenced tables from a SELECT statement.

    Returns:
        List of (schema, table) tuples
    """
    tables = []
    cte_names = set()

    # First, collect CTE names if present
    with_clause = statement.find(sqlglot.expressions.With)
    if with_clause:
        for cte in with_clause.expressions:
            if hasattr(cte, 'alias') and cte.alias:
                cte_names.add(cte.alias)

    # Walk through all table nodes in the SQL AST
    for table_node in statement.find_all(sqlglot.expressions.Table):
        # Get the table name and schema
        table_name = table_node.name

        # Skip empty table names (can happen with function calls like dblink)
        if not table_name:
            continue

        # Skip CTE references - they're not real database tables
        if table_name in cte_names:
            continue

        if table_node.db:
            schema_name = table_node.db
        else:
            schema_name = "public"  # Default schema

        tables.append((schema_name, table_name))

    return tables


def _validate_schema_and_tables(referenced_tables: List[Tuple[str, str]], settings) -> None:
    """
    Validate that all referenced tables are allowed.

    Args:
        referenced_tables: List of (schema, table) tuples
        settings: Application settings

    Raises:
        GuardError: If validation fails
    """
    if not referenced_tables:
        return

    # Extract unique schemas
    schemas = {schema for schema, _ in referenced_tables}

    # Check for cross-schema joins
    if len(schemas) > 1:
        raise GuardError("cross_schema_join")

    # Validate each table
    for schema, table in referenced_tables:
        # Check if schema is allowed
        if schema not in settings.vanna_allowed_schemas:
            raise GuardError(f"schema_not_allowed:{schema}")

        # Check if table is allowed (full qualified name)
        fq_table = f"{schema}.{table}"
        if fq_table not in settings.vanna_allowed_tables:
            raise GuardError(f"table_not_allowed:{fq_table}")


def _validate_feature_policy(statement: sqlglot.expressions.Select) -> None:
    """
    Validate SQL statement against feature policy restrictions.

    Args:
        statement: Parsed SELECT statement

    Raises:
        GuardError: If statement violates feature policy
    """
    # Check for WITH RECURSIVE first (higher priority than set operations within CTEs)
    with_clause = statement.find(sqlglot.expressions.With)
    if with_clause and getattr(with_clause, 'recursive', False):
        raise GuardError("with_recursive_disallowed")

    # Check for set operations (UNION, INTERSECT, EXCEPT) at statement level
    # (excluding those inside WITH clauses which are valid)
    if statement.find(sqlglot.expressions.Union):
        raise GuardError("set_operations_disallowed")
    if statement.find(sqlglot.expressions.Intersect):
        raise GuardError("set_operations_disallowed")
    if statement.find(sqlglot.expressions.Except):
        raise GuardError("set_operations_disallowed")

    # Check for LATERAL joins
    for _ in statement.find_all(sqlglot.expressions.Lateral):
        raise GuardError("lateral_joins_disallowed")


def _has_global_tenant_predicate(sql: str, settings) -> bool:
    """
    Check if SQL contains global tenant predicate like "business_id = :business_id".

    Args:
        sql: Final SQL string to check
        settings: Application settings with tenant column/param names

    Returns:
        True if global tenant predicate is found
    """
    import re

    tenant_column = settings.vanna_tenant_column
    tenant_param = settings.vanna_tenant_param

    # Pattern to match: business_id = :business_id (with optional whitespace and case variations)
    # This covers: business_id=:business_id, business_id = :business_id, BUSINESS_ID = :BUSINESS_ID, etc.
    pattern = rf'\b{re.escape(tenant_column)}\s*=\s*:{re.escape(tenant_param)}\b'

    return bool(re.search(pattern, sql, re.IGNORECASE))


def _extract_table_aliases(statement: sqlglot.expressions.Select) -> Dict[str, Tuple[str, str]]:
    """
    Extract all table aliases and their corresponding schema.table mappings.

    Args:
        statement: Parsed SELECT statement

    Returns:
        Dict mapping alias -> (schema, table) tuple
    """
    aliases = {}

    # Get tables from FROM clause
    from_clause = statement.find(sqlglot.expressions.From)
    if from_clause and from_clause.this:
        table_node = from_clause.this
        if isinstance(table_node, sqlglot.expressions.Table):
            table_name = table_node.name
            schema_name = table_node.db if table_node.db else "public"

            # Check if table has an alias
            if hasattr(table_node, 'alias') and table_node.alias:
                alias = table_node.alias
            else:
                # If no explicit alias, the table name itself is the alias
                alias = table_name

            if table_name:  # Skip empty table names
                aliases[alias] = (schema_name, table_name)

    # Get tables from JOIN clauses
    for join_node in statement.find_all(sqlglot.expressions.Join):
        if join_node.this and isinstance(join_node.this, sqlglot.expressions.Table):
            table_node = join_node.this
            table_name = table_node.name
            schema_name = table_node.db if table_node.db else "public"

            # Check if table has an alias
            if hasattr(table_node, 'alias') and table_node.alias:
                alias = table_node.alias
            else:
                # If no explicit alias, the table name itself is the alias
                alias = table_name

            if table_name:  # Skip empty table names
                aliases[alias] = (schema_name, table_name)

    return aliases


def _has_per_alias_tenant_predicate(sql: str, alias: str, settings) -> bool:
    """
    Check if SQL contains per-alias tenant predicate like "alias.business_id = :business_id".

    Args:
        sql: Final SQL string to check
        alias: Table alias to check for
        settings: Application settings with tenant column/param names

    Returns:
        True if per-alias tenant predicate is found
    """
    import re

    tenant_column = settings.vanna_tenant_column
    tenant_param = settings.vanna_tenant_param

    # Pattern to match: alias.business_id = :business_id (with optional whitespace and case variations)
    pattern = rf'\b{re.escape(alias)}\.{re.escape(tenant_column)}\s*=\s*:{re.escape(tenant_param)}\b'

    return bool(re.search(pattern, sql, re.IGNORECASE))


def _validate_tenant_enforcement(sql: str, statement: sqlglot.expressions.Select, settings) -> None:
    """
    Validate tenant enforcement requirements: global and per-alias predicates.

    Args:
        sql: Final SQL string
        statement: Parsed SELECT statement
        settings: Application settings

    Raises:
        GuardError: If tenant enforcement requirements are not met
    """
    # Check for global tenant predicate
    if not _has_global_tenant_predicate(sql, settings):
        raise GuardError("missing_tenant_scope")

    # Check per-alias tenant predicates (if enabled)
    if settings.vanna_tenant_enforce_per_table:
        # Extract table aliases and their mappings
        table_aliases = _extract_table_aliases(statement)

        # Check each alias for required tables
        for alias, (schema, table) in table_aliases.items():
            fq_table = f"{schema}.{table}"

            # Only enforce per-alias for required tables
            if fq_table in settings.vanna_tenant_required_tables:
                if not _has_per_alias_tenant_predicate(sql, alias, settings):
                    raise GuardError(f"missing_tenant_scope_for_alias:{alias}")


def _has_star_expression(statement: sqlglot.expressions.Select) -> bool:
    """
    Check if the SELECT statement contains any Star (*) expressions.

    Args:
        statement: Parsed SELECT statement

    Returns:
        True if statement contains SELECT * expressions
    """
    for expression in statement.expressions:
        if isinstance(expression, sqlglot.expressions.Star):
            return True
    return False


def _get_table_columns_from_db(engine: Engine, schema: str, table: str, settings) -> List[Tuple[str, str]]:
    """
    Get column names and types for a specific table from the database.

    Args:
        engine: SQLAlchemy engine for database connection
        schema: Database schema name
        table: Table name
        settings: Application settings for exclusions

    Returns:
        List of (column_name, column_type) tuples
    """
    query = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = :schema AND table_name = :table
    ORDER BY ordinal_position
    """

    with engine.begin() as conn:
        result = conn.execute(text(query), {"schema": schema, "table": table})
        columns = [(row[0], row[1]) for row in result.fetchall()]

    # Apply exclusions
    filtered_columns = []
    fq_table = f"{schema}.{table}"

    for col_name, col_type in columns:
        # Skip excluded types (e.g., bytea)
        if col_type.lower() in [t.lower() for t in settings.vanna_expand_exclude_types]:
            continue

        # Skip columns matching sensitive name patterns
        should_skip = False
        for pattern in settings.vanna_expand_exclude_name_patterns:
            if re.search(pattern, col_name, re.IGNORECASE):
                should_skip = True
                break

        if should_skip:
            continue

        # Skip per-table excluded columns
        fq_column = f"{fq_table}.{col_name}"
        if fq_column in settings.vanna_expand_exclude_columns:
            continue

        filtered_columns.append((col_name, col_type))

    return filtered_columns


def _make_column_alias(table_alias: str, column_name: str) -> str:
    """
    Create column alias in lower_snake_case format.

    Args:
        table_alias: Table or alias name
        column_name: Column name

    Returns:
        Column alias in format: {table_alias}_{column_name}
    """
    # Convert to snake_case and lowercase
    alias = f"{table_alias}_{column_name}".lower()
    # Replace any non-alphanumeric characters with underscores
    alias = re.sub(r'[^a-z0-9_]', '_', alias)
    # Remove duplicate underscores
    alias = re.sub(r'_+', '_', alias)
    # Remove leading/trailing underscores
    alias = alias.strip('_')

    return alias


def _expand_star_expression(statement: sqlglot.expressions.Select, engine: Engine, settings) -> sqlglot.expressions.Select:
    """
    Expand SELECT * expressions into explicit column lists with aliases.

    Args:
        statement: Parsed SELECT statement
        engine: SQLAlchemy engine for database connection
        settings: Application settings

    Returns:
        Modified SELECT statement with expanded columns
    """
    if not settings.vanna_expand_select_star or not _has_star_expression(statement):
        return statement

    # Get table aliases in FROM/JOIN order
    table_aliases = _extract_table_aliases(statement)

    # Build new expression list
    new_expressions = []

    for expression in statement.expressions:
        if isinstance(expression, sqlglot.expressions.Star):
            # Expand * for all tables in order
            for alias, (schema, table) in table_aliases.items():
                try:
                    columns = _get_table_columns_from_db(engine, schema, table, settings)
                    for col_name, col_type in columns:
                        # Create qualified column reference
                        column_ref = sqlglot.expressions.Column(
                            this=sqlglot.expressions.Identifier(this=col_name),
                            table=sqlglot.expressions.Identifier(this=alias)
                        )

                        # Create alias
                        column_alias = _make_column_alias(alias, col_name)
                        aliased_column = sqlglot.expressions.Alias(
                            this=column_ref,
                            alias=sqlglot.expressions.Identifier(this=column_alias)
                        )

                        new_expressions.append(aliased_column)

                except Exception as e:
                    # If column expansion fails, keep original * expression
                    # This could happen if table doesn't exist or no permissions
                    new_expressions.append(expression)
                    break
        else:
            # Keep non-star expressions as-is
            new_expressions.append(expression)

    # Create new SELECT statement with expanded expressions
    # Build a new SELECT with the same structure but different expressions
    new_select = sqlglot.expressions.Select(
        expressions=new_expressions,
        from_=statement.args.get('from'),
        joins=statement.args.get('joins'),
        where=statement.args.get('where'),
        group=statement.args.get('group'),
        having=statement.args.get('having'),
        order=statement.args.get('order'),
        limit=statement.args.get('limit'),
        offset=statement.args.get('offset'),
        with_=statement.args.get('with'),
        distinct=statement.args.get('distinct')
    )

    return new_select


def _validate_function_denylist(statement: sqlglot.expressions.Select, settings) -> None:
    """
    Validate that no denied functions are used.

    Args:
        statement: Parsed SELECT statement
        settings: Application settings with function denylist

    Raises:
        GuardError: If denied function is found
    """
    import re

    # Walk through all function calls
    for func_node in statement.find_all(sqlglot.expressions.Anonymous):
        func_name = func_node.this.lower()

        # Check against deny-list patterns (case-insensitive)
        for pattern in settings.vanna_function_denylist:
            if re.match(pattern, func_name, re.IGNORECASE):
                raise GuardError(f"function_denied:{func_name}")

    # Also check standard function calls
    for func_node in statement.find_all(sqlglot.expressions.Func):
        func_name = func_node.key.lower()

        # Check against deny-list patterns (case-insensitive)
        for pattern in settings.vanna_function_denylist:
            if re.match(pattern, func_name, re.IGNORECASE):
                raise GuardError(f"function_denied:{func_name}")


def guard_and_rewrite_sql(sql: str, business_id: int) -> Tuple[str, List[str], Dict[str, Any]]:
    """
    Guard and rewrite SQL according to Vanna policy.

    Args:
        sql: Input SQL statement
        business_id: Tenant business ID for scoping

    Returns:
        Tuple of (final_sql, guard_flags, metadata)

    Raises:
        GuardError: If SQL fails policy checks
    """
    try:
        # Parse with sqlglot using Postgres dialect
        parsed = sqlglot.parse(sql, dialect='postgres')

        if not parsed or parsed[0] is None:
            raise GuardError("failed_to_parse_sql")

        # Check if it's a SELECT-like statement or set operation
        statement = parsed[0]
        if isinstance(statement, (sqlglot.expressions.Union, sqlglot.expressions.Intersect, sqlglot.expressions.Except)):
            raise GuardError("set_operations_disallowed")
        elif not isinstance(statement, sqlglot.expressions.Select):
            raise GuardError("non_select_statement")

        # Extract referenced tables and validate against allow-list
        settings = get_settings()
        referenced_tables = _extract_referenced_tables(statement)
        _validate_schema_and_tables(referenced_tables, settings)

        # Validate feature policy restrictions
        _validate_feature_policy(statement)

        # Validate function deny-list
        _validate_function_denylist(statement, settings)

        # Validate tenant enforcement (global and per-alias)
        _validate_tenant_enforcement(sql, statement, settings)

        # Expand SELECT * expressions if enabled
        expanded_statement = _expand_star_expression(statement, ENGINE, settings)

        # Convert back to SQL string
        final_sql = expanded_statement.sql(dialect='postgres')

        # For now, return expanded SQL with empty flags/metadata
        guard_flags = []
        metadata = {}

        return final_sql, guard_flags, metadata

    except sqlglot.ParseError as e:
        raise GuardError(f"sql_parse_error: {str(e)}")


def guarded_run_sql(
    engine: Engine,
    sql: str,
    params: Dict[str, Any],
    timeout_s: int = 5,
    work_mem: Optional[str] = None,
) -> Tuple[List[str], List[List[Any]], int, bool, int, Optional[str]]:
    """
    Execute SQL with safety GUCs, timeouts, and read-only constraints.

    Returns tuple of (columns, rows, row_count, truncated, execution_ms, description).
    """
    start_time = time.time()
    timeout_ms = timeout_s * 1000

    with engine.begin() as conn:
        # Set safety GUCs
        conn.execute(text("SET TRANSACTION READ ONLY"))
        conn.execute(text("SET LOCAL search_path = 'public'"))
        conn.execute(text("SET LOCAL lock_timeout = '1s'"))
        conn.execute(text("SET LOCAL idle_in_transaction_session_timeout = '5s'"))
        conn.execute(text(f"SET LOCAL statement_timeout = '{timeout_ms}ms'"))

        if work_mem:
            conn.execute(text(f"SET LOCAL work_mem = '{work_mem}'"))

        # Execute the actual query
        result = conn.execute(text(sql), params)

        # Fetch column names
        columns = list(result.keys()) if result.keys() else []

        # Fetch all rows and convert to lists
        rows_as_dicts = result.fetchall()
        rows = [list(row) for row in rows_as_dicts]

        row_count = len(rows)
        truncated = False  # Will implement truncation detection later

        # Calculate execution time
        execution_ms = int((time.time() - start_time) * 1000)

        # Get description from cursor if available
        description = None
        if hasattr(result, 'cursor') and hasattr(result.cursor, 'description'):
            description = result.cursor.description

        return (columns, rows, row_count, truncated, execution_ms, description)


def get_vanna() -> VannaDefault:
    """Get configured Vanna instance with guarded SQL execution."""
    settings = get_settings()
    vn = VannaDefault(model=settings.vanna_model, api_key=settings.vanna_api_key)

    # Guarded run_sql for any Vanna-initiated executions (rare today, but safe)
    def _vn_run_sql(sql: str, params: dict | None = None) -> List[List[Any]]:
        params = params or {}
        # Enforce tenant param presence (do NOT silently inject here)
        if settings.vanna_tenant_param not in params:
            raise RuntimeError(f"{settings.vanna_tenant_param} is required for VN.run_sql")

        # We assume SQL is already guarded upstream; still use safe GUCs/timeout defaults
        _, rows, *_ = guarded_run_sql(
            ENGINE, sql, params,
            timeout_s=settings.vanna_default_timeout_s,
            work_mem=settings.vanna_work_mem,
        )
        return rows  # Vanna typically expects rows-only

    vn.run_sql = _vn_run_sql
    return vn


# Global Vanna instance
VN = get_vanna()