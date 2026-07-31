import logging
import json
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
            # Keep client connection open
            data = await websocket.receive_text()
            # Simple echo support or heartbeats
            await websocket.send_text(json.dumps({"status": "heartbeat", "received": data}))
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Active: {len(active_connections)}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)

async def broadcast_event(event_name: str, payload: dict | None = None):
    """Broadcast real-time refresh event to all connected clients."""
    if not active_connections:
        return
    
    msg = json.dumps({
        "event": event_name,
        "data": payload or {}
    })
    
    dead_connections = []
    for ws in active_connections:
        try:
            await ws.send_text(msg)
        except Exception as e:
            logger.warning(f"Failed to send websocket broadcast: {e}")
            dead_connections.append(ws)
            
    for dead in dead_connections:
        if dead in active_connections:
            active_connections.remove(dead)
