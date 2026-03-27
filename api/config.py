# api/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    # API configuration
    API_KEYS: str = Field(default="")
    api_port: int = 8000
    api_host: str = "0.0.0.0"
    ALLOWED_ORIGINS: str = Field(default="http://localhost:3000")
    max_image_size_bytes: int = 10485760  # 10MB
    max_request_body_size: int = 15728640  # 15MB
    SUPPORTED_FORMATS: str = Field(default="png,jpg,jpeg,webp")

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

    # Debug mode
    debug: bool = False

    # Log configuration
    log_level: str = "INFO"
    log_format: str = "json"

    # Computed properties from string fields
    @property
    def api_keys(self) -> list[str]:
        return [k.strip() for k in self.API_KEYS.split(",") if k.strip()]

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def supported_formats(self) -> list[str]:
        return [f.strip().lower() for f in self.SUPPORTED_FORMATS.split(",") if f.strip()]

# Global configuration instance
settings = Settings()
