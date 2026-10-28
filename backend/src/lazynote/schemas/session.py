from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class SessionBase(BaseModel):
    title: str = Field(default="Untitled Lecture", max_length=255)


class SessionCreate(SessionBase):
    pass


class SessionFinalize(BaseModel):
    expected_chunk_count: int = Field(..., ge=1, description="Total number of chunks uploaded")


class SessionResponse(SessionBase):
    id: UUID
    status: str
    expected_chunk_count: int | None = None
    duration_ms: int | None = None
    master_audio_path: str | None = None
    dsp_audio_path: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
