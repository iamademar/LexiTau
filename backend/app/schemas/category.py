from pydantic import BaseModel
from datetime import datetime


class CategoryBase(BaseModel):
    name: str


class Category(CategoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True