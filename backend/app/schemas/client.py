from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ClientBase(BaseModel):
    name: str


class ClientCreate(ClientBase):
    pass


class Client(ClientBase):
    id: int
    business_id: int
    created_at: datetime

    class Config:
        from_attributes = True