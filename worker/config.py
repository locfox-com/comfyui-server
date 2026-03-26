# worker/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
import os

class WorkerSettings(BaseSettings):
    # Redis configuration
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # ComfyUI configuration
    comfyui_host: str = "http://comfyui:8188"
    comfyui_timeout: int = 300

    # R2 configuration
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_url: str = ""

    # Worker configuration
    worker_concurrency: int = 1
    worker_poll_interval: int = 1
    gpu_temp_threshold: int = 85

    # Task timeout configuration
    task_timeout_face_swap: int = 60
    task_timeout_upscale: int = 120
    task_timeout_remove_bg: int = 30

    # Cleanup configuration
    cleanup_input_after_hours: int = 2
    cleanup_output_after_hours: int = 24
    cleanup_interval_minutes: int = 30

    # Log configuration
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables"""
        return cls(
            redis_host=os.getenv("REDIS_HOST", "redis"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            comfyui_host=os.getenv("COMFYUI_HOST", "http://comfyui:8188"),
            comfyui_timeout=int(os.getenv("COMFYUI_TIMEOUT", "300")),
            r2_account_id=os.getenv("R2_ACCOUNT_ID", ""),
            r2_access_key_id=os.getenv("R2_ACCESS_KEY_ID", ""),
            r2_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY", ""),
            r2_bucket_name=os.getenv("R2_BUCKET_NAME", ""),
            r2_public_url=os.getenv("R2_PUBLIC_URL", ""),
            worker_concurrency=int(os.getenv("WORKER_CONCURRENCY", "1")),
            worker_poll_interval=int(os.getenv("WORKER_POLL_INTERVAL", "1")),
            gpu_temp_threshold=int(os.getenv("GPU_TEMP_THRESHOLD", "85")),
            task_timeout_face_swap=int(os.getenv("TASK_TIMEOUT_FACE_SWAP", "60")),
            task_timeout_upscale=int(os.getenv("TASK_TIMEOUT_UPSCALE", "120")),
            task_timeout_remove_bg=int(os.getenv("TASK_TIMEOUT_REMOVE_BG", "30")),
            cleanup_input_after_hours=int(os.getenv("CLEANUP_INPUT_AFTER_HOURS", "2")),
            cleanup_output_after_hours=int(os.getenv("CLEANUP_OUTPUT_AFTER_HOURS", "24")),
            cleanup_interval_minutes=int(os.getenv("CLEANUP_INTERVAL_MINUTES", "30")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

# Global configuration instance
settings = WorkerSettings.from_env()
