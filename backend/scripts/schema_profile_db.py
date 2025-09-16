# scripts/schema_profile_db.py
# Portable DB profiler (SQLAlchemy) — prints JSON lines, one ColumnProfile per column.
# Uses DATABASE_URL if present, otherwise pass --url
#   export DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/dbname"
#   docker-compose exec fastapi python -u scripts/profile_db.py --tables documents,clients

from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, random, sys
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import create_engine, MetaData, Table, select, func, text, cast
from sqlalchemy.engine import Engine
from sqlalchemy.sql.elements import ColumnClause
from sqlalchemy.types import (
    Integer, BigInteger, SmallInteger, Numeric, Float, DECIMAL,
    Date, DateTime, Time, String, Text, Unicode, UnicodeText, LargeBinary, Boolean
)

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# Database imports for saving profiles
from sqlalchemy.orm import sessionmaker
from app.models.column_profile import ColumnProfile as ColumnProfileModel
from app.schemas.column_profile import ColumnProfileCreate
from app.services.embedding_service import embedding_service


# ------------------ CONFIG (tweak as needed) ------------------
TOP_K = 10                              # number of most frequent values to keep
DISTINCT_SAMPLE_MAX = 10_000            # cap of distinct values sampled per column (for sketches)
MINHASH_PERM = 128                      # number of hash functions in minhash sketch
NULL_STRING = "<NULL>"                  # canonical null marker for profiles
TEXT_SAMPLE_FOR_SHAPE = 5_000           # rows to sample for char-class stats
PREFIX_LEN = 3                          # prefix length for common_prefixes
PREFIX_TOP = 5                          # how many prefixes to keep
RANDOM_SEED = 1337                      # reproducibility for sampling
# --------------------------------------------------------------

# --------- CLI & debug ----------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Database profiler — prints ColumnProfile JSON lines and saves to database.")
    p.add_argument("--url", help="SQLAlchemy DB URL. If omitted, uses $DATABASE_URL.", default=None)
    p.add_argument("--tables", help="Comma-separated allowlist of tables to profile.", default=None)
    p.add_argument("--schema", help="DB schema to reflect (e.g., public). Default: DB default.", default=None)
    p.add_argument("--jsonl-out", help="Optional path to write JSONL output (in addition to stdout).", default=None)
    p.add_argument("--debug", action="store_true", help="Print debug info to stderr.")
    p.add_argument("--database-name", help="Name of the database being profiled. Defaults to database name from URL.")
    return p.parse_args()

DEBUG = False
def dbg(msg: str):
    if DEBUG:
        print(f"[profile_db] {msg}", file=sys.stderr, flush=True)

# --------- dataclasses ----------
@dataclass
class ShapeInfo:
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    length_min: Optional[int] = None
    length_max: Optional[int] = None
    char_classes: Dict[str, int] = field(default_factory=dict)
    common_prefixes: List[Tuple[str, int]] = field(default_factory=list)

@dataclass
class ColumnProfile:
    table_name: str
    column_name: str
    data_type: str
    table_row_count: int
    null_count: int
    non_null_count: int
    distinct_count: Optional[float]
    shape: ShapeInfo
    top_k_values: List[Tuple[str, int]]
    distinct_sample: List[str]
    minhash_signature: List[int]
    generated_at: str

# --------- MinHash ----------
class MinHasher:
    """Simple MinHash using blake2b with different seeds (no extra deps)."""
    def __init__(self, num_perm: int = 128):
        self.num_perm = num_perm
        rng = random.Random(RANDOM_SEED)
        self.seeds = [rng.getrandbits(64).to_bytes(8, "little") for _ in range(num_perm)]
        self.signature = [2**64 - 1] * num_perm

    def _h(self, val_bytes: bytes, seed_bytes: bytes) -> int:
        h = hashlib.blake2b(val_bytes, digest_size=8, person=seed_bytes)
        return int.from_bytes(h.digest(), "big", signed=False)

    def update(self, val: str) -> None:
        b = val.encode("utf-8", errors="ignore")
        for i, seed in enumerate(self.seeds):
            hv = self._h(b, seed)
            if hv < self.signature[i]:
                self.signature[i] = hv

    def digest(self) -> List[int]:
        return self.signature[:]

