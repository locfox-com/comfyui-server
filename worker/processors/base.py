# worker/processors/base.py
import os
import logging
import json
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from utils.redis import redis_client
from utils.comfyui import comfyui_client
from utils.r2 import r2_client
from utils.gpu_monitor import gpu_monitor
from utils.cleanup import cleanup_task

logger = logging.getLogger(__name__)

class BaseProcessor(ABC):
    """Base class for task processors"""

    def __init__(self, task_type: str):
        """
        Initialize processor

        Args:
            task_type: Task type (face-swap, upscale, remove-background)
        """
        self.task_type = task_type

    @abstractmethod
    def load_workflow(self) -> Dict[str, Any]:
        """
        Load ComfyUI workflow template

        Returns:
            Workflow dictionary
        """
        pass

    @abstractmethod
    def prepare_workflow(self, workflow: Dict[str, Any], task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare workflow with task-specific parameters

        Args:
            workflow: Base workflow template
            task_data: Task data from queue

        Returns:
            Prepared workflow dictionary
        """
        pass

    @abstractmethod
    def get_timeout(self) -> int:
        """
        Get task-specific timeout in seconds

        Returns:
            Timeout in seconds
        """
        pass

    def process(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process task with full lifecycle

        Args:
            task_data: Task data from queue

        Returns:
            Result dictionary with status and output/error
        """
        task_id = task_data.get("task_id")
        logger.info(f"Processing {self.task_type} task {task_id}")

        result = {
            "task_id": task_id,
            "status": "failed",
            "error": None,
            "output_url": None
        }

        try:
            # Update status to processing
            self.update_status(task_id, "processing")

            # Check GPU temperature
            if gpu_monitor.is_too_hot():
                raise Exception("GPU temperature too high, refusing task")

            # Load and prepare workflow
            workflow = self.load_workflow()
            prepared_workflow = self.prepare_workflow(workflow, task_data)

            # Submit to ComfyUI
            self.update_progress(task_id, 0, "Submitting workflow to ComfyUI...")
            prompt_id = comfyui_client.submit_workflow(prepared_workflow)
            if not prompt_id:
                raise Exception("Failed to submit workflow to ComfyUI")

            # Wait for completion
            self.update_progress(task_id, 10, "Processing...")
            timeout = self.get_timeout()
            comfyui_client.timeout = timeout  # Set timeout for this task

            success = comfyui_client.wait_for_completion(prompt_id)
            if not success:
                raise Exception("ComfyUI workflow failed or timed out")

            # Get output images
            self.update_progress(task_id, 90, "Downloading results...")
            output_images = comfyui_client.get_output_images(prompt_id)
            if not output_images:
                raise Exception("No output images generated")

            # Download and upload first image
            image_info = output_images[0]
            image_data = comfyui_client.download_image(
                filename=image_info["filename"],
                subfolder=image_info.get("subfolder", ""),
                image_type=image_info.get("type", "output")
            )

            if not image_data:
                raise Exception("Failed to download output image")

            # Upload to R2
            self.update_progress(task_id, 95, "Uploading to R2...")
            output_url = r2_client.upload_result(
                task_id=task_id,
                task_type=self.task_type,
                image_data=image_data,
                filename=image_info["filename"]
            )

            if not output_url:
                raise Exception("Failed to upload to R2")

            # Success
            result["status"] = "completed"
            result["output_url"] = output_url
            self.update_progress(task_id, 100, "Completed")
            self.update_status(task_id, "completed", output_url=output_url)
            logger.info(f"Task {task_id} completed successfully")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Task {task_id} failed: {error_msg}")
            result["error"] = error_msg
            self.update_status(task_id, "failed", error=error_msg)

        finally:
            # Cleanup task files
            try:
                cleanup_task(task_id)
            except Exception as e:
                logger.warning(f"Cleanup failed for task {task_id}: {e}")

        return result

    def update_progress(self, task_id: str, progress: int, message: str) -> bool:
        """
        Update task progress in Redis and publish to Pub/Sub

        Args:
            task_id: Task ID
            progress: Progress percentage (0-100)
            message: Progress message

        Returns:
            True on success, False on failure
        """
        progress_data = {
            "progress": str(progress),
            "message": message
        }

        # Store in Redis
        redis_client.set_progress(task_id, progress_data)

        # Publish to Pub/Sub
        message_data = {
            "task_id": task_id,
            "progress": progress,
            "message": message,
            "timestamp": int(time.time())
        }
        redis_client.publish_progress(task_id, message_data)

        logger.debug(f"Task {task_id} progress: {progress}% - {message}")
        return True

    def update_status(self, task_id: str, status: str, output_url: str = None, error: str = None) -> bool:
        """
        Update task status in Redis

        Args:
            task_id: Task ID
            status: Task status (processing, completed, failed)
            output_url: Output URL (for completed tasks)
            error: Error message (for failed tasks)

        Returns:
            True on success, False on failure
        """
        status_data = {
            "status": status,
            "task_id": task_id
        }

        if output_url:
            status_data["output_url"] = output_url

        if error:
            status_data["error"] = error

        return redis_client.set_task_status(task_id, status_data)

    def cleanup(self, task_id: str) -> bool:
        """
        Cleanup task resources

        Args:
            task_id: Task ID

        Returns:
            True on success, False on failure
        """
        try:
            return cleanup_task(task_id)
        except Exception as e:
            logger.error(f"Cleanup failed for task {task_id}: {e}")
            return False
