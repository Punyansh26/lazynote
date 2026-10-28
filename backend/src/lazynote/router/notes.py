from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lazynote.database.models.session import RecordingSession
from lazynote.database.models.transcript import NoteArtifact, TranscriptSegment
from lazynote.database.session import get_db
from lazynote.schemas.transcript import (
    LectureNotesPackage,
    NoteArtifactResponse,
    TranscriptSegmentResponse,
)

router = APIRouter(prefix="/sessions/{session_id}", tags=["Notes & Transcripts"])


@router.get("/notes", response_model=NoteArtifactResponse)
async def get_session_notes(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve generated study notes for a session."""
    result = await db.execute(
        select(NoteArtifact).where(NoteArtifact.session_id == session_id)
    )
    notes = result.scalar_one_or_none()
    if not notes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notes for session {session_id} not found or still generating",
        )
    return notes


@router.get("/transcripts", response_model=List[TranscriptSegmentResponse])
async def get_session_transcripts(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve chronological timestamped transcript stream for a session."""
    result = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.session_id == session_id)
        .order_by(TranscriptSegment.sequence_index.asc())
    )
    return result.scalars().all()


@router.get("/package", response_model=LectureNotesPackage)
async def get_full_package(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve combined package of transcripts and study notes."""
    sess_res = await db.execute(
        select(RecordingSession).where(RecordingSession.id == session_id)
    )
    session = sess_res.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    trans_res = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.session_id == session_id)
        .order_by(TranscriptSegment.sequence_index.asc())
    )
    transcripts = trans_res.scalars().all()

    notes_res = await db.execute(
        select(NoteArtifact).where(NoteArtifact.session_id == session_id)
    )
    notes = notes_res.scalar_one_or_none()

    return LectureNotesPackage(
        session_id=session.id,
        title=session.title,
        transcripts=transcripts,
        notes=notes,
    )