# --------- type helpers ----------
def is_numeric(sa_type) -> bool:
    return isinstance(sa_type, (Integer, BigInteger, SmallInteger, Numeric, Float, DECIMAL))

def is_textual(sa_type) -> bool:
    return isinstance(sa_type, (String, Text, Unicode, UnicodeText))

def is_temporal(sa_type) -> bool:
    return isinstance(sa_type, (Date, DateTime, Time))

def safe_type_name(sa_type) -> str:
    return getattr(sa_type, "__class__", type(sa_type)).__name__

def supports_random(engine: Engine) -> str:
    name = engine.dialect.name
    if name in ("postgresql", "duckdb", "redshift"): return "random()"
    if name in ("sqlite",): return "RANDOM()"
    if name in ("mysql", "mariadb"): return "RAND()"
    return "random()"

# --------- SQL helpers ----------
def count_rows(engine: Engine, table: Table) -> int:
    q = select(func.count()).select_from(table)
    with engine.connect() as cxn:
        return int(cxn.execute(q).scalar_one())

def null_vs_nonnull(engine: Engine, table: Table, col: ColumnClause) -> Tuple[int, int]:
    q = select(
        func.count().filter(col.is_(None)),
        func.count().filter(col.is_not(None))
    ).select_from(table)
    with engine.connect() as cxn:
        nulls, nonnulls = cxn.execute(q).one()
        return int(nulls or 0), int(nonnulls or 0)

def distinct_count(engine: Engine, table: Table, col: ColumnClause) -> int:
    q = select(func.count(func.distinct(col))).select_from(table).where(col.is_not(None))
    with engine.connect() as cxn:
        return int(cxn.execute(q).scalar_one() or 0)

def min_max_numeric(engine: Engine, table: Table, col: ColumnClause) -> Tuple[Optional[Any], Optional[Any]]:
    q = select(func.min(col), func.max(col)).where(col.is_not(None)).select_from(table)
    with engine.connect() as cxn:
        return cxn.execute(q).one()

def min_max_lex(engine: Engine, table: Table, col: ColumnClause) -> Tuple[Optional[str], Optional[str]]:
    # Cast to TEXT for portability across UUID/JSON/BOOL/etc.
    q = select(
        func.min(cast(col, String())),
        func.max(cast(col, String()))
    ).where(col.is_not(None)).select_from(table)
    with engine.connect() as cxn:
        return cxn.execute(q).one()


def length_range(engine: Engine, table: Table, col: ColumnClause) -> Tuple[Optional[int], Optional[int]]:
    # Cast to TEXT so enums/uuids/etc. work
    q = select(
        func.min(func.length(cast(col, String()))),
        func.max(func.length(cast(col, String())))
    ).where(col.is_not(None)).select_from(table)
    with engine.connect() as cxn:
        return cxn.execute(q).one()


def topk(engine: Engine, table: Table, col: ColumnClause, k: int) -> List[Tuple[str, int]]:
    ident = engine.dialect.identifier_preparer.format_column(col)
    q = text(f"""
        SELECT {ident} AS v, COUNT(*) AS n
        FROM {table.name}
        WHERE {ident} IS NOT NULL
        GROUP BY v
        ORDER BY n DESC
        LIMIT :k
    """)
    with engine.connect() as cxn:
        rows = cxn.execute(q, {"k": k}).fetchall()
    return [(NULL_STRING if v is None else str(v), int(n)) for v, n in rows]

def distinct_sample(engine: Engine, table: Table, col: ColumnClause, limit: int) -> List[str]:
    ident = engine.dialect.identifier_preparer.format_column(col)
    rnd = supports_random(engine)
    q = text(f"""
        SELECT {ident} AS v
        FROM (
          SELECT DISTINCT {ident} AS {ident}
          FROM {table.name}
          WHERE {ident} IS NOT NULL
        ) d
        ORDER BY {rnd}
        LIMIT :lim
    """)
    with engine.connect() as cxn:
        return [NULL_STRING if r[0] is None else str(r[0]) for r in cxn.execute(q, {"lim": limit}).fetchall()]

