# api/main.py
from fastapi import FastAPI, WebSocket, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from contextlib import asynccontextmanager
from config import settings

from routers import tasks, health
from websocket.handler import websocket_endpoint

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    # Startup
    logger.info("Starting API service...")
    # logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    # Test Redis connection
    from utils.redis import redis_client
    try:
        redis_client.client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down API service...")

# Create FastAPI app
app = FastAPI(
    title="ComfyUI Task API",
    description="API for submitting and managing image processing tasks",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")

# WebSocket endpoint
@app.websocket("/ws/tasks/{task_id}")
async def tasks_websocket(
    websocket: WebSocket,
    task_id: str,
    token: str = Query(...),
    api_key: str = Query(None)
):
    """WebSocket endpoint for task progress updates"""
    await websocket_endpoint(websocket, task_id, token, api_key)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "ComfyUI Task API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "tasks": "/api/v1/tasks",
            "health": "/api/v1/health",
            "websocket": "/ws/tasks/{task_id}"
        }
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "details": str(exc) if settings.debug else "An unexpected error occurred"
        }
    )

# Startup event logging
@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    logger.info("=" * 50)
    logger.info("ComfyUI Task API Started")
    # logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug: {settings.debug}")
    logger.info(f"Max Image Size: {settings.max_image_size_bytes} bytes")
    logger.info(f"Supported Formats: {settings.supported_formats}")
    logger.info(f"CORS Origins: {settings.allowed_origins}")
    logger.info("=" * 50)

# Shutdown event logging
@app.on_event("shutdown")
async def shutdown_event():
    """Log shutdown information"""
    logger.info("ComfyUI Task API Shutting Down...")
    logger.info("=" * 50)
