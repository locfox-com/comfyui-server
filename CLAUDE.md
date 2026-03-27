# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ComfyUI AI Image Server is a microservices-based image processing system that provides three AI operations: face swap, image upscaling, and background removal. The system uses ComfyUI as the AI inference engine, Redis for job queuing, FastAPI for the REST API, and Cloudflare R2 for storage.

**Architecture:**
- 5 Docker services: Nginx (reverse proxy) → API (FastAPI) → Redis (queues) ↔ Workers (processors) ↔ ComfyUI (AI engine) → R2 (storage)
- Workers poll Redis queues (`queue:upscale`, `queue:face-swap`, `queue:remove-background`) and execute ComfyUI workflows
- Template-based workflow system with JSON files in `worker/workflows/`
- WebSocket support for real-time progress updates via Redis Pub/Sub

## Development Commands

### Building and Starting Services

```bash
# Build all services (or individually: api, worker, comfyui)
docker compose build

# Start all services
docker compose up -d

# Scale workers horizontally
docker compose up -d --scale worker=3

# Check service status
docker compose ps

# View logs
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f comfyui

# Restart specific services
docker compose restart api worker

# Stop all services
docker compose down
```

### Debugging and Testing

```bash
# Health check
curl http://localhost/health

# Check Redis data
docker compose exec redis redis-cli GET "task:data:<task_id>"
docker compose exec redis redis-cli LLEN queue:upscale

# Monitor progress updates
docker compose exec redis redis-cli SUBSCRIBE task:progress:<task_id>

# Check GPU access
docker compose exec comfyui nvidia-smi

# Verify models
docker compose exec comfyui ls -lh /app/ComfyUI/models/

# Test API locally (requires services running)
cd api && pip install -r requirements.txt && uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

### Model Management

```bash
# Download AI models (~500MB) - run this after first deployment
docker compose exec comfyui bash /app/download_models.sh
```

## Architecture Details

### Task Processing Flow

1. **API receives request** → Validates base64 images, saves to shared volume (`/data/input/{task_id}/`)
2. **API creates task** → Stores in Redis (`task:data:{id}`), adds to queue (`queue:{type}`)
3. **Worker polls queue** → Pops task ID, retrieves full task data
4. **Worker loads workflow** → Reads JSON template from `worker/workflows/`, replaces `{{OUTPUT_PREFIX}}`, sets input paths
5. **Worker submits to ComfyUI** → POST to `/prompt` endpoint
6. **Worker polls for completion** → GET `/history/{prompt_id}` until done or timeout
7. **Worker downloads output** → GET `/view?filename={name}` from ComfyUI
8. **Worker uploads to R2** → PUT to R2 bucket, returns public URL
9. **Worker updates status** → Redis `task:status:{id}`, publishes progress via Pub/Sub
10. **Cleanup** → Removes input files from shared volume

### Configuration System

**Dual config pattern:**
- **API** (`api/config.py`): Uses pydantic-settings v2 with `BaseSettings` and `@property` computed fields
  - List fields must be strings with @property getters (pydantic v2 auto-parses env vars)
  - Example: `API_KEYS: str` → `@property def api_keys(self) -> list[str]`
- **Worker** (`worker/config.py`): Uses `from_env()` classmethod with manual `os.getenv()`

**Environment variable format:**
- All uppercase: `API_KEYS`, `ALLOWED_ORIGINS`, `COMFYUI_HOST`
- Proxy config in docker-compose.yml: `HTTP_PROXY=http://172.17.0.1:7897`
- **Critical**: `NO_PROXY` must include internal services: `localhost,127.0.0.1,redis,comfyui,api`

### Processor Pattern

All processors inherit from `BaseProcessor` (`worker/processors/base.py`) and implement:

1. **`load_workflow()`** - Load JSON template from `worker/workflows/{type}.json`
2. **`prepare_workflow(workflow, task_data)`** - Inject task-specific parameters:
   - Replace `{{OUTPUT_PREFIX}}` with `upscale_{task_id[:8]}`
   - Set input image paths in LoadImage nodes
   - Modify parameters based on `task_data['params']`
3. **`get_timeout()`** - Return task-specific timeout from config

**Example from `upscale.py`:**
```python
def prepare_workflow(self, workflow, task_data):
    task_id = task_data.get("task_id")
    output_prefix = f"upscale_{task_id[:8]}"

    # Extract image path from task_data['images']['source']['path']
    images = task_data.get("images", {})
    input_image = images.get("source", {}).get("path")

    # Replace template variables
    for node_id, node_data in workflow.items():
        if "inputs" in node_data:
            for key, value in node_data["inputs"].items():
                if "{{OUTPUT_PREFIX}}" in value:
                    node_data["inputs"][key] = value.replace("{{OUTPUT_PREFIX}}", output_prefix)

    # Set input image (node 3 is LoadImage)
    workflow["3"]["inputs"]["image"] = input_image
    return workflow
```

### Redis Data Structure

