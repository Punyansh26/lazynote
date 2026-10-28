from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lazynote.database.models.session import RecordingSession
from lazynote.database.session import get_db
from lazynote.schemas.session import SessionCreate, SessionFinalize, SessionResponse

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new recording session."""
    session = RecordingSession(title=payload.title, status="recording")
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


@router.get("", response_model=List[SessionResponse])
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List recent recording sessions."""
    result = await db.execute(
        select(RecordingSession)
        .order_by(RecordingSession.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Fetch status and details of a single recording session."""
    result = await db.execute(
        select(RecordingSession).where(RecordingSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return session


@router.post("/{session_id}/finalize", response_model=SessionResponse)
async def finalize_session(
    session_id: UUID,
    payload: SessionFinalize,
    db: AsyncSession = Depends(get_db),
):
    """Mark session recording complete and trigger backend pipeline."""
    result = await db.execute(
        select(RecordingSession).where(RecordingSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    session.expected_chunk_count = payload.expected_chunk_count
    session.status = "uploading"
    await db.flush()
    await db.refresh(session)
    return session
