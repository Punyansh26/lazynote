import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from lazynote.database.session import Base


def utc_now():
    return datetime.now(timezone.utc)


class RecordingSession(Base):
    """Represents a recorded lecture session lifecycle."""

    __tablename__ = "recording_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False, default="Untitled Lecture")
    status = Column(
        String(50), nullable=False, default="recording"
    )  # recording | uploading | processing | completed | failed
    expected_chunk_count = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    master_audio_path = Column(String(512), nullable=True)
    dsp_audio_path = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    chunks = relationship(
        "AudioChunk",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AudioChunk.sequence_number",
    )
    transcript_segments = relationship(
        "TranscriptSegment",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="TranscriptSegment.sequence_index",
    )
    notes = relationship(
        "NoteArtifact",
        back_populates="session",
        cascade="all, delete-orphan",
    )
