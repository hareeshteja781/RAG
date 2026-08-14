from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    processing_status: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentTextResponse(BaseModel):
    document_id: int
    text: str