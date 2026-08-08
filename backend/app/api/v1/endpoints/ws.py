import logging
import json
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()

# Global list of connected WebSocket clients
active_connections: list[WebSocket] = []

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"WebSocket client connected. Active: {len(active_connections)}")
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"status": "heartbeat", "received": data}))
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Active: {len(active_connections)}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)


async def _broadcast_raw(msg: str) -> None:
    """Send a pre-serialised message to all live clients, pruning dead ones."""
    if not active_connections:
        return
    dead: list[WebSocket] = []
    for ws in active_connections:
        try:
            await ws.send_text(msg)
        except Exception as e:
            logger.warning(f"WS send failed: {e}")
            dead.append(ws)
    for d in dead:
        if d in active_connections:
            active_connections.remove(d)


async def broadcast_event(event_name: str, payload: dict | None = None) -> None:
    """Broadcast a generic named event (kept for non-cycle callers)."""
    await _broadcast_raw(json.dumps({"event": event_name, "data": payload or {}}))


async def broadcast_cycle_stage(
    cycle_id: str,
    stage: int,
    name: str,
    status: str,                  # RUNNING | COMPLETED | SKIPPED | FAILED
    duration_ms: float | None,
    detail: dict[str, Any],
    error: str | None,
) -> None:
    """Typed cycle.stage event."""
    await _broadcast_raw(json.dumps({
        "type":        "cycle.stage",
        "cycle_id":    cycle_id,
        "stage":       stage,
        "name":        name,
        "status":      status,
        "duration_ms": duration_ms,
        "detail":      detail,
        "error":       error,
    }))


async def broadcast_cycle_complete(
    cycle_id: str,
    summary: dict[str, Any],
) -> None:
    """Typed cycle.complete event."""
    await _broadcast_raw(json.dumps({
        "type":     "cycle.complete",
        "cycle_id": cycle_id,
        "summary":  summary,
    }))
