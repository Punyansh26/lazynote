from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lazynote.config import get_settings
from lazynote.router import api_v1_router, health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown hooks."""
    settings = get_settings()
    # Startup: ensure upload directory exists
    from pathlib import Path
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown hooks (if any)



def create_app() -> FastAPI:
    """FastAPI application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Classroom lecture audio capture, DSP, transcription, and notes engine",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(api_v1_router)

    return app


app = create_app()


def main():
    """Run uvicorn development server from CLI."""
    import uvicorn
    settings = get_settings()
    uvicorn.run("lazynote.main:app", host="0.0.0.0", port=settings.PORT, reload=settings.DEBUG)


if __name__ == "__main__":
    main()