**Keys and TTL:**
- `task:data:{task_id}` - Full task data (JSON string, 7-day TTL)
- `task:status:{task_id}` - Status hash (7-day TTL)
- `task:progress:{task_id}` - Progress data (24-hour TTL)
- `ws:token:{token}` - WebSocket tokens (5-minute TTL)
- `queue:{type}` - Task queues (LIFO: `queue:upscale`, `queue:face-swap`, `queue:remove-background`)

**Critical implementation detail:**
- Redis `hset` does **not** accept nested dictionaries
- Store complex data as JSON strings: `task_json = json.dumps(task_data)` then `client.set(key, task_json)`

### ComfyUI Integration

**Workflow format:**
```json
{
  "3": {
    "inputs": {"image": "input.png", "upload": "image"},
    "class_type": "LoadImage"
  },
  "4": {
    "inputs": {"upscale_model": "RealESRGAN_x4plus.pth", "image": ["3", 0]},
    "class_type": "ImageScale"
  },
  "5": {
    "inputs": {"images": ["4", 0], "filename_prefix": "output"},
    "class_type": "SaveImage"
  }
}
```

**Node references:** `["3", 0]` means "output 0 from node 3"

**API endpoints:**
- POST `/prompt` - Submit workflow (returns `prompt_id`)
- GET `/history/{prompt_id}` - Check completion status
- GET `/view?filename={name}` - Download output image

### Import Conventions

**Absolute imports only** (relative imports fail in Docker):
```python
# Correct
from processors.base import BaseProcessor
from config import settings
from utils.redis import redis_client

# Incorrect (fails in containers)
from .base import BaseProcessor
from ..config import settings
```

**`__init__.py` files must export classes:**
```python
# worker/processors/__init__.py
from .base import BaseProcessor
from .face_swap import FaceSwapProcessor
# ...
```

## Common Issues and Solutions

### Docker Registry Blocking (China)
- Configure Docker daemon proxy via systemd
- Add build-time ARG to Dockerfiles: `ARG HTTP_PROXY`
- Runtime proxy in docker-compose.yml: `HTTP_PROXY=http://172.17.0.1:7897`
- **Critical**: Use `172.17.0.1` (Docker bridge IP) not `127.0.0.1` for host access from containers

### Workers Not Processing Tasks
- Check queue name mismatch: Worker polls `queue:upscale` but API adds to `task:queue`
- Solution: Worker polls multiple queues: `["queue:upscale", "queue:face-swap", "queue:remove-background"]`
- Check field name mismatch: API uses `"type"` but Worker expects `"task_type"`
- Solution: Accept both: `task_type = task_data.get("task_type") or task_data.get("type")`

### Pydantic v2 Settings Errors
- Error: `SettingsError: error parsing value for field "api_keys" from source "EnvSettingsSource"`
- Cause: pydantic-settings v2 auto-parses env vars, can't parse list from comma-separated string
- Solution: Use string fields with `@property` getters

### Internal Service Communication Blocked
- Error: Workers can't connect to ComfyUI (requests go through proxy)
- Cause: `HTTP_PROXY` intercepts internal traffic
- Solution: Set `NO_PROXY=localhost,127.0.0.1,redis,comfyui,api`

### ComfyUI Workflow Validation Errors
- Error: `Required input is missing: upscale_method, width, crop, height`
- Cause: Workflow JSON missing required parameters for node class
- Solution: Add all required parameters to workflow template (check ComfyUI node definitions)

### Template Variables Not Replaced
- Error: Output file named `{{OUTPUT_PREFIX}}_00001_.png`
- Cause: `prepare_workflow()` doesn't replace template variables
- Solution: Iterate through workflow nodes and replace `{{OUTPUT_PREFIX}}` with actual value

## Key Files to Understand

**Service orchestration:**
- `docker-compose.yml` - Multi-container setup with networks, volumes, GPU passthrough
- `.env.example` - All configuration variables

**API service:**
- `api/main.py` - FastAPI app setup, middleware, WebSocket, startup/shutdown
- `api/config.py` - Pydantic settings with @property computed fields
- `api/routers/tasks.py` - Task creation, status, listing, cancellation
- `api/utils/redis.py` - Redis client (create_task, add_to_queue, get_task_data)
- `api/utils/image.py` - Base64 decoding, shared volume storage

**Worker service:**
- `worker/main.py` - Worker loop, multi-queue polling, task dispatch
- `worker/processors/base.py` - Abstract processor with full lifecycle
- `worker/processors/upscale.py` - Upscale processor implementation
- `worker/utils/comfyui.py` - ComfyUI API client (submit, wait, download)
- `worker/utils/r2.py` - Cloudflare R2 upload client
- `worker/workflows/upscale.json` - ComfyUI workflow templates

**Proxy and networking:**
- `nginx/default.conf` - Reverse proxy with rate limiting, WebSocket support
- Docker proxy configuration in `/etc/systemd/system/docker.service.d/http-proxy.conf`

## Testing Checklist

When making changes:
1. Build affected services: `docker compose build api worker`
2. Restart services: `docker compose restart api worker`
3. Check logs for errors: `docker compose logs -f worker`
4. Verify Redis queue: `docker compose exec redis redis-cli LLEN queue:upscale`
5. Test full flow: Submit task → Check status → Verify output
6. Check GPU access: `docker compose exec comfyui nvidia-smi`
