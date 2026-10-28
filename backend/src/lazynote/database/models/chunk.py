import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from lazynote.database.session import Base


def utc_now():
    return datetime.now(timezone.utc)


class AudioChunk(Base):
    """Represents a client-uploaded 30s audio slice."""

    __tablename__ = "audio_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recording_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_number = Column(Integer, nullable=False)
    start_offset_ms = Column(Integer, nullable=False)
    end_offset_ms = Column(Integer, nullable=False)
    byte_length = Column(Integer, nullable=False)
    storage_path = Column(String(512), nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    session = relationship("RecordingSession", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("session_id", "sequence_number", name="uq_session_chunk_seq"),
    )
