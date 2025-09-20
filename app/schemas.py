from pydantic import BaseModel
from datetime import datetime


class DocumentCreate(BaseModel):
    filename: str
    content_text: str


class DocumentRead(DocumentCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True
