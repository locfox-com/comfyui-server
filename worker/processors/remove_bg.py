# worker/processors/remove_bg.py
import logging
import json
import os
from typing import Dict, Any
from base import BaseProcessor
from config import settings

logger = logging.getLogger(__name__)

class RemoveBackgroundProcessor(BaseProcessor):
    """Processor for remove-background tasks"""

    def __init__(self):
        super().__init__("remove-background")

    def load_workflow(self) -> Dict[str, Any]:
        """
        Load remove-background workflow template

        Returns:
            Workflow dictionary
        """
        workflow_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "workflows",
            "remove_background.json"
        )

        try:
            with open(workflow_path, 'r') as f:
                workflow = json.load(f)
            logger.debug("Loaded remove-background workflow template")
            return workflow
        except FileNotFoundError:
            logger.error(f"Remove-background workflow not found: {workflow_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid remove-background workflow JSON: {e}")
            raise

    def prepare_workflow(self, workflow: Dict[str, Any], task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare remove-background workflow with input image

        Args:
            workflow: Base workflow template
            task_data: Task data containing input_image

        Returns:
            Prepared workflow with image path
        """
        # Extract image path from task data
        input_image = task_data.get("input_image")

        if not input_image:
            raise ValueError("input_image is required")

        # Find LoadImage node and set its path
        # Assuming the workflow has a LoadImage node with ID 3
        # You may need to adjust the node ID based on your actual workflow

        if "3" in workflow:
            workflow["3"]["inputs"]["image"] = input_image
        else:
            logger.warning("Node 3 (input image) not found in workflow")

        logger.info(f"Prepared remove-background workflow: input={input_image}")
        return workflow

    def get_timeout(self) -> int:
        """
        Get remove-background task timeout

        Returns:
            Timeout in seconds
        """
        return settings.task_timeout_remove_bg
