# api/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
import os

class Settings(BaseSettings):
    # API configuration
    api_keys: list[str] = Field(default_factory=list)
    api_port: int = 8000
    api_host: str = "0.0.0.0"
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    max_image_size_bytes: int = 10485760  # 10MB
    max_request_body_size: int = 15728640  # 15MB
    supported_formats: list[str] = Field(default_factory=lambda: ["png", "jpg", "jpeg", "webp"])

    # Queue configuration
    max_queue_length: int = 50

    # Redis configuration
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    redis_max_memory: str = "512mb"

    # ComfyUI configuration
    comfyui_host: str = "http://comfyui:8188"
    comfyui_timeout: int = 300

    # R2 configuration
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_url: str = ""

    # WebSocket configuration
    ws_token_ttl: int = 300  # 5 minutes
    ws_heartbeat_interval: int = 30
    ws_heartbeat_timeout: int = 60

    # Log configuration
    log_level: str = "INFO"
    log_format: str = "json"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables"""
        api_keys_str = os.getenv("API_KEYS", "")
        api_keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]

        allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
        allowed_origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]

        supported_formats_str = os.getenv("SUPPORTED_FORMATS", "png,jpg,jpeg,webp")
        supported_formats = [f.strip().lower() for f in supported_formats_str.split(",") if f.strip()]

        return cls(
            api_keys=api_keys,
            allowed_origins=allowed_origins,
            supported_formats=supported_formats,
            api_port=int(os.getenv("API_PORT", "8000")),
            max_image_size_bytes=int(os.getenv("MAX_IMAGE_SIZE_BYTES", "10485760")),
            max_queue_length=int(os.getenv("MAX_QUEUE_LENGTH", "50")),
            redis_host=os.getenv("REDIS_HOST", "redis"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            comfyui_host=os.getenv("COMFYUI_HOST", "http://comfyui:8188"),
            r2_account_id=os.getenv("R2_ACCOUNT_ID", ""),
            r2_access_key_id=os.getenv("R2_ACCESS_KEY_ID", ""),
            r2_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY", ""),
            r2_bucket_name=os.getenv("R2_BUCKET_NAME", ""),
            r2_public_url=os.getenv("R2_PUBLIC_URL", ""),
        )

# Global configuration instance
settings = Settings.from_env()
