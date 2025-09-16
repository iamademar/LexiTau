import asyncio
import sys
import os
import json
sys.path.append('/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from openai import AsyncOpenAI
from typing import List, Dict

from app.core.settings import get_settings
from app.services.embedding_service import embedding_service
from app.services.value_index_service import ValueLSHIndex
from app.services.schema_linking_orchestrator_service import run_sql_first_linking, LLMClient
from app.services.extractor_fields_and_literals_service import extract_fields_and_literals
from app.services.openai_llm_service import OpenAILLMService

# Setup database connection
settings = get_settings()
engine = create_engine(settings.database_url.replace('+asyncpg', ''))
SessionLocal = sessionmaker(bind=engine)


async def test_orchestrator():
    """Test the schema linking orchestrator service manually"""

    # Test questions
    test_questions = [
        "How many invoices did I upload in the last month?",
        "Show me all documents from Aotearoa Electrical",
        "What's the total value of expenses in 2025?",
        "List all categories with their document counts"
    ]

    print("Testing Schema Linking Orchestrator Service")
    print("=" * 60)

    db = SessionLocal()

    try:
        # Initialize services
        print("1. Initializing Value LSH Index...")
        value_index = ValueLSHIndex(threshold=0.4, num_perm=128, k=4)
        value_index.build_from_db(db)

        stats = value_index.get_stats()
        print(f"   Index built: {stats['is_built']}")
        print(f"   Columns indexed: {stats['num_columns']}")
        print(f"   Threshold: {stats['threshold']}")
        print()

        # Test value index first
        print("2. Testing Value Index lookups...")
        test_literals = ["Aotearoa Electrical", "2025", "invoice", "1", "expense"]

        for literal in test_literals:
            candidates = value_index.lookup_literal(literal)
            print(f"   '{literal}' -> {len(candidates)} candidates: {candidates[:3]}")  # Show first 3
        print()

        # Initialize LLM client
        print("3. Initializing LLM Client...")
        openai_client = AsyncOpenAI()
        llm = OpenAILLMService(openai_client, model="gpt-4o-mini", temperature=0.0)
        print("   LLM client ready")
        print()

        # Test each question
        for i, question in enumerate(test_questions, 1):
            print(f"4.{i} Testing Question: '{question}'")
            print("-" * 50)

            try:
                # Run the orchestrator
                final_sql, linked_fields = await run_sql_first_linking(
                    db=db,
                    question=question,
                    llm=llm,
                    embedding_service=embedding_service,
                    value_index=value_index,
                    max_retry=2,
                    M=20,  # Smaller for testing
                    P=3,   # Max 3 columns per table
                    T=4,   # Max 4 tables
                    trim_long_to_examples=True
                )

                print(f"   Final SQL Generated:")
                print("   " + "-" * 30)
                for line in final_sql.split('\n'):
                    print(f"   {line}")
                print("   " + "-" * 30)

                print(f"   Linked Fields ({len(linked_fields)}):")
                fields_by_table = {}
                for table, column in linked_fields:
                    if table not in fields_by_table:
                        fields_by_table[table] = []
                    fields_by_table[table].append(column)

                for table in sorted(fields_by_table.keys()):
                    columns = sorted(fields_by_table[table])
                    print(f"     {table}: {', '.join(columns)}")

                # Analyze the final SQL
                print(f"   SQL Analysis:")
                try:
                    fields_final, literals_final = extract_fields_and_literals(final_sql)
                    print(f"     Fields in SQL: {len(fields_final)}")
                    print(f"     Literals in SQL: {len(literals_final)} -> {sorted(literals_final)}")
                except Exception as e:
                    print(f"     SQL Analysis Error: {e}")

                print()

            except Exception as e:
                print(f"   ERROR: {e}")
                import traceback
                traceback.print_exc()
                print()

    except Exception as e:
        print(f"Setup Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()

async def test_value_index_only():
    """Test just the value index functionality"""
    print("Testing Value Index Service Only")
    print("=" * 40)

    db = SessionLocal()

    try:
        # Initialize and build index
        print("Building Value LSH Index...")
        value_index = ValueLSHIndex(threshold=0.4, num_perm=128, k=4)
        value_index.build_from_db(db)

        stats = value_index.get_stats()
        print(f"Stats: {stats}")
        print()

        # Test lookups with various literals from the database
        test_literals = [
            "Aotearoa Electrical",
            "Kiwi Clean Co",
            "Tāmaki Plumbing & Gas",
            "2025",
            "2",
            "3",
            "invoice",
            "business",
            "document"
        ]

        print("Testing literal lookups:")
        for literal in test_literals:
            candidates = value_index.lookup_literal(literal)
            print(f"  '{literal}' -> {candidates}")

        print()
        print("Testing utility methods:")

        # Test get_candidate_columns_for_table
        tables = ["businesses", "documents", "categories"]
        for table in tables:
            cols = value_index.get_candidate_columns_for_table(table)
            print(f"  {table} indexed columns: {cols}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "index-only":
        asyncio.run(test_value_index_only())
    else:
        asyncio.run(test_orchestrator())