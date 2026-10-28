from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ChunkUploadMetadata(BaseModel):
    sequence_number: int = Field(..., ge=0)
    start_offset_ms: int = Field(..., ge=0)
    end_offset_ms: int = Field(..., ge=0)


class ChunkResponse(BaseModel):
    id: UUID
    session_id: UUID
    sequence_number: int
    start_offset_ms: int
    end_offset_ms: int
    byte_length: int
    is_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
