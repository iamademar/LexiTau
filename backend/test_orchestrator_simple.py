import asyncio
import sys
sys.path.append('/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from openai import AsyncOpenAI
from typing import List, Dict

from app.core.settings import get_settings
from app.services.embedding_service import embedding_service
from app.services.value_index_service import ValueLSHIndex
from app.services.schema_linking_orchestrator_service import run_sql_first_linking

# Setup database connection
settings = get_settings()
engine = create_engine(settings.database_url.replace('+asyncpg', ''))
SessionLocal = sessionmaker(bind=engine)

class OpenAILLMClient:
    """Wrapper to make OpenAI client conform to LLMClient protocol"""
    def __init__(self, client: AsyncOpenAI, model: str = "gpt-4o-mini", temperature: float = 0.0):
        self.client = client
        self.model = model
        self.temperature = temperature

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """Convert messages to OpenAI format and get response"""
        try:
            # Convert to OpenAI format if needed
            openai_messages = []
            for msg in messages:
                openai_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=self.temperature,
                max_tokens=400
            )

            content = response.choices[0].message.content
            if not content:
                return ""

            # Clean up SQL if wrapped in markdown
            content = content.strip()
            if content.startswith("```sql"):
                content = content[6:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            return content.strip()

        except Exception as e:
            print(f"LLM Error: {e}")
            return f"-- Error: {e}"

async def test_simple():
    """Test with one question using real OpenAI"""
    question = "How many invoices did I upload in the last month?"

    print("Testing Schema Linking Orchestrator with Real OpenAI")
    print("=" * 60)
    print(f"Question: {question}")
    print()

    db = SessionLocal()

    try:
        # Initialize services
        print("Initializing services...")
        value_index = ValueLSHIndex(threshold=0.4, num_perm=128, k=4)
        value_index.build_from_db(db)

        openai_client = AsyncOpenAI()
        llm = OpenAILLMClient(openai_client, model="gpt-4o-mini", temperature=0.0)

        print(f"Value index: {value_index.get_stats()['num_columns']} columns indexed")
        print("Running orchestrator...")
        print()

        # Run the orchestrator
        final_sql, linked_fields = await run_sql_first_linking(
            db=db,
            question=question,
            llm=llm,
            embedding_service=embedding_service,
            value_index=value_index,
            max_retry=1,  # Limit retries
            M=10,  # Smaller for testing
            P=3,   # Max 3 columns per table
            T=3,   # Max 3 tables
            trim_long_to_examples=True
        )

        print("RESULT:")
        print("-" * 40)
        print("Final SQL:")
        for line in final_sql.split('\n'):
            print(f"  {line}")

        print(f"\nLinked Fields ({len(linked_fields)}):")
        fields_by_table = {}
        for table, column in linked_fields:
            if table not in fields_by_table:
                fields_by_table[table] = []
            fields_by_table[table].append(column)

        for table in sorted(fields_by_table.keys()):
            columns = sorted(fields_by_table[table])
            print(f"  {table}: {', '.join(columns)}")

        print("-" * 40)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_simple())