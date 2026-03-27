# api/routers/health.py
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
import logging
import psutil
from datetime import datetime

from models import HealthResponse
from middleware.auth import verify_api_key
from utils.redis import redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

def get_disk_usage(path: str = "/data") -> dict:
    """Get disk usage statistics"""
    try:
        usage = psutil.disk_usage(path)
        return {
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent": usage.percent
        }
    except Exception as e:
        logger.error(f"Error getting disk usage: {e}")
        return None

def get_queue_stats() -> dict:
    """Get queue statistics from Redis"""
    try:
        return {
            "pending_tasks": redis_client.get_queue_length(),
            "processing_tasks": redis_client.get_processing_count()
        }
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        return {
            "pending_tasks": 0,
            "processing_tasks": 0
        }

def check_services_health() -> dict:
    """Check health of all services"""
    services = {}

    # Check Redis
    try:
        redis_client.client.ping()
        services["redis"] = "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        services["redis"] = "unhealthy"

    # Check shared volume
    try:
        import os
        if os.path.exists("/data"):
            services["shared_volume"] = "healthy"
        else:
            services["shared_volume"] = "unhealthy"
    except Exception as e:
        logger.error(f"Shared volume check failed: {e}")
        services["shared_volume"] = "unhealthy"

    return services

def determine_overall_status(services: dict) -> str:
    """Determine overall health status"""
    unhealthy_count = sum(1 for s in services.values() if s == "unhealthy")

    if unhealthy_count == 0:
        return "healthy"
    elif unhealthy_count == 1:
        return "degraded"
    else:
        return "unhealthy"

@router.get("", response_model=HealthResponse)
async def health_check(
    api_key: Optional[str] = Depends(verify_api_key)
):
    """Health check endpoint"""
    services_health = check_services_health()
    overall_status = determine_overall_status(services_health)

    # Get queue statistics
    queue_stats = get_queue_stats()

    # Get disk usage
    disk_usage = get_disk_usage()

    # Get GPU info (if available)
    gpu_info = None
    try:
        # Check if NVIDIA GPU is available
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.used,memory.total,utilization.gpu', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            gpu_info = {"gpus": []}
            for i, line in enumerate(lines):
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 4:
                    gpu_info["gpus"].append({
                        "id": i,
                        "name": parts[0],
                        "memory_used_mb": int(parts[1]),
                        "memory_total_mb": int(parts[2]),
                        "utilization_percent": int(parts[3])
                    })
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        logger.debug(f"GPU info not available: {e}")
        gpu_info = None

    response = HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat() + "Z",
        services=services_health,
        gpu=gpu_info,
        queue=queue_stats,
        disk=disk_usage
    )

    return response

@router.get("/live")
async def liveness_probe():
    """Liveness probe - simple check if service is running"""
    return {"status": "alive"}

@router.get("/ready")
async def readiness_probe():
    """Readiness probe - check if service is ready to accept traffic"""
    try:
        # Check if Redis is accessible
        redis_client.client.ping()

        # Check if shared volume is accessible
        import os
        if not os.path.exists("/data"):
            raise Exception("Shared volume not accessible")

        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Service not ready"
        )
