import os
from pathlib import Path
from typing import Protocol
import aiofiles

from lazynote.config import get_settings


class StorageService(Protocol):
    """Abstract interface for storing raw chunks and master audio."""

    async def save_chunk(self, session_id: str, sequence_number: int, data: bytes) -> str:
        """Save an audio chunk and return its storage path / URI."""
        ...

    async def get_chunk(self, storage_path: str) -> bytes:
        """Read and return chunk bytes from storage."""
        ...

    async def delete_session_files(self, session_id: str) -> None:
        """Remove all temporary storage assets for a session."""
        ...


class LocalDiskStorage:
    """Local filesystem storage driver for development and local testing."""

    def __init__(self, base_dir: str | None = None):
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.UPLOAD_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_dir(self, session_id: str) -> Path:
        session_dir = self.base_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    async def save_chunk(self, session_id: str, sequence_number: int, data: bytes) -> str:
        session_dir = self._get_session_dir(session_id)
        file_path = session_dir / f"chunk_{sequence_number:05d}.webm"
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(data)
        return str(file_path)

    async def get_chunk(self, storage_path: str) -> bytes:
        async with aiofiles.open(storage_path, "rb") as f:
            return await f.read()

    async def delete_session_files(self, session_id: str) -> None:
        session_dir = self.base_dir / session_id
        if session_dir.exists():
            for root, _, files in os.walk(session_dir, topdown=False):
                for f in files:
                    os.remove(os.path.join(root, f))
            os.rmdir(session_dir)


def get_storage_service() -> StorageService:
    """Factory dependency for storage service."""
    return LocalDiskStorage()