def sample_nonnull_values(engine: Engine, table: Table, col: ColumnClause, limit: int) -> List[str]:
    ident = engine.dialect.identifier_preparer.format_column(col)
    rnd = supports_random(engine)
    q = text(f"""
        SELECT {ident} AS v
        FROM {table.name}
        WHERE {ident} IS NOT NULL
        ORDER BY {rnd}
        LIMIT :lim
    """)
    with engine.connect() as cxn:
        return [str(r[0]) for r in cxn.execute(q, {"lim": limit}).fetchall()]

def char_class_counts_from_sample(values: Sequence[str]) -> Dict[str, int]:
    import string
    digits_only = alpha_only = has_punct = has_space = mixed = 0
    punct_set = set(string.punctuation)
    for v in values:
        if v is None: continue
        s = str(v)
        if not s: continue
        is_digits = all(ch.isdigit() for ch in s)
        is_alpha  = all(ch.isalpha() for ch in s)
        punct = any(ch in punct_set for ch in s)
        space = any(ch.isspace() for ch in s)
        if is_digits: digits_only += 1
        if is_alpha:  alpha_only += 1
        if punct:     has_punct += 1
        if space:     has_space += 1
        if not (is_digits or is_alpha): mixed += 1
    return {"digits_only": digits_only, "alpha_only": alpha_only, "has_punct": has_punct,
            "has_space": has_space, "mixed": mixed, "total": len(values)}

def common_prefixes(values: Sequence[str], prefix_len: int, top: int) -> List[Tuple[str, int]]:
    from collections import Counter
    prefs = Counter([str(v)[:prefix_len] for v in values if v])
    return prefs.most_common(top)

# --------- core profiling ----------
def profile_column(engine: Engine, table: Table, col_name: str, table_row_count: int) -> ColumnProfile:
    col = table.c[col_name]
    dtype = safe_type_name(col.type)

    nulls, nonnulls = null_vs_nonnull(engine, table, col)
    dc = distinct_count(engine, table, col)

    shape = ShapeInfo()

    if is_numeric(col.type):
        min_v, max_v = min_max_numeric(engine, table, col)

    elif is_textual(col.type):
        min_v, max_v = min_max_lex(engine, table, col)
        len_min, len_max = length_range(engine, table, col)
        shape.length_min = int(len_min) if len_min is not None else None
        shape.length_max = int(len_max) if len_max is not None else None
        vals_sample = sample_nonnull_values(engine, table, col, limit=min(TEXT_SAMPLE_FOR_SHAPE, max(1000, TOP_K * 20)))
        shape.char_classes = char_class_counts_from_sample(vals_sample)
        shape.common_prefixes = common_prefixes(vals_sample, prefix_len=PREFIX_LEN, top=PREFIX_TOP)

    elif is_temporal(col.type) or isinstance(col.type, Boolean):
        min_v, max_v = min_max_lex(engine, table, col)

    else:
        min_v, max_v = min_max_lex(engine, table, col)

    shape.min_value, shape.max_value = min_v, max_v

    topk_vals = topk(engine, table, col, TOP_K)
    sample_vals = distinct_sample(engine, table, col, limit=DISTINCT_SAMPLE_MAX)

    mh = MinHasher(num_perm=MINHASH_PERM)
    for v in sample_vals: mh.update(v)
    sig = mh.digest()

    return ColumnProfile(
        table_name=table.name,
        column_name=col_name,
        data_type=dtype,
        table_row_count=table_row_count,
        null_count=int(nulls),
        non_null_count=int(nonnulls),
        distinct_count=float(dc),
        shape=shape,
        top_k_values=topk_vals,
        distinct_sample=sample_vals,
        minhash_signature=[int(x) for x in sig],
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )

def profile_to_english_description(profile: ColumnProfile) -> str:
    parts = []

    # Basic stats (same as before)
    parts.append(f"Column {profile.column_name} has {profile.null_count} NULL values out of {profile.table_row_count} records.")
    
    # Use ALL ShapeInfo fields
    if profile.shape.length_min is not None and profile.shape.length_max is not None:
        if profile.shape.length_min == profile.shape.length_max:
            parts.append(f"All values are exactly {profile.shape.length_min} characters long.")
        else:
            parts.append(f"Value lengths range from {profile.shape.length_min} to {profile.shape.length_max} characters.")
    
    if profile.shape.common_prefixes:
        prefixes = [f"'{p}' ({c} times)" for p, c in profile.shape.common_prefixes[:3]]
        parts.append(f"Most common prefixes: {', '.join(prefixes)}.")
    
    # Enhanced char_classes usage
    if profile.shape.char_classes and profile.shape.char_classes.get('total', 0) > 0:
        total = profile.shape.char_classes['total']
        patterns = []
        if profile.shape.char_classes.get('digits_only', 0) / total > 0.8:
            patterns.append("mostly numeric")
        if profile.shape.char_classes.get('alpha_only', 0) / total > 0.8:
            patterns.append("mostly alphabetic")
        if profile.shape.char_classes.get('has_punct', 0) / total > 0.5:
            patterns.append("often contains punctuation")
        
        if patterns:
            parts.append(f"Values are {', '.join(patterns)}.")
    
    return " ".join(parts)


