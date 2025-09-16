# backend/app/services/openai_llm_service.py
from typing import List, Dict
from openai import AsyncOpenAI
import logging

logger = logging.getLogger(__name__)

class OpenAILLMService:
    """OpenAI LLM service that conforms to LLMClient protocol"""

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
                max_tokens=800  # Increased for better SQL generation
            )

            content = response.choices[0].message.content
            if not content:
                logger.warning("Empty response from OpenAI")
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
            logger.error(f"OpenAI LLM Error: {e}")
            return f"-- Error: {e}"