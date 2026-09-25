from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PARSED = "parsed"
    FAILED = "failed"

class DocumentBase(BaseModel):
    filename: str
    file_type: str
    file_size: Optional[int] = None
    word_count: Optional[int] = None
    page_count: Optional[int] = None

class DocumentResponse(DocumentBase):
    id: int
    status: DocumentStatus
    progress: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    extra_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class DocumentTextResponse(BaseModel):
    document_id: int
    text: str
    word_count: int
