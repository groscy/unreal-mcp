"""Shared pytest fixtures and configuration."""
from unittest.mock import MagicMock, patch

import pytest

from unreal_mcp.connection import ConnectionState


@pytest.fixture
def mock_connection():
    """Return a mock UEConnection for testing tools without a live UE instance."""
    conn = MagicMock()
    conn.state = ConnectionState.CONNECTED
    return conn
