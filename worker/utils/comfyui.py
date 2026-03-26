# worker/utils/comfyui.py
import requests
import logging
import time
from typing import Dict, List, Optional, Any
from config import settings

logger = logging.getLogger(__name__)

class ComfyUIClient:
    def __init__(self):
        self.base_url = settings.comfyui_host
        self.timeout = settings.comfyui_timeout

    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """
        Make HTTP request to ComfyUI API

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments for requests

        Returns:
            Response object, None on failure
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.request(method, url, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"ComfyUI request failed: {method} {url} - {e}")
            return None

    def submit_workflow(self, workflow: Dict) -> Optional[str]:
        """
        Submit workflow to ComfyUI

        Args:
            workflow: Workflow dictionary (prompt)

        Returns:
            Prompt ID (task ID), None on failure
        """
        try:
            response = self._request("POST", "/prompt", json={"prompt": workflow})
            if response:
                data = response.json()
                prompt_id = data.get("prompt_id")
                if prompt_id:
                    logger.info(f"Submitted workflow to ComfyUI: {prompt_id}")
                    return prompt_id
                else:
                    logger.error("No prompt_id in ComfyUI response")
            return None
        except Exception as e:
            logger.error(f"Failed to submit workflow: {e}")
            return None

    def get_history(self, prompt_id: str) -> Optional[Dict]:
        """
        Get workflow execution history

        Args:
            prompt_id: Prompt ID from submit_workflow

        Returns:
            History dictionary, None on failure
        """
        try:
            response = self._request("GET", f"/history/{prompt_id}")
            if response:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return None

    def wait_for_completion(self, prompt_id: str, check_interval: float = 0.5) -> bool:
        """
        Wait for workflow completion

        Args:
            prompt_id: Prompt ID from submit_workflow
            check_interval: Check interval in seconds (default: 0.5)

        Returns:
            True on success, False on failure or timeout
        """
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            history = self.get_history(prompt_id)
            if history and prompt_id in history:
                status = history[prompt_id].get("status", {})
                if status.get("completed", False):
                    logger.info(f"Workflow {prompt_id} completed successfully")
                    return True
                elif status.get("error", None):
                    error_msg = status.get("error", "Unknown error")
                    logger.error(f"Workflow {prompt_id} failed: {error_msg}")
                    return False

            time.sleep(check_interval)

        logger.error(f"Workflow {prompt_id} timed out after {self.timeout}s")
        return False

    def get_output_images(self, prompt_id: str) -> List[Dict[str, Any]]:
        """
        Get output images from completed workflow

        Args:
            prompt_id: Prompt ID from submit_workflow

        Returns:
            List of output image dictionaries with filename, subfolder, type
        """
        try:
            history = self.get_history(prompt_id)
            if not history or prompt_id not in history:
                logger.error(f"No history found for prompt {prompt_id}")
                return []

            outputs = history[prompt_id].get("outputs", {})
            images = []

            for node_id, node_output in outputs.items():
                if "images" in node_output:
                    for img in node_output["images"]:
                        images.append({
                            "filename": img.get("filename"),
                            "subfolder": img.get("subfolder", ""),
                            "type": img.get("type", "output")
                        })

            logger.info(f"Found {len(images)} output images for prompt {prompt_id}")
            return images

        except Exception as e:
            logger.error(f"Failed to get output images: {e}")
            return []

    def download_image(self, filename: str, subfolder: str = "", image_type: str = "output") -> Optional[bytes]:
        """
        Download image from ComfyUI

        Args:
            filename: Image filename
            subfolder: Subfolder path (default: "")
            image_type: Image type (default: "output")

        Returns:
            Image binary data, None on failure
        """
        try:
            params = {
                "filename": filename,
                "subfolder": subfolder,
                "type": image_type
            }
            response = self._request("GET", "/view", params=params)
            if response:
                logger.info(f"Downloaded image: {filename}")
                return response.content
            return None
        except Exception as e:
            logger.error(f"Failed to download image {filename}: {e}")
            return None

    def test_connection(self) -> bool:
        """
        Test ComfyUI connection

        Returns:
            True on success, False on failure
        """
        try:
            response = self._request("GET", "/system_stats")
            if response:
                logger.info("ComfyUI connection test successful")
                return True
            return False
        except Exception as e:
            logger.error(f"ComfyUI connection test failed: {e}")
            return False

# Global instance
comfyui_client = ComfyUIClient()
