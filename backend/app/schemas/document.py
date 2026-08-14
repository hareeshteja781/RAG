from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: Optional[str]
    file_size: Optional[int]
    created_at: datetime

    class Config:
        orm_mode = True
