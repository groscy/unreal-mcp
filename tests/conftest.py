"""Shared pytest fixtures and configuration."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_connection():
    """Return a mock UEConnection for testing tools without a live UE instance."""
    conn = MagicMock()
    conn.is_connected = True
    return conn
