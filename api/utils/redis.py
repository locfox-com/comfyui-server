# api/utils/redis.py
import redis
import json
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password if settings.redis_password else None,
            db=settings.redis_db,
            decode_responses=True,
            health_check_interval=30
        )

    def ping(self) -> bool:
        """Check Redis connection"""
        try:
            return self.client.ping()
        except redis.RedisError as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    def create_task(self, task_id: str, task_data: dict) -> bool:
        """Create task in Redis"""
        try:
            # Store task data as JSON string
            task_key = f"task:data:{task_id}"
            task_json = json.dumps(task_data)
            self.client.set(task_key, task_json, ex=604800)  # 7 days TTL

            # Set initial status
            self.set_task_status(task_id, {
                "task_id": task_id,
                "status": task_data.get("status", "queued"),
                "progress": 0,
                "created_at": task_data.get("created_at"),
                "type": task_data.get("type")
            })

            logger.info(f"Task {task_id} created in Redis")
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to create task: {e}")
            return False

    def add_to_queue(self, task_id: str, task_type: str) -> int:
        """Add task to queue and return position"""
        try:
            queue_key = f"queue:{task_type}"
            position = self.client.rpush(queue_key, task_id)
            logger.info(f"Task {task_id} added to {task_type} queue at position {position}")
            return position
        except redis.RedisError as e:
            logger.error(f"Failed to add to queue: {e}")
            return 0

    def pop_task(self, queue_name: str = "task:queue", timeout: int = 1) -> Optional[str]:
        """Pop task from queue (blocking)"""
        try:
            result = self.client.brpop(queue_name, timeout=timeout)
            if result:
                return result[1]  # Return task_id
            return None
        except redis.RedisError as e:
            logger.error(f"Failed to pop from queue: {e}")
            return None

    def get_task_data(self, task_id: str) -> Optional[dict]:
        """Get task data"""
        try:
            task_key = f"task:data:{task_id}"
            data_json = self.client.get(task_key)
            if data_json:
                return json.loads(data_json)
            return None
        except redis.RedisError as e:
            logger.error(f"Failed to get task data: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse task data JSON: {e}")
            return None

    def push_task(self, task_data: dict) -> bool:
        """Push task to queue"""
        try:
            task_json = json.dumps(task_data)
            self.client.lpush("task:queue", task_json)
            logger.info(f"Task {task_data['task_id']} pushed to queue")
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to push task: {e}")
            return False

    def get_queue_length(self) -> int:
        """Get current queue length"""
        try:
            return self.client.llen("task:queue")
        except redis.RedisError as e:
            logger.error(f"Failed to get queue length: {e}")
            return 0

    def set_task_status(self, task_id: str, status_data: dict, ttl: int = 604800) -> bool:
        """Set task status (default TTL 7 days)"""
        try:
            key = f"task:status:{task_id}"
            self.client.hset(key, mapping=status_data)
            self.client.expire(key, ttl)
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to set task status: {e}")
            return False

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get task status"""
        try:
            key = f"task:status:{task_id}"
            data = self.client.hgetall(key)
            return data if data else None
        except redis.RedisError as e:
            logger.error(f"Failed to get task status: {e}")
            return None

    def set_progress(self, task_id: str, progress_data: dict, ttl: int = 86400) -> bool:
        """Set task progress (default TTL 24 hours)"""
        try:
            key = f"task:progress:{task_id}"
            self.client.hset(key, mapping=progress_data)
            self.client.expire(key, ttl)
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to set progress: {e}")
            return False

    def get_progress(self, task_id: str) -> Optional[dict]:
        """Get task progress"""
        try:
            key = f"task:progress:{task_id}"
            data = self.client.hgetall(key)
            return data if data else None
        except redis.RedisError as e:
            logger.error(f"Failed to get progress: {e}")
            return None

    def set_ws_token(self, token: str, task_id: str, ttl: int = 300) -> bool:
        """Set WebSocket Token (default TTL 5 minutes)"""
        try:
            key = f"ws:token:{token}"
            self.client.setex(key, ttl, task_id)
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to set ws token: {e}")
            return False

    def get_ws_token_task_id(self, token: str) -> Optional[str]:
        """Validate WebSocket Token and get task_id"""
        try:
            key = f"ws:token:{token}"
            task_id = self.client.get(key)
            # Token is one-time use, delete after reading
            self.client.delete(key)
            return task_id
        except redis.RedisError as e:
            logger.error(f"Failed to get ws token: {e}")
            return None

    def publish_progress(self, task_id: str, message: dict) -> bool:
        """Publish progress message to Pub/Sub"""
        try:
            channel = f"task:progress:{task_id}"
            self.client.publish(channel, json.dumps(message))
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to publish progress: {e}")
            return False

    def close(self):
        """Close connection"""
        self.client.close()

# Global instance
redis_client = RedisClient()
