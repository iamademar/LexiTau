# backend/app/services/extractor_fields_and_literals_service.py
from typing import Set, Tuple
import sqlglot
from sqlglot import exp

def extract_fields_and_literals(sql: str) -> tuple[Set[tuple[str, str]], Set[str]]:
    """
    Returns:
      fields: set of (table, column) with table names resolved from aliases
      literals: set of concrete values (strings/numbers/dates) used in the SQL
    """
    tree = sqlglot.parse_one(sql, read="postgres")

    # Build alias->table mapping
    alias_to_table: dict[str, str] = {}
    for t in tree.find_all(exp.Table):
        base = (t.this.name if isinstance(t.this, exp.Identifier) else t.name) or ""
        base = base.split(".")[-1]
        if t.alias:
            alias_to_table[t.alias] = base
        alias_to_table.setdefault(base, base)

    # Extract columns
    fields: set[Tuple[str, str]] = set()
    for col in tree.find_all(exp.Column):
        tab = col.table
        colname = col.name
        if tab and colname:
            fields.add((alias_to_table.get(tab, tab), colname))

    # Extract literals (strings/numbers/dates, incl. IN/ BETWEEN / casts)
    lits: set[str] = set()
    for node in tree.walk():
        if isinstance(node, exp.Literal) and node.this is not None:
            lits.add(str(node.this))
        elif isinstance(node, exp.Tuple):
            for child in node.expressions:
                if isinstance(child, exp.Literal) and child.this is not None:
                    lits.add(str(child.this))
        elif isinstance(node, (exp.Cast, exp.DateStrToDate, exp.StrToTime)):
            for child in node.find_all(exp.Literal):
                if child.this is not None:
                    lits.add(str(child.this))

    # Normalize a bit (trim quotes/spaces)
    norm = set()
    for l in lits:
        s = str(l).strip().strip("'").strip('"')
        s = s.replace("–", "-")
        if s:
            norm.add(s)
    return fields, norm
