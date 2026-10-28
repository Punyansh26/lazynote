from fastapi import APIRouter

from lazynote.router.chunks import router as chunks_router
from lazynote.router.health import router as health_router
from lazynote.router.notes import router as notes_router
from lazynote.router.sessions import router as sessions_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(sessions_router)
api_v1_router.include_router(chunks_router)
api_v1_router.include_router(notes_router)

__all__ = ["health_router", "api_v1_router"]
