from collections.abc import AsyncIterator

import pytest
from fastmcp import Client

from app.infrastructure.settings import Settings
from app.presentation.mcp_server import create_mcp


@pytest.fixture
async def mcp_client(
    settings: Settings, migrated_database: None
) -> AsyncIterator[Client]:
    async with Client(create_mcp(settings)) as client:
        yield client
