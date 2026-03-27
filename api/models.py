# api/models.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime

class TaskRequest(BaseModel):
    """Unified task request model"""
    type: Literal["face-swap", "upscale", "remove-background"]
    images: dict
    params: Optional[dict] = None
    webhook_url: Optional[str] = None

    @field_validator('images')
    def validate_images(cls, v, info):
        task_type = info.data.get('type')

        if task_type == "face-swap":
            if "source" not in v or "target" not in v:
                raise ValueError("face-swap requires 'source' and 'target' images")
        elif task_type in ("upscale", "remove-background"):
            if "source" not in v:
                raise ValueError(f"{task_type} requires 'source' image")

        return v

    @field_validator('params')
    def validate_params(cls, v, info):
        task_type = info.data.get('type')

        if task_type == "upscale" and v:
            scale_factor = v.get('scale_factor', 2)
            if scale_factor not in [2, 4, 8]:
                raise ValueError("scale_factor must be 2, 4, or 8")

        return v

class TaskResponse(BaseModel):
    """Task creation response"""
    task_id: str
    status: Literal["queued"]
    websocket_url: str
    ws_token: str
    queue_position: int

class TaskStatusResponse(BaseModel):
    """Task status response"""
    task_id: str
    type: str
    status: Literal["queued", "processing", "completed", "failed", "cancelled"]
    progress: int
    result_url: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    processing_time: Optional[float] = None
    error: Optional[str] = None

class TasksListResponse(BaseModel):
    """Batch task query response"""
    tasks: list[TaskStatusResponse]
    total: int
    limit: int
    offset: int

class ProgressMessage(BaseModel):
    """Progress message"""
    type: Literal["progress", "completed", "error"]
    timestamp: str
    data: dict

class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    details: Optional[str] = None
    retry_after: Optional[int] = None

class HealthResponse(BaseModel):
    """Health check response"""
    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: str
    services: dict
    gpu: Optional[dict] = None
    queue: dict
    disk: Optional[dict] = None