def generate_short_summary(english_desc: str, column_name: str, 
                         table_name: str, other_columns: List[str]) -> str:
    """
    Generate a short summary of what a column contains using LLM.
    Requires OPENAI_API_KEY environment variable to be set.
    """

    # Initialize the ChatOpenAI model
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.0  # Keep it deterministic for consistent summaries
    )
        
    # Create the prompt template
    prompt = ChatPromptTemplate.from_template("""
Given this database column information, provide a brief 1-2 sentence description of what this field likely contains:

Column: {column_name}
Table: {table_name}
Other columns in table: {other_columns}
Detailed profile: {english_desc}

Generate a concise summary focusing on the business purpose and data content. Be direct and avoid technical jargon.
""")
        
    # Create the chain and run it
    chain = prompt | llm
    
    # Run the chain with the input variables
    response = chain.invoke({
        "column_name": column_name,
        "table_name": table_name,
        "other_columns": ", ".join(other_columns),
        "english_desc": english_desc
    })
    
    # Extract the content from the response
    return response.content.strip()


def convert_to_pydantic_schema(cp: ColumnProfile, english_desc: str, 
                              short_summary: str, long_summary: str,
                              database_name: str) -> ColumnProfileCreate:
    """Convert ColumnProfile dataclass to ColumnProfileCreate Pydantic model"""
    
    # Convert top_k_values from List[Tuple[str, int]] to List[Dict[str, Any]]
    top_k_dicts = [{"value": val, "count": count} for val, count in cp.top_k_values]
    
    # Convert common_prefixes from List[Tuple[str, int]] to List[Dict[str, Any]]
    prefix_dicts = [{"prefix": prefix, "count": count} for prefix, count in cp.shape.common_prefixes]
    
    return ColumnProfileCreate(
        database_name=database_name,
        table_name=cp.table_name,
        column_name=cp.column_name,
        data_type=cp.data_type,
        table_row_count=cp.table_row_count,
        null_count=cp.null_count,
        non_null_count=cp.non_null_count,
        distinct_count=cp.distinct_count,
        
        # Shape information
        min_value=str(cp.shape.min_value) if cp.shape.min_value is not None else None,
        max_value=str(cp.shape.max_value) if cp.shape.max_value is not None else None,
        length_min=cp.shape.length_min,
        length_max=cp.shape.length_max,
        char_classes=cp.shape.char_classes if cp.shape.char_classes else None,
        common_prefixes=prefix_dicts if prefix_dicts else None,
        
        # Value samples
        top_k_values=top_k_dicts if top_k_dicts else None,
        distinct_sample=cp.distinct_sample if cp.distinct_sample else None,
        minhash_signature=cp.minhash_signature if cp.minhash_signature else None,
        
        # Generated descriptions
        english_description=english_desc,
        short_summary=short_summary,
        long_summary=long_summary,
        vector_embedding=None,  # You might want to generate this separately
        
        generated_at=dt.datetime.fromisoformat(cp.generated_at.replace('Z', '+00:00'))
    )


def save_profile_to_db(session, profile_data: ColumnProfileCreate) -> None:
    """Save a column profile to the database"""
    # Check if profile already exists (upsert behavior)
    existing = session.query(ColumnProfileModel).filter_by(
        database_name=profile_data.database_name,
        table_name=profile_data.table_name,
        column_name=profile_data.column_name
    ).first()
    
    if existing:
        # Update existing record
        for key, value in profile_data.model_dump().items():
            if key != 'id':  # Don't update the ID
                setattr(existing, key, value)
        dbg(f"Updated existing profile for {profile_data.table_name}.{profile_data.column_name}")
    else:
        # Insert new record
        db_profile = ColumnProfileModel(**profile_data.model_dump())
        session.add(db_profile)
        dbg(f"Created new profile for {profile_data.table_name}.{profile_data.column_name}")
    
    session.commit()


