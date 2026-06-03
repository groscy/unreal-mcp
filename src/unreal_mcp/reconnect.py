"""Background asyncio task that reconnects the Remote Execution channel.

This task is the *sole* owner of reconnection attempts. Inline tool calls never
reconnect — they return an error immediately when the connection is not
``CONNECTED`` (see ``UEConnection.execute``). When a connection drops mid-session
the connection's state moves to ``RECONNECTING``; this loop notices any
non-connected state and retries with exponential backoff.
"""

from __future__ import annotations

import asyncio
import logging

from .connection import ConnectionState, UEConnection

logger = logging.getLogger(__name__)

# Backoff schedule: 1 → 2 → 4 → 8 → 16 → 30 s (then hold at the cap).
_INITIAL_DELAY = 1.0
_MAX_DELAY = 30.0
# Log every attempt at DEBUG; escalate to WARNING every N consecutive failures.
_WARN_EVERY = 5

_RECONNECT_STATES = (ConnectionState.DISCONNECTED, ConnectionState.RECONNECTING)


async def run_reconnect_loop(conn: UEConnection) -> None:
    """Monitor ``conn.state`` and retry the RE connection with exponential backoff.

    Runs until cancelled (on server shutdown). When connected, it idles cheaply;
    when disconnected, it retries on the backoff schedule, resetting the delay to
    1 s on a successful (re)connect.
    """
    while True:
        if conn.state not in _RECONNECT_STATES:
            # Connected (or actively connecting on another path) — idle.
            conn._reconnect_delay = _INITIAL_DELAY
            conn._reconnect_attempts = 0
            await asyncio.sleep(1.0)
            continue

        # connect() is blocking (UDP discovery + sleeps); run off the event loop.
        ok = await asyncio.to_thread(conn.connect)
        if ok:
            logger.info("unreal-mcp: reconnected to UE5 editor")
            conn._reconnect_delay = _INITIAL_DELAY
            conn._reconnect_attempts = 0
            continue

        conn._reconnect_attempts += 1
        delay = conn._reconnect_delay
        if conn._reconnect_attempts % _WARN_EVERY == 0:
            logger.warning(
                "unreal-mcp: still cannot reach UE5 editor after %d attempts; "
                "retrying every %.0f s",
                conn._reconnect_attempts,
                delay,
            )
        else:
            logger.debug(
                "unreal-mcp: reconnect attempt %d failed; retrying in %.0f s",
                conn._reconnect_attempts,
                delay,
            )

        await asyncio.sleep(delay)
        conn._reconnect_delay = min(conn._reconnect_delay * 2, _MAX_DELAY)
