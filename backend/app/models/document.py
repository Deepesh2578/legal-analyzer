from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Enum
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PARSED = "parsed"
    FAILED = "failed"

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    file_type = Column(String(50), nullable=True)

    raw_text = Column(Text, nullable=True)
    processed_text = Column(Text, nullable=True)

    status = Column(Enum(DocumentStatus), default=DocumentStatus.PENDING)
    progress = Column(Integer, default=0)

    page_count = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # IMPORTANT: avoid using 'metadata' as column name (reserved by SQLAlchemy)
    extra_data = Column(Text, nullable=True)