async def profile_database(engine: Engine, only_tables: Optional[Sequence[str]] = None, schema: Optional[str] = None,
                     out_path: Optional[str] = None, db_session=None, database_name: str = None) -> List[ColumnProfile]:
    md = MetaData(schema=schema) if schema else MetaData()
    profiles: List[ColumnProfile] = []

    # Reflect only selected tables if provided (faster & avoids system tables)
    tables: List[Table] = []
    if only_tables:
        for name in [t.strip() for t in only_tables if t.strip()]:
            tables.append(Table(name, md, autoload_with=engine, schema=schema))
    else:
        md.reflect(bind=engine, schema=schema)
        tables = list(md.sorted_tables)

    dbg(f"dialect={engine.dialect.name} schema={schema or '(default)'}")
    dbg(f"tables_found={ [t.name for t in tables] }")
    if not tables:
        print("[profile_db] No tables matched the filter; nothing to profile.", file=sys.stderr, flush=True)
        return profiles

    fh = sys.stdout
    fobj = None
    if out_path:
        fobj = open(out_path, "w", encoding="utf-8")
        dbg(f"Writing JSONL to {out_path}")

    for t in tables:
        try:
            row_count = count_rows(engine, t)
        except Exception as e:
            print(f"[profile_db] SKIP table={t.name} (row count failed: {e})", file=sys.stderr, flush=True)
            continue
        
        # Get all column names for context
        other_columns = [col.name for col in t.columns if not isinstance(col.type, LargeBinary)]
        
        for col in t.columns:
            if isinstance(col.type, LargeBinary):
                dbg(f"SKIP column {t.name}.{col.name} (LargeBinary)")
                continue
            try:
                cp = profile_column(engine, t, col.name, row_count)
                english_desc = profile_to_english_description(cp)
                
                # Generate LLM summary
                other_cols = [c for c in other_columns if c != col.name]
                short_summary = generate_short_summary(english_desc, col.name, t.name, other_cols)
                embedding = await embedding_service.generate_embedding(short_summary)
                
                # Combine both descriptions
                long_summary = f"{short_summary} {english_desc}"
                
                print(long_summary, file=fh, flush=True)
                if fobj:
                    print(long_summary, file=fobj, flush=True)
                
                # Save to database if session and database name are provided
                if db_session and database_name:
                    try:
                        profile_schema = convert_to_pydantic_schema(
                            cp, english_desc, short_summary, long_summary, database_name
                        )
                        profile_schema.vector_embedding = embedding
                        save_profile_to_db(db_session, profile_schema)
                        dbg(f"Saved profile for {t.name}.{col.name} to database")
                    except Exception as db_error:
                        print(f"[profile_db] DB SAVE ERROR {t.name}.{col.name}: {db_error}", file=sys.stderr, flush=True)
                
                profiles.append(cp)
            except Exception as e:
                print(f"[profile_db] ERROR {t.name}.{col.name}: {e}", file=sys.stderr, flush=True)
    if fobj:
        fobj.close()
    return profiles

# --------- main ----------
async def main() -> None:
    global DEBUG
    args = parse_args()
    DEBUG = bool(args.debug)

    url = args.url or os.getenv("DATABASE_URL")
    if not url:
        print("ERROR: Provide --url or set DATABASE_URL", file=sys.stderr, flush=True)
        sys.exit(2)

    # Convert asyncpg URL to psycopg2 for synchronous operation
    if "postgresql+asyncpg://" in url:
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    
    engine = create_engine(url, future=True)
    only_tables = [t.strip() for t in args.tables.split(",")] if args.tables else None

    # Set up database session for saving profiles (using same database)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    # Extract database name from URL or use provided name
    database_name = args.database_name or engine.url.database

    random.seed(RANDOM_SEED)
    
    try:
        await profile_database(
            engine, 
            only_tables=only_tables, 
            schema=args.schema, 
            out_path=args.jsonl_out,
            db_session=db_session,
            database_name=database_name
        )
    finally:
        if db_session:
            db_session.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

