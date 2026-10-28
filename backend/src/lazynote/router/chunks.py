from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lazynote.database.models.chunk import AudioChunk
from lazynote.database.models.session import RecordingSession
from lazynote.database.session import get_db
from lazynote.schemas.chunk import ChunkResponse
from lazynote.services.storage import StorageService, get_storage_service

router = APIRouter(prefix="/sessions/{session_id}/chunks", tags=["Chunks"])


@router.post("", response_model=ChunkResponse, status_code=status.HTTP_201_CREATED)
async def upload_chunk(
    session_id: UUID,
    sequence_number: int = Form(...),
    start_offset_ms: int = Form(...),
    end_offset_ms: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
):
    """Receive and persist a 30s WebM audio chunk from the recording client."""
    # Verify session exists
    res = await db.execute(
        select(RecordingSession).where(RecordingSession.id == session_id)
    )
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded chunk cannot be empty",
        )

    # Persist audio slice via storage service
    storage_path = await storage.save_chunk(
        session_id=str(session_id),
        sequence_number=sequence_number,
        data=file_bytes,
    )

    # Record in database
    chunk = AudioChunk(
        session_id=session_id,
        sequence_number=sequence_number,
        start_offset_ms=start_offset_ms,
        end_offset_ms=end_offset_ms,
        byte_length=len(file_bytes),
        storage_path=storage_path,
        is_verified=True,
    )
    db.add(chunk)
    await db.flush()
    await db.refresh(chunk)
    return chunk
