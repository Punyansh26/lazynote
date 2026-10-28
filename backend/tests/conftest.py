import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lazynote.main import app


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
