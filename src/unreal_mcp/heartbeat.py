"""Heartbeat channel: a persistent TCP link from the Python MCP server to the
``UnrealMCPStatus`` C++ plugin, independent of the Remote Execution protocol.

The server connects once on startup to ``localhost:6690`` (the C++ plugin's
listener), announces itself with a ``connected`` event, then sends a ``heartbeat``
every few seconds. On clean shutdown it sends ``stopped`` so the editor's status
widget updates immediately instead of waiting for the heartbeat timeout.

Wire format is newline-delimited JSON, one object per line::

    {"event": "connected", "pid": 12345}
    {"event": "heartbeat"}
    {"event": "stopped"}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

logger = logging.getLogger(__name__)

_HEARTBEAT_HOST = os.environ.get("UE_MCP_HEARTBEAT_HOST", "127.0.0.1")
_HEARTBEAT_PORT = int(os.environ.get("UE_MCP_HEARTBEAT_PORT", "6690"))
_HEARTBEAT_INTERVAL = float(os.environ.get("UE_MCP_HEARTBEAT_INTERVAL", "5.0"))
_CONNECT_TIMEOUT = 2.0


class HeartbeatClient:
    """Holds a single TCP connection to the C++ plugin's heartbeat listener."""

    def __init__(self, host: str = _HEARTBEAT_HOST, port: int = _HEARTBEAT_PORT) -> None:
        self.host = host
        self.port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    @property
    def connected(self) -> bool:
        return self._writer is not None

    async def connect(self) -> bool:
        """Connect to the heartbeat listener with a 2 s timeout.

        Returns ``True`` on success. A refused/timed-out connection (UE5 not
        running or the plugin not loaded) is silently swallowed and returns
        ``False`` — the server operates normally without a status UI.
        """
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=_CONNECT_TIMEOUT,
            )
            logger.debug("unreal-mcp: heartbeat channel connected to %s:%d", self.host, self.port)
            return True
        except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
            # No listener (UE5 closed or plugin absent) — expected, stay quiet.
            self._reader = None
            self._writer = None
            return False

    async def send(self, event: str, **kwargs: object) -> None:
        """Write ``{"event": event, ...}\\n`` to the socket; drop silently if down."""
        if self._writer is None:
            return
        payload = {"event": event, **kwargs}
        line = (json.dumps(payload) + "\n").encode("utf-8")
        try:
            self._writer.write(line)
            await self._writer.drain()
        except (ConnectionError, OSError) as exc:
            logger.debug("unreal-mcp: heartbeat send failed (%s); marking disconnected", exc)
            self._reader = None
            self._writer = None

    async def close(self) -> None:
        """Close the heartbeat socket if open."""
        if self._writer is None:
            return
        writer = self._writer
        self._reader = None
        self._writer = None
        try:
            writer.close()
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass


async def run_heartbeat_loop(client: HeartbeatClient) -> None:
    """Send ``connected`` once, then ``heartbeat`` every interval until cancelled.

    On cancellation (clean server shutdown) a final ``stopped`` event is sent
    before returning so the C++ plugin updates immediately.
    """
    try:
        await client.send("connected", pid=os.getpid())
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
            await client.send("heartbeat")
    except asyncio.CancelledError:
        await client.send("stopped")
        raise
