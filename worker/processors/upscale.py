# worker/processors/upscale.py
import logging
import json
import os
from typing import Dict, Any
from processors.base import BaseProcessor
from config import settings

logger = logging.getLogger(__name__)

class UpscaleProcessor(BaseProcessor):
    """Processor for image upscaling tasks"""

    def __init__(self):
        super().__init__("upscale")

    def load_workflow(self) -> Dict[str, Any]:
        """
        Load upscale workflow template

        Returns:
            Workflow dictionary
        """
        workflow_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "workflows",
            "upscale.json"
        )

        try:
            with open(workflow_path, 'r') as f:
                workflow = json.load(f)
            logger.debug("Loaded upscale workflow template")
            return workflow
        except FileNotFoundError:
            logger.error(f"Upscale workflow not found: {workflow_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid upscale workflow JSON: {e}")
            raise

    def prepare_workflow(self, workflow: Dict[str, Any], task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare upscale workflow with input image

        Args:
            workflow: Base workflow template
            task_data: Task data containing images.source.path

        Returns:
            Prepared workflow with image path
        """
        # Extract image path from task data
        # API provides images as: {"source": {"path": "...", "filename": "...", "format": "..."}}
        images = task_data.get("images", {})
        source_image = images.get("source", {})

        input_image = source_image.get("path")

        if not input_image:
            raise ValueError("input_image path is required")

        # Find LoadImage node and set its path
        # Assuming the workflow has a LoadImage node with ID 3
        # You may need to adjust the node ID based on your actual workflow

        if "3" in workflow:
            workflow["3"]["inputs"]["image"] = input_image
        else:
            logger.warning("Node 3 (input image) not found in workflow")

        logger.info(f"Prepared upscale workflow: input={input_image}")
        return workflow

    def get_timeout(self) -> int:
        """
        Get upscale task timeout

        Returns:
            Timeout in seconds
        """
        return settings.task_timeout_upscale
