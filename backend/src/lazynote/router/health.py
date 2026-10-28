from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health check")
async def health_check():
    return {"status": "ok", "app": "Lazy Note API"}


@router.get("/", summary="Root endpoint")
async def root():
    return {
        "status": "ok",
        "app": "Lazy Note API",
        "docs": "/docs",
        "version": "0.1.0",
    }
