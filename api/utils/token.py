# api/utils/token.py
import secrets
import logging
from typing import Tuple
from config import settings

logger = logging.getLogger(__name__)

def generate_ws_token() -> str:
    """Generate WebSocket Token"""
    token = secrets.token_hex(32)
    return token

def save_ws_token(token: str, task_id: str, ttl: int = None) -> bool:
    """Save WebSocket Token to Redis"""
    from utils.redis import redis_client

    if ttl is None:
        ttl = settings.ws_token_ttl

    return redis_client.set_ws_token(token, task_id, ttl)

def validate_ws_token(token: str) -> str | None:
    """Validate WebSocket Token and return task_id"""
    from utils.redis import redis_client

    task_id = redis_client.get_ws_token_task_id(token)

    if not task_id:
        logger.warning(f"Invalid or expired WebSocket token")
        return None

    return task_id
