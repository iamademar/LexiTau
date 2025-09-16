from typing import List, Optional
from langchain_openai import OpenAIEmbeddings
from sqlalchemy.orm import Session
from ..core.settings import get_settings
from ..models.column_profile import ColumnProfile

class EmbeddingService:
    def __init__(self):
        settings = get_settings()
        self.embeddings = OpenAIEmbeddings(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model
        )
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        if not text or not text.strip():
            return None
        
        try:
            embedding = await self.embeddings.aembed_query(text.strip())
            return embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        valid_texts = [text.strip() for text in texts if text and text.strip()]
        if not valid_texts:
            return []
        
        try:
            embeddings = await self.embeddings.aembed_documents(valid_texts)
            return embeddings
        except Exception as e:
            print(f"Error generating embeddings: {e}")
            return []
    
    def update_column_profile_embedding(
        self, 
        db: Session, 
        profile_id: int, 
        embedding: List[float]
    ) -> bool:
        """Update a column profile with its embedding"""
        try:
            profile = db.query(ColumnProfile).filter(ColumnProfile.id == profile_id).first()
            if profile:
                profile.vector_embedding = embedding
                db.commit()
                return True
            return False
        except Exception as e:
            print(f"Error updating embedding: {e}")
            db.rollback()
            return False


# Global instance
embedding_service = EmbeddingService()
