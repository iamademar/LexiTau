import asyncio
import sys
sys.path.append('/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Set, Tuple

from app.core.settings import get_settings
from app.services.embedding_service import embedding_service
from app.services.value_index_service import ValueLSHIndex
from app.services.schema_linking_orchestrator_service import run_sql_first_linking, LLMClient
from app.services.extractor_fields_and_literals_service import extract_fields_and_literals

# Setup database connection
settings = get_settings()
engine = create_engine(settings.database_url.replace('+asyncpg', ''))
SessionLocal = sessionmaker(bind=engine)

class MockLLMClient:
    """Mock LLM client that returns predictable SQL responses"""

    def __init__(self):
        self.call_count = 0

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """Generate mock SQL responses based on call patterns"""
        self.call_count += 1

        # Analyze the user message for the question
        user_content = ""
        for msg in messages:
            if msg["role"] == "user":
                user_content = msg["content"].lower()
                break

        # Return different SQL based on the question content
        if "invoice" in user_content and "month" in user_content:
            return """
            SELECT COUNT(*) as invoice_count
            FROM documents d
            WHERE d.document_type = 'INVOICE'
            AND d.created_at >= CURRENT_DATE - INTERVAL '30 days'
            """

        elif "aotearoa electrical" in user_content:
            return """
            SELECT d.*
            FROM documents d
            JOIN businesses b ON d.business_id = b.id
            WHERE b.name = 'Aotearoa Electrical'
            """

        elif "total value" in user_content and "expense" in user_content:
            return """
            SELECT SUM(ef.total_amount) as total_expenses
            FROM documents d
            JOIN extracted_fields ef ON d.id = ef.document_id
            WHERE d.classification = 'EXPENSE'
            AND EXTRACT(YEAR FROM d.created_at) = 2025
            """

        elif "categories" in user_content and "document count" in user_content:
            return """
            SELECT c.name, COUNT(d.id) as document_count
            FROM categories c
            LEFT JOIN documents d ON c.id = d.category_id
            GROUP BY c.id, c.name
            ORDER BY document_count DESC
            """

        elif "revise" in user_content:
            # This is a revision request - try to incorporate the suggested fields
            return """
            SELECT COUNT(*) as invoice_count
            FROM documents d
            JOIN businesses b ON d.business_id = b.id
            WHERE d.document_type = 'INVOICE'
            AND d.created_at >= CURRENT_DATE - INTERVAL '1 month'
            AND b.name IS NOT NULL
            """

        else:
            # Default fallback
            return """
            SELECT COUNT(*) as total_documents
            FROM documents d
            WHERE d.created_at IS NOT NULL
            """

async def test_orchestrator_with_mock():
    """Test the orchestrator with a mock LLM that generates predictable responses"""

    test_questions = [
        "How many invoices did I upload in the last month?",
        "Show me all documents from Aotearoa Electrical",
        "What's the total value of expenses in 2025?",
        "List all categories with their document counts"
    ]

    print("Testing Schema Linking Orchestrator with Mock LLM")
    print("=" * 60)

    db = SessionLocal()

    try:
        # Initialize services
        print("1. Initializing Value LSH Index...")
        value_index = ValueLSHIndex(threshold=0.3, num_perm=128, k=4)  # Lower threshold for more matches
        value_index.build_from_db(db)

        stats = value_index.get_stats()
        print(f"   Index built: {stats['is_built']}")
        print(f"   Columns indexed: {stats['num_columns']}")
        print(f"   Threshold: {stats['threshold']}")
        print()

        # Initialize mock LLM
        print("2. Initializing Mock LLM Client...")
        llm = MockLLMClient()
        print("   Mock LLM client ready")
        print()

        # Test each question
        for i, question in enumerate(test_questions, 1):
            print(f"3.{i} Testing Question: '{question}'")
            print("-" * 50)

            try:
                # Run the orchestrator
                final_sql, linked_fields = await run_sql_first_linking(
                    db=db,
                    question=question,
                    llm=llm,
                    embedding_service=embedding_service,
                    value_index=value_index,
                    max_retry=1,  # Limit retries for testing
                    M=15,  # Smaller for testing
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
                    print(f"     Fields in final SQL: {len(fields_final)}")
                    for table, column in sorted(fields_final):
                        print(f"       - {table}.{column}")
                    print(f"     Literals in final SQL: {sorted(literals_final)}")

                    # Test literal lookup for interesting literals
                    for literal in literals_final:
                        if literal not in ['1', '30', '2025']:  # Skip common numbers
                            candidates = value_index.lookup_literal(literal)
                            if candidates:
                                print(f"       Literal '{literal}' found in: {candidates}")

                except Exception as e:
                    print(f"     SQL Analysis Error: {e}")

                print(f"   Total LLM calls made: {llm.call_count}")
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

async def test_individual_components():
    """Test individual components in isolation"""
    print("Testing Individual Components")
    print("=" * 40)

    db = SessionLocal()

    try:
        # Test 1: Extract fields and literals from sample SQL
        print("1. Testing SQL Field/Literal Extraction:")
        sample_sql = """
        SELECT COUNT(*) as invoice_count
        FROM documents d
        JOIN businesses b ON d.business_id = b.id
        WHERE d.document_type = 'INVOICE'
        AND d.created_at >= '2025-01-01'
        AND b.name = 'Aotearoa Electrical'
        """

        fields, literals = extract_fields_and_literals(sample_sql)
        print(f"   Fields: {sorted(fields)}")
        print(f"   Literals: {sorted(literals)}")
        print()

        # Test 2: Value index lookups
        print("2. Testing Value Index Lookups:")
        value_index = ValueLSHIndex(threshold=0.3, num_perm=128, k=4)
        value_index.build_from_db(db)

        test_literals = ['INVOICE', 'Aotearoa Electrical', '2025-01-01']
        for literal in test_literals:
            candidates = value_index.lookup_literal(literal)
            print(f"   '{literal}' -> {candidates[:5]}")  # Show first 5
        print()

        # Test 3: Embedding service (if available)
        print("3. Testing Embedding Service:")
        try:
            embedding = await embedding_service.generate_embedding("test query about invoices")
            if embedding:
                print(f"   Embedding generated: {len(embedding)} dimensions")
                print(f"   First 5 values: {embedding[:5]}")
            else:
                print("   No embedding generated")
        except Exception as e:
            print(f"   Embedding error: {e}")

    except Exception as e:
        print(f"Component test error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "components":
        asyncio.run(test_individual_components())
    else:
        asyncio.run(test_orchestrator_with_mock())