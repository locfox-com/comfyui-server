# worker/processors/face_swap.py
import logging
import json
import os
from typing import Dict, Any
from processors.base import BaseProcessor
from config import settings

logger = logging.getLogger(__name__)

class FaceSwapProcessor(BaseProcessor):
    """Processor for face-swap tasks"""

    def __init__(self):
        super().__init__("face-swap")

    def load_workflow(self) -> Dict[str, Any]:
        """
        Load face-swap workflow template

        Returns:
            Workflow dictionary
        """
        workflow_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "workflows",
            "face_swap.json"
        )

        try:
            with open(workflow_path, 'r') as f:
                workflow = json.load(f)
            logger.debug("Loaded face-swap workflow template")
            return workflow
        except FileNotFoundError:
            logger.error(f"Face-swap workflow not found: {workflow_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid face-swap workflow JSON: {e}")
            raise

    def prepare_workflow(self, workflow: Dict[str, Any], task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare face-swap workflow with source and target images

        Args:
            workflow: Base workflow template
            task_data: Task data containing source_image and target_image

        Returns:
            Prepared workflow with image paths
        """
        # Extract image paths from task data
        source_image = task_data.get("source_image")
        target_image = task_data.get("target_image")

        if not source_image or not target_image:
            raise ValueError("Both source_image and target_image are required")

        # Find LoadImage nodes and set their paths
        # Assuming the workflow has two LoadImage nodes with specific IDs
        # You may need to adjust the node IDs based on your actual workflow

        # Common ComfyUI workflow structure:
        # Node 3: LoadImage (source face)
        # Node 4: LoadImage (target image)

        # Update source image node
        if "3" in workflow:
            workflow["3"]["inputs"]["image"] = source_image
        else:
            logger.warning("Node 3 (source image) not found in workflow")

        # Update target image node
        if "4" in workflow:
            workflow["4"]["inputs"]["image"] = target_image
        else:
            logger.warning("Node 4 (target image) not found in workflow")

        logger.info(f"Prepared face-swap workflow: source={source_image}, target={target_image}")
        return workflow

    def get_timeout(self) -> int:
        """
        Get face-swap task timeout

        Returns:
            Timeout in seconds
        """
        return settings.task_timeout_face_swap
