# worker/utils/cleanup.py
import os
import shutil
import logging
import time
from typing import List
from pathlib import Path
from config import settings

logger = logging.getLogger(__name__)

# Directories for task storage
INPUT_DIR = "/tmp/comfyui/input"
OUTPUT_DIR = "/tmp/comfyui/output"

def cleanup_directory(directory: str, max_age_hours: int) -> int:
    """
    Cleanup files in directory older than max_age_hours

    Args:
        directory: Directory path to cleanup
        max_age_hours: Maximum age in hours

    Returns:
        Number of files cleaned up
    """
    if not os.path.exists(directory):
        logger.debug(f"Directory does not exist: {directory}")
        return 0

    max_age_seconds = max_age_hours * 3600
    current_time = time.time()
    cleaned_count = 0

    try:
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)

            # Check if item is a file or directory
            if os.path.isfile(item_path):
                item_age = current_time - os.path.getmtime(item_path)
                if item_age > max_age_seconds:
                    try:
                        os.remove(item_path)
                        logger.info(f"Removed old file: {item_path}")
                        cleaned_count += 1
                    except Exception as e:
                        logger.error(f"Failed to remove file {item_path}: {e}")

            elif os.path.isdir(item_path):
                item_age = current_time - os.path.getmtime(item_path)
                if item_age > max_age_seconds:
                    try:
                        shutil.rmtree(item_path)
                        logger.info(f"Removed old directory: {item_path}")
                        cleaned_count += 1
                    except Exception as e:
                        logger.error(f"Failed to remove directory {item_path}: {e}")

        logger.info(f"Cleaned up {cleaned_count} items from {directory} (max age: {max_age_hours}h)")
        return cleaned_count

    except Exception as e:
        logger.error(f"Failed to cleanup directory {directory}: {e}")
        return 0

def cleanup_task(task_id: str) -> bool:
    """
    Cleanup files for a specific task

    Args:
        task_id: Task ID

    Returns:
        True on success, False on failure
    """
    cleaned = False

    # Cleanup input files
    input_path = os.path.join(INPUT_DIR, task_id)
    if os.path.exists(input_path):
        try:
            if os.path.isfile(input_path):
                os.remove(input_path)
            elif os.path.isdir(input_path):
                shutil.rmtree(input_path)
            logger.debug(f"Cleaned up input files for task {task_id}")
            cleaned = True
        except Exception as e:
            logger.error(f"Failed to cleanup input for task {task_id}: {e}")

    # Cleanup output files
    output_path = os.path.join(OUTPUT_DIR, task_id)
    if os.path.exists(output_path):
        try:
            if os.path.isfile(output_path):
                os.remove(output_path)
            elif os.path.isdir(output_path):
                shutil.rmtree(output_path)
            logger.debug(f"Cleaned up output files for task {task_id}")
            cleaned = True
        except Exception as e:
            logger.error(f"Failed to cleanup output for task {task_id}: {e}")

    return cleaned

def get_disk_free_gb(path: str = "/tmp") -> float:
    """
    Get free disk space in GB

    Args:
        path: Path to check (default: /tmp)

    Returns:
        Free space in GB
    """
    try:
        stat = shutil.disk_usage(path)
        free_gb = stat.free / (1024 ** 3)
        return free_gb
    except Exception as e:
        logger.error(f"Failed to get disk free space: {e}")
        return 0.0

def emergency_cleanup(threshold_gb: float = 5.0) -> int:
    """
    Perform emergency cleanup if disk space is below threshold

    Args:
        threshold_gb: Threshold in GB (default: 5.0)

    Returns:
        Number of files cleaned up
    """
    free_gb = get_disk_free_gb()

    if free_gb >= threshold_gb:
        logger.debug(f"Disk space OK: {free_gb:.2f}GB >= {threshold_gb}GB")
        return 0

    logger.warning(f"Low disk space: {free_gb:.2f}GB < {threshold_gb}GB, performing emergency cleanup")

    total_cleaned = 0

    # Cleanup output files first (shorter retention)
    total_cleaned += cleanup_directory(OUTPUT_DIR, max_age_hours=1)

    # Cleanup input files if still needed
    if get_disk_free_gb() < threshold_gb:
        total_cleaned += cleanup_directory(INPUT_DIR, max_age_hours=1)

    logger.info(f"Emergency cleanup completed: {total_cleaned} items removed, {get_disk_free_gb():.2f}GB free")
    return total_cleaned

def ensure_directories():
    """
    Ensure required directories exist
    """
    directories = [INPUT_DIR, OUTPUT_DIR]
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create directory {directory}: {e}")
