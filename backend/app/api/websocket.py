"""WebSocket endpoint for real-time event broadcasting."""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()

_PING_INTERVAL_SECONDS = 30


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    logger.info("WebSocket connected (%d total)", ws_manager.connection_count())

    ping_task = asyncio.create_task(_ping_loop(websocket))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "pong":
                continue
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        logger.exception("WebSocket error")
    finally:
        ping_task.cancel()
        await ws_manager.disconnect(websocket)


async def _ping_loop(websocket: WebSocket) -> None:
    try:
        while True:
            await asyncio.sleep(_PING_INTERVAL_SECONDS)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except asyncio.CancelledError:
        raise
    except Exception:
        # Connection probably closed — let the receive loop clean up
        pass
