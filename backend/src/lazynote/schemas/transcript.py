from datetime import datetime
from typing import Any, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class TranscriptSegmentResponse(BaseModel):
    id: UUID
    session_id: UUID
    sequence_index: int
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NoteArtifactResponse(BaseModel):
    id: UUID
    session_id: UUID
    title: str
    markdown_content: str
    summary: str | None = None
    quiz_json: Any | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LectureNotesPackage(BaseModel):
    session_id: UUID
    title: str
    transcripts: List[TranscriptSegmentResponse]
    notes: NoteArtifactResponse | None = None
