"""In-process WebSocket connection manager.

Single broadcaster used by services to push real-time events to every
connected client. Connections are added/removed from the websocket
endpoint (app.api.websocket).
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, event_type: str, payload: Any) -> None:
        if not self._connections:
            return

        message = json.dumps({"type": event_type, "payload": payload}, default=str)

        dead: list[WebSocket] = []
        # Snapshot to avoid mutation during iteration
        async with self._lock:
            targets = list(self._connections)

        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                logger.debug("WS send failed — marking connection dead")
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)

    def connection_count(self) -> int:
        return len(self._connections)


ws_manager = ConnectionManager()
