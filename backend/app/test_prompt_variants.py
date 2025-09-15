import asyncio
import sys
import os
import json
sys.path.append('/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from openai import AsyncOpenAI

from app.core.settings import get_settings
from app.services.embedding_service import embedding_service
from app.services.prompt_variants_service import (
    build_five_prompt_variants,
    generate_raw_responses_for_five_variants,   # <-- new
)
from app.services.extractor_fields_and_literals_service import extract_fields_and_literals

# Setup database connection
settings = get_settings()
engine = create_engine(settings.database_url.replace('+asyncpg', ''))
SessionLocal = sessionmaker(bind=engine)

# Setup OpenAI client (will use OPENAI_API_KEY env var)
client = AsyncOpenAI()

def _dump_openai_response(resp) -> str:
    """
    Pretty-print an OpenAI SDK response. Uses model_dump_json if available,
    otherwise falls back to str().
    """
    # Newer SDKs: Pydantic models support model_dump_json/model_dump
    for attr in ("model_dump_json", "to_json"):
        if hasattr(resp, attr):
            try:
                return getattr(resp, attr)(indent=2)
            except TypeError:
                # some to_json may not accept indent
                return getattr(resp, attr)()
    if hasattr(resp, "model_dump"):
        try:
            return json.dumps(resp.model_dump(), indent=2)
        except Exception:
            pass
    # Oldest fallback
    try:
        return json.dumps(resp, indent=2, default=str)
    except Exception:
        return str(resp)

async def test_prompt_variants():
    """Test the prompt variants service (build + raw LLM responses)"""
    question = "How many invoices did I upload in the last month?"

    print(f"Testing question: {question}")
    print("=" * 60)

    db = SessionLocal()
    try:
        # 1) Build the five variants (for preview/debug)
        prompt_result = await build_five_prompt_variants(
            db=db,
            question=question,
            embedding_service=embedding_service,
            M=20,  # Smaller for testing
            P=3,   # Max 3 columns per table
            T=4,   # Max 4 tables
        )

        print(f"Generated {len(prompt_result.variants)} variants for question:")
        print(f"'{prompt_result.question}'\n")

        # 2) Get RAW OpenAI responses for each variant
        llm_results = await generate_raw_responses_for_five_variants(
            db=db,
            question=question,
            embedding_service=embedding_service,
            llm_client=client,
            model="gpt-4o-mini",
            temperature=0.0,
            max_tokens=600,
            M=20, P=3, T=4,
        )

        # 3) Process each variant: extract SQL and analyze with SQL extractor
        all_linked_fields = set()

        for i, variant in enumerate(prompt_result.variants, 1):
            print(f"=== VARIANT {i}: {variant.name.upper()} ===")
            print(f"Schema: {variant.schema_kind}, Profile: {variant.profile_kind}")
            print(f"Tables: {variant.context_preview['table_count']}")

            # Show table preview
            for table in variant.context_preview['tables']:
                cols = ', '.join(table['columns'][:3])
                print(f"  - {table['name']} ({len(table['columns'])} cols): {cols}")

            # Show message structure
            print(f"Messages: {len(variant.messages)}")
            for j, msg in enumerate(variant.messages):
                role = msg['role']
                content_preview = msg['content'][:100].replace('\n', ' ')
                print(f"  {j+1}. {role}: {content_preview}...")

            # Match the same index from llm_results
            raw = llm_results.results[i - 1]

            # Extract SQL from OpenAI response
            try:
                if hasattr(raw.response, 'choices') and raw.response.choices:
                    sql_content = raw.response.choices[0].message.content
                else:
                    sql_content = str(raw.response)

                # Clean up SQL (remove markdown if present)
                sql_content = sql_content.strip()
                if sql_content.startswith("```sql"):
                    sql_content = sql_content[6:]
                elif sql_content.startswith("```"):
                    sql_content = sql_content[3:]
                if sql_content.endswith("```"):
                    sql_content = sql_content[:-3]
                sql_content = sql_content.strip()

                print(f"\n--- EXTRACTED SQL ---")
                print(sql_content)

                # Use SQL extractor to get fields and literals
                fields_q, lits_q = extract_fields_and_literals(sql_content)

                print(f"\n--- SQL ANALYSIS ---")
                print(f"Extracted Fields ({len(fields_q)}):")
                for table, column in sorted(fields_q):
                    print(f"  - {table}.{column}")

                print(f"\nExtracted Literals ({len(lits_q)}):")
                for lit in sorted(lits_q):
                    print(f"  - '{lit}'")

                # Accumulate fields for final union
                all_linked_fields.update(fields_q)

                print(f"\n(latency: {raw.latency_ms} ms, profile={raw.profile_kind}, schema={raw.schema_kind})")

            except Exception as e:
                print(f"\n--- SQL EXTRACTION ERROR ---")
                print(f"Error: {e}")
                print("\n--- RAW OPENAI RESPONSE ---")
                print(_dump_openai_response(raw.response))
                print(f"(latency: {raw.latency_ms} ms, profile={raw.profile_kind}, schema={raw.schema_kind})")

            print()

        # 4) Summary of all linked fields across variants
        print("=" * 60)
        print(f"SUMMARY: Total Linked Fields Across All Variants ({len(all_linked_fields)})")
        print("=" * 60)

        # Group by table for better readability
        fields_by_table = {}
        for table, column in all_linked_fields:
            if table not in fields_by_table:
                fields_by_table[table] = []
            fields_by_table[table].append(column)

        for table in sorted(fields_by_table.keys()):
            columns = sorted(fields_by_table[table])
            print(f"{table}: {', '.join(columns)}")

        print(f"\nTotal unique (table, column) pairs: {len(all_linked_fields)}")
        print(f"Total tables involved: {len(fields_by_table)}")

    except Exception as e:
        print(f"Error testing prompt variants: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_prompt_variants())
