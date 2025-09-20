from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    content_text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
