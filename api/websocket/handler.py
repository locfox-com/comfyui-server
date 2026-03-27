# api/websocket/handler.py
from fastapi import WebSocket, WebSocketDisconnect, Query
from typing import Optional
import json
import asyncio
import logging
from datetime import datetime
from utils.token import validate_ws_token
from utils.redis import redis_client

logger = logging.getLogger(__name__)

class WebSocketHandler:
    def __init__(self, websocket: WebSocket, task_id: str):
        self.websocket = websocket
        self.task_id = task_id
        self.connected = True
        self.heartbeat_task: Optional[asyncio.Task] = None

    async def connect(self):
        """Accept WebSocket connection"""
        await self.websocket.accept()
        logger.info(f"WebSocket connected for task {self.task_id}")

    async def send_progress(self, data: dict):
        """Send progress message"""
        if not self.connected:
            return

        message = {
            "type": "progress",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": data
        }

        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send progress: {e}")
            self.connected = False

    async def send_completed(self, result_url: str, metadata: dict = None):
        """Send completion message"""
        if not self.connected:
            return

        message = {
            "type": "completed",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "result_url": result_url,
                "metadata": metadata or {}
            }
        }

        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send completed: {e}")

    async def send_error(self, error: str, code: str = "UNKNOWN_ERROR", details: str = None):
        """Send error message"""
        if not self.connected:
            return

        message = {
            "type": "error",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "error": error,
                "code": code,
                "details": details
            }
        }

        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send error: {e}")

    async def start_heartbeat(self, interval: int = 30, timeout: int = 60):
        """Start heartbeat detection"""
        async def heartbeat():
            while self.connected:
                try:
                    await asyncio.wait_for(
                        self.websocket.ping(),
                        timeout=timeout
                    )
                    await asyncio.sleep(interval)
                except asyncio.TimeoutError:
                    logger.warning(f"WebSocket heartbeat timeout for task {self.task_id}")
                    self.connected = False
                    break
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
                    self.connected = False
                    break

        self.heartbeat_task = asyncio.create_task(heartbeat())

    async def disconnect(self):
        """Disconnect"""
        self.connected = False
        if self.heartbeat_task:
            self.heartbeat_task.cancel()

        try:
            await self.websocket.close()
        except:
            pass

        logger.info(f"WebSocket disconnected for task {self.task_id}")

async def websocket_endpoint(
    websocket: WebSocket,
    task_id: str,
    token: str = Query(...),
    api_key: str = Query(None)
):
    """WebSocket endpoint"""
    # Validate token
    validated_task_id = validate_ws_token(token)

    if not validated_task_id or validated_task_id != task_id:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    # Create handler
    handler = WebSocketHandler(websocket, task_id)

    try:
        await handler.connect()
        await handler.start_heartbeat()

        # Subscribe to Redis progress channel
        pubsub = redis_client.client.pubsub()
        channel = f"task:progress:{task_id}"
        await pubsub.subscribe(channel)

        logger.info(f"Subscribed to progress channel: {channel}")

        # Listen for progress messages
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    await handler.send_progress(data)

                    if data.get('status') == 'completed':
                        await asyncio.sleep(1)
                        break
                    elif data.get('status') == 'failed':
                        await handler.send_error(
                            error=data.get('error', 'Task failed'),
                            code=data.get('error_code', 'TASK_FAILED')
                        )
                        break

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in progress message: {message['data']}")
                except Exception as e:
                    logger.error(f"Error handling progress message: {e}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected by client for task {task_id}")
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
        await handler.send_error(str(e), "WEBSOCKET_ERROR")
    finally:
        await handler.disconnect()
        await pubsub.unsubscribe(channel)
