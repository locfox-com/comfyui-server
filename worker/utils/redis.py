# worker/utils/redis.py
import redis
import json
import logging
from typing import Optional, Dict
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

    def pop_task(self, queue_name: str = "task:queue", timeout: int = 1) -> Optional[Dict]:
        """
        Pop task from queue (blocking)

        Args:
            queue_name: Queue name (default: task:queue)
            timeout: Blocking timeout in seconds (default: 1)

        Returns:
            Task data dictionary, None if no task
        """
        try:
            result = self.client.brpop(queue_name, timeout=timeout)
            if result:
                _, task_json = result
                task_data = json.loads(task_json)
                logger.info(f"Popped task {task_data.get('task_id')} from queue")
                return task_data
            return None
        except redis.RedisError as e:
            logger.error(f"Failed to pop task from queue: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode task JSON: {e}")
            return None

    def pop_from_queue(self, queue_name: str, timeout: int = 1) -> Optional[str]:
        """
        Pop task ID from queue (blocking)

        Args:
            queue_name: Queue name
            timeout: Blocking timeout in seconds

        Returns:
            Task ID string, None if no task
        """
        try:
            result = self.client.brpop(queue_name, timeout=timeout)
            if result:
                _, task_id = result
                return task_id
            return None
        except redis.RedisError as e:
            logger.error(f"Failed to pop from queue {queue_name}: {e}")
            return None

    def get_task_data(self, task_id: str) -> Optional[Dict]:
        """
        Get task data by ID

        Args:
            task_id: Task ID

        Returns:
            Task data dictionary, None if not found
        """
        try:
            task_key = f"task:data:{task_id}"
            task_json = self.client.get(task_key)
            if task_json:
                return json.loads(task_json)
            return None
        except redis.RedisError as e:
            logger.error(f"Failed to get task data: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode task data JSON: {e}")
            return None

    def set_task_status(self, task_id: str, status_data: Dict, ttl: int = 604800) -> bool:
        """
        Set task status (default TTL 7 days)

        Args:
            task_id: Task ID
            status_data: Status data dictionary
            ttl: Time to live in seconds (default: 7 days)

        Returns:
            True on success, False on failure
        """
        try:
            key = f"task:status:{task_id}"
            self.client.hset(key, mapping=status_data)
            self.client.expire(key, ttl)
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to set task status: {e}")
            return False

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        Get task status

        Args:
            task_id: Task ID

        Returns:
            Task status dictionary, None if not found
        """
        try:
            key = f"task:status:{task_id}"
            data = self.client.hgetall(key)
            return data if data else None
        except redis.RedisError as e:
            logger.error(f"Failed to get task status: {e}")
            return None

    def set_progress(self, task_id: str, progress_data: Dict, ttl: int = 86400) -> bool:
        """
        Set task progress (default TTL 24 hours)

        Args:
            task_id: Task ID
            progress_data: Progress data dictionary
            ttl: Time to live in seconds (default: 24 hours)

        Returns:
            True on success, False on failure
        """
        try:
            key = f"task:progress:{task_id}"
            self.client.hset(key, mapping=progress_data)
            self.client.expire(key, ttl)
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to set progress: {e}")
            return False

    def get_progress(self, task_id: str) -> Optional[Dict]:
        """
        Get task progress

        Args:
            task_id: Task ID

        Returns:
            Progress data dictionary, None if not found
        """
        try:
            key = f"task:progress:{task_id}"
            data = self.client.hgetall(key)
            return data if data else None
        except redis.RedisError as e:
            logger.error(f"Failed to get progress: {e}")
            return None

    def publish_progress(self, task_id: str, message: Dict) -> bool:
        """
        Publish progress message to Pub/Sub

        Args:
            task_id: Task ID
            message: Progress message dictionary

        Returns:
            True on success, False on failure
        """
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
