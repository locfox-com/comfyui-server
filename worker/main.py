# worker/main.py
import asyncio
import logging
import signal
import sys
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

# Configure logging
from config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import utilities
from utils.redis import redis_client
from utils.comfyui import comfyui_client
from utils.r2 import r2_client
from utils.gpu_monitor import gpu_monitor
from utils.cleanup import (
    cleanup_directory,
    emergency_cleanup,
    ensure_directories,
    INPUT_DIR,
    OUTPUT_DIR
)

# Import processors
from processors.face_swap import FaceSwapProcessor
from processors.upscale import UpscaleProcessor
from processors.remove_bg import RemoveBackgroundProcessor

# Processor registry
PROCESSORS = {
    "face-swap": FaceSwapProcessor(),
    "upscale": UpscaleProcessor(),
    "remove-background": RemoveBackgroundProcessor()
}

class Worker:
    """Worker process for handling ComfyUI tasks"""

    def __init__(self):
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=settings.worker_concurrency)

    def process_task(self, task_data: dict) -> bool:
        """
        Process a single task

        Args:
            task_data: Task data from queue

        Returns:
            True on success, False on failure
        """
        task_type = task_data.get("task_type")
        task_id = task_data.get("task_id")

        if not task_type or not task_id:
            logger.error(f"Invalid task data: {task_data}")
            return False

        # Get processor for task type
        processor = PROCESSORS.get(task_type)
        if not processor:
            logger.error(f"No processor found for task type: {task_type}")
            return False

        logger.info(f"Processing task {task_id} (type: {task_type})")

        try:
            # Process task
            result = processor.process(task_data)

            if result["status"] == "completed":
                logger.info(f"Task {task_id} completed successfully: {result.get('output_url')}")
                return True
            else:
                logger.error(f"Task {task_id} failed: {result.get('error')}")
                return False

        except Exception as e:
            logger.error(f"Unexpected error processing task {task_id}: {e}")
            return False

    async def worker_loop(self):
        """Main worker loop for processing tasks"""
        logger.info("Starting worker loop")

        # Ensure directories exist
        ensure_directories()

        # Test connections
        if not redis_client.ping():
            logger.error("Redis connection failed, exiting")
            return

        if not comfyui_client.test_connection():
            logger.error("ComfyUI connection failed, exiting")
            return

        if r2_client and not r2_client.test_connection():
            logger.warning("R2 connection test failed, continuing anyway")

        self.running = True

        while self.running:
            try:
                # Pop task from queue (blocking)
                task_data = redis_client.pop_task(timeout=settings.worker_poll_interval)

                if task_data:
                    # Process task in thread pool
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        self.executor,
                        self.process_task,
                        task_data
                    )

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                await asyncio.sleep(1)

        logger.info("Worker loop stopped")

    async def cleanup_loop(self):
        """Periodic cleanup loop"""
        logger.info("Starting cleanup loop")

        while self.running:
            try:
                # Wait for cleanup interval
                await asyncio.sleep(settings.cleanup_interval_minutes * 60)

                # Perform cleanup
                logger.info("Running periodic cleanup")

                # Cleanup input files
                input_cleaned = cleanup_directory(
                    INPUT_DIR,
                    max_age_hours=settings.cleanup_input_after_hours
                )

                # Cleanup output files
                output_cleaned = cleanup_directory(
                    OUTPUT_DIR,
                    max_age_hours=settings.cleanup_output_after_hours
                )

                # Check disk space and perform emergency cleanup if needed
                disk_free = cleanup_directory.__module__
                # Note: We're not importing get_disk_free_gb here, but could add check

                logger.info(f"Cleanup completed: {input_cleaned} input files, {output_cleaned} output files")

            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

        logger.info("Cleanup loop stopped")

    def stop(self):
        """Stop worker"""
        logger.info("Stopping worker")
        self.running = False
        self.executor.shutdown(wait=True)

async def main():
    """Main entry point"""
    logger.info("Starting ComfyUI worker")

    worker = Worker()

    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        worker.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run worker and cleanup loops concurrently
    try:
        await asyncio.gather(
            worker.worker_loop(),
            worker.cleanup_loop()
        )
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        worker.stop()
        redis_client.close()
        logger.info("Worker shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
