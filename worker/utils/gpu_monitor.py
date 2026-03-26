# worker/utils/gpu_monitor.py
import logging
import subprocess
import re
from typing import Optional, Dict, Tuple
from config import settings

logger = logging.getLogger(__name__)

class GPUMonitor:
    def __init__(self):
        self.temp_threshold = settings.gpu_temp_threshold
        self.nvidia_smi_path = "nvidia-smi"

    def _run_nvidia_smi(self, args: list) -> Optional[str]:
        """
        Run nvidia-smi command

        Args:
            args: Command arguments

        Returns:
            Command output, None on failure
        """
        try:
            cmd = [self.nvidia_smi_path] + args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"nvidia-smi command failed: {e.stderr}")
            return None
        except FileNotFoundError:
            logger.error("nvidia-smi not found - GPU monitoring unavailable")
            return None
        except Exception as e:
            logger.error(f"Failed to run nvidia-smi: {e}")
            return None

    def get_temperature(self, gpu_id: int = 0) -> Optional[int]:
        """
        Get GPU temperature

        Args:
            gpu_id: GPU ID (default: 0)

        Returns:
            Temperature in Celsius, None on failure
        """
        output = self._run_nvidia_smi([
            "--query-gpu=temperature.gpu",
            "--format=csv,noheader,nounits",
            f"--id={gpu_id}"
        ])

        if output:
            try:
                temp = int(output)
                logger.debug(f"GPU {gpu_id} temperature: {temp}°C")
                return temp
            except ValueError:
                logger.error(f"Failed to parse temperature: {output}")
                return None
        return None

    def get_memory_info(self, gpu_id: int = 0) -> Optional[Dict[str, int]]:
        """
        Get GPU memory information

        Args:
            gpu_id: GPU ID (default: 0)

        Returns:
            Dictionary with total, used, free memory in MB, None on failure
        """
        output = self._run_nvidia_smi([
            "--query-gpu=memory.total,memory.used,memory.free",
            "--format=csv,noheader,nounits",
            f"--id={gpu_id}"
        ])

        if output:
            try:
                parts = output.split(",")
                if len(parts) == 3:
                    memory_info = {
                        "total": int(parts[0].strip()),
                        "used": int(parts[1].strip()),
                        "free": int(parts[2].strip())
                    }
                    logger.debug(f"GPU {gpu_id} memory: {memory_info}")
                    return memory_info
            except (ValueError, IndexError) as e:
                logger.error(f"Failed to parse memory info: {output} - {e}")
                return None
        return None

    def get_utilization(self, gpu_id: int = 0) -> Optional[Dict[str, int]]:
        """
        Get GPU utilization

        Args:
            gpu_id: GPU ID (default: 0)

        Returns:
            Dictionary with gpu and memory utilization percentages, None on failure
        """
        output = self._run_nvidia_smi([
            "--query-gpu=utilization.gpu,utilization.memory",
            "--format=csv,noheader,nounits",
            f"--id={gpu_id}"
        ])

        if output:
            try:
                parts = output.split(",")
                if len(parts) == 2:
                    utilization = {
                        "gpu": int(parts[0].strip()),
                        "memory": int(parts[1].strip())
                    }
                    logger.debug(f"GPU {gpu_id} utilization: {utilization}")
                    return utilization
            except (ValueError, IndexError) as e:
                logger.error(f"Failed to parse utilization: {output} - {e}")
                return None
        return None

    def is_too_hot(self, gpu_id: int = 0) -> bool:
        """
        Check if GPU temperature exceeds threshold

        Args:
            gpu_id: GPU ID (default: 0)

        Returns:
            True if temperature exceeds threshold, False otherwise
        """
        temp = self.get_temperature(gpu_id)
        if temp is None:
            # If we can't read temperature, assume it's OK
            logger.warning("Could not read GPU temperature, assuming OK")
            return False

        is_hot = temp >= self.temp_threshold
        if is_hot:
            logger.warning(f"GPU {gpu_id} temperature {temp}°C exceeds threshold {self.temp_threshold}°C")
        return is_hot

    def get_all_info(self, gpu_id: int = 0) -> Dict[str, any]:
        """
        Get all GPU information

        Args:
            gpu_id: GPU ID (default: 0)

        Returns:
            Dictionary with temperature, memory, and utilization info
        """
        return {
            "temperature": self.get_temperature(gpu_id),
            "memory": self.get_memory_info(gpu_id),
            "utilization": self.get_utilization(gpu_id),
            "is_too_hot": self.is_too_hot(gpu_id)
        }

# Global instance
gpu_monitor = GPUMonitor()
