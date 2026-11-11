import os
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from app.infrastructure.settings import Settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.slow
async def test_connect_over_stdio(settings: Settings, migrated_database: None) -> None:
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "app.presentation.mcp_server"],
        env={**os.environ, "DATABASE_URL": settings.database_url},
        cwd=str(PROJECT_ROOT),
    )

    async with Client(transport) as client:
        tools = await client.list_tools()

    assert len(tools) == 8
