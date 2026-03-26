# api/routers/tasks.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
import logging
from datetime import datetime
import uuid

from models import TaskRequest, TaskResponse, TaskStatusResponse, TasksListResponse
from middleware.auth import verify_api_key
from utils.image import decode_base64_image, save_image_to_shared_volume
from utils.token import generate_ws_token, save_ws_token
from utils.redis import redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    request: TaskRequest,
    api_key: str = Depends(verify_api_key)
):
    """Create a new task"""
    task_id = str(uuid.uuid4())

    try:
        # Validate and decode images
        decoded_images = {}
        for image_key, image_data in request.images.items():
            try:
                image_bytes, image_format = decode_base64_image(image_data)
                filename = f"{image_key}.{image_format}"
                filepath = save_image_to_shared_volume(image_bytes, task_id, filename)
                decoded_images[image_key] = {
                    "filename": filename,
                    "format": image_format,
                    "path": filepath
                }
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid image data for {image_key}: {str(e)}"
                )

        # Generate WebSocket token
        ws_token = generate_ws_token()
        save_ws_token(ws_token, task_id)

        # Create task data
        task_data = {
            "task_id": task_id,
            "type": request.type,
            "status": "queued",
            "progress": 0,
            "images": decoded_images,
            "params": request.params or {},
            "webhook_url": request.webhook_url,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "completed_at": None,
            "processing_time": None,
            "error": None
        }

        # Save to Redis
        redis_client.create_task(task_id, task_data)

        # Add to queue
        queue_position = redis_client.add_to_queue(task_id, request.type)

        # Generate WebSocket URL
        websocket_url = f"ws://localhost:8000/ws/tasks/{task_id}?token={ws_token}"

        logger.info(f"Created task {task_id} of type {request.type}")

        return TaskResponse(
            task_id=task_id,
            status="queued",
            websocket_url=websocket_url,
            ws_token=ws_token,
            queue_position=queue_position
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )

@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get task status"""
    task_data = redis_client.get_task_data(task_id)

    if not task_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )

    # Get result URL if completed
    result_url = None
    if task_data.get('status') == 'completed':
        result_url = task_data.get('result_url')

    return TaskStatusResponse(
        task_id=task_id,
        type=task_data['type'],
        status=task_data['status'],
        progress=task_data.get('progress', 0),
        result_url=result_url,
        created_at=task_data['created_at'],
        completed_at=task_data.get('completed_at'),
        processing_time=task_data.get('processing_time'),
        error=task_data.get('error')
    )

@router.get("", response_model=TasksListResponse)
async def list_tasks(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, regex="^(queued|processing|completed|failed|cancelled)$"),
    api_key: str = Depends(verify_api_key)
):
    """List tasks with pagination"""
    task_ids = redis_client.get_all_task_ids()

    # Filter by status if provided
    if status_filter:
        filtered_tasks = []
        for task_id in task_ids:
            task_data = redis_client.get_task(task_id)
            if task_data and task_data.get('status') == status_filter:
                filtered_tasks.append(task_id)
        task_ids = filtered_tasks

    # Apply pagination
    total = len(task_ids)
    paginated_ids = task_ids[offset:offset + limit]

    tasks = []
    for task_id in paginated_ids:
        task_data = redis_client.get_task(task_id)
        if task_data:
            result_url = None
            if task_data.get('status') == 'completed':
                result_url = task_data.get('result_url')

            tasks.append(TaskStatusResponse(
                task_id=task_id,
                type=task_data['type'],
                status=task_data['status'],
                progress=task_data.get('progress', 0),
                result_url=result_url,
                created_at=task_data['created_at'],
                completed_at=task_data.get('completed_at'),
                processing_time=task_data.get('processing_time'),
                error=task_data.get('error')
            ))

    return TasksListResponse(
        tasks=tasks,
        total=total,
        limit=limit,
        offset=offset
    )

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_task(
    task_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Cancel a task"""
    task_data = redis_client.get_task(task_id)

    if not task_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )

    current_status = task_data.get('status')
    if current_status in ['completed', 'failed', 'cancelled']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel task with status: {current_status}"
        )

    # Update task status
    task_data['status'] = 'cancelled'
    redis_client.update_task(task_id, task_data)

    # Remove from queue if present
    redis_client.remove_from_queue(task_id)

    # Publish cancellation message
    redis_client.publish_progress(task_id, {
        "status": "cancelled",
        "progress": 0,
        "message": "Task cancelled by user"
    })

    logger.info(f"Cancelled task {task_id}")
    return None
