# ComfyUI AI Image Server

A scalable, production-ready AI image processing server built on ComfyUI with async job queues, Redis backend, and Cloudflare R2 storage.

## Features

- **Three AI Operations**:
  - Face Swap: Swap faces between images using ReActor
  - Image Upscaling: Enhance resolution with Real-ESRGAN (2x/4x)
  - Background Removal: Remove backgrounds with RMBG-1.4

- **Production Architecture**:
  - Async REST API with FastAPI
  - Redis-based job queue
  - Horizontal scaling workers
  - WebSocket support for real-time updates
  - Cloudflare R2 storage integration
  - Nginx reverse proxy with rate limiting
  - PostgreSQL database for job tracking

- **Developer Experience**:
  - Docker Compose setup
  - Comprehensive API documentation
  - Integration tests included
  - Environment-based configuration
  - Structured logging

## Quick Start

### Prerequisites

- Docker and Docker Compose
- 8GB+ RAM
- 20GB+ disk space
- GPU with CUDA support (optional, CPU mode available)

### 1. Clone and Configure

```bash
git clone <repository>
cd comfyui-server
cp .env.example .env
```

### 2. Edit Environment Variables

Edit `.env` with your configuration:

```bash
# Generate secure keys
JWT_SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 16)
REDIS_PASSWORD=$(openssl rand -hex 16)

# Cloudflare R2 (required)
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=your_bucket_name
R2_PUBLIC_URL=https://your_bucket.r2.dev
```

### 3. Start Services

```bash
# Start all services
docker compose up -d

# Download AI models (~500MB)
docker compose exec comfyui bash /app/download_models.sh
```

### 4. Verify Deployment

```bash
# Check health
curl http://localhost/health

# View logs
docker compose logs -f
```

## Usage

### Create a Face Swap Job

```bash
curl -X POST http://localhost/api/v1/jobs/face-swap \
  -H "Content-Type: application/json" \
  -d '{
    "source_image_url": "https://example.com/source.jpg",
    "target_image_url": "https://example.com/target.jpg"
  }'
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "operation": "face_swap",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Check Job Status

```bash
curl http://localhost/api/v1/jobs/{job_id}
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "operation": "face_swap",
  "output_url": "https://r2.dev/output/result.jpg",
  "created_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:31:15Z"
}
```

## Architecture

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Client    │─────▶│   Nginx     │─────▶│  FastAPI    │
└─────────────┘      └─────────────┘      └─────────────┘
                                                │
                                                ▼
                                        ┌─────────────┐
                                        │  PostgreSQL │
                                        └─────────────┘
                                                │
                                                ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  ComfyUI    │◀─────│   Worker    │◀─────│   Redis     │
└─────────────┘      └─────────────┘      └─────────────┘
                            │
                            ▼
                    ┌─────────────┐
                    │ Cloudflare  │
                    │     R2      │
                    └─────────────┘
```

## API Endpoints

### Jobs
- `POST /api/v1/jobs/face-swap` - Create face swap job
- `POST /api/v1/jobs/upscale` - Create upscale job
- `POST /api/v1/jobs/remove-background` - Create background removal job
- `GET /api/v1/jobs/{job_id}` - Get job status
- `GET /api/v1/jobs` - List all jobs
- `DELETE /api/v1/jobs/{job_id}` - Cancel job

### WebSocket
- `WS /ws/jobs/{job_id}` - Real-time job updates

### System
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

See [docs/API.md](docs/API.md) for complete API documentation.

## Project Structure

```
comfyui-server/
├── api/                    # FastAPI application
│   ├── main.py            # API entry point
│   ├── models.py          # Database models
│   ├── config.py          # Configuration
│   └── jobs/              # Job creation endpoints
│       ├── face_swap.py
│       ├── upscale.py
│       └── remove_bg.py
├── worker/                # Worker service
│   ├── main.py           # Worker entry point
│   ├── config.py         # Worker configuration
│   ├── processors/       # Job processors
│   │   ├── base.py       # Base processor
│   │   ├── face_swap.py  # Face swap processor
│   │   ├── upscale.py    # Upscale processor
│   │   └── remove_bg.py  # Background removal processor
│   ├── utils/            # Utility modules
│   │   ├── redis.py      # Redis client
│   │   ├── comfyui.py    # ComfyUI API client
│   │   ├── r2.py         # R2 upload client
│   │   ├── gpu_monitor.py # GPU monitoring
│   │   └── cleanup.py    # Cleanup utilities
│   └── workflows/        # ComfyUI workflow templates
│       ├── face_swap.json
│       ├── upscale.json
│       └── remove_background.json
├── comfyui/              # ComfyUI service
│   ├── Dockerfile
│   └── download_models.sh
├── nginx/                # Nginx configuration
│   └── default.conf
├── tests/                # Integration tests
│   └── integration/
│       └── test_full_flow.py
├── docs/                 # Documentation
│   ├── API.md           # API documentation
│   └── DEPLOYMENT.md    # Deployment guide
├── docker-compose.yml
├── .env.example
└── README.md
```

## Configuration

### Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `JWT_SECRET_KEY`: Secret for JWT tokens
- `POSTGRES_PASSWORD`: Database password
- `REDIS_PASSWORD`: Redis password
- `R2_*`: Cloudflare R2 credentials
- `GPU_MEMORY_LIMIT`: GPU memory allocation
- `COMFYUI_SERVER_URL`: ComfyUI server URL

### Scaling Workers

Scale horizontally by adding more workers:

```bash
docker compose up -d --scale worker=3
```

Or modify `docker-compose.yml`:

```yaml
services:
  worker:
    deploy:
      replicas: 3
```

## Monitoring

### Health Checks

```bash
# API health
curl http://localhost/health

# Service status
docker compose ps

# View logs
docker compose logs -f api
docker compose logs -f worker
```

### Metrics

Prometheus metrics available at `/metrics`:

- `jobs_total`: Total jobs processed
- `jobs_duration_seconds`: Job processing duration
- `active_jobs`: Currently active jobs
- `gpu_memory_used_bytes`: GPU memory usage

## Development

### Running Tests

```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Run integration tests
pytest tests/integration/

# Run specific test
pytest tests/integration/test_full_flow.py::TestHealthEndpoint
```

### Local Development

```bash
# Start services
docker compose up -d

# Run API locally (for development)
cd api
pip install -r requirements.txt
uvicorn main:app --reload

# Run worker locally
cd worker
pip install -r requirements.txt
python main.py
```

## Troubleshooting

### Workers not processing jobs

```bash
# Check Redis
docker compose logs worker | grep Redis

# Check ComfyUI connection
docker compose logs worker | grep ComfyUI

# View job queue
docker compose exec redis redis-cli LLEN job_queue
```

### GPU not detected

```bash
# Verify GPU
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Check ComfyUI GPU access
docker compose exec comfyui nvidia-smi
```

### Models not loading

```bash
# Check models
docker compose exec comfyui ls -lh /app/ComfyUI/models/

# Re-download models
docker compose exec comfyui bash /app/download_models.sh
```

For more troubleshooting tips, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Production Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for:

- SSL/TLS setup with Let's Encrypt
- Worker scaling and resource limits
- Performance tuning
- Backup and recovery
- Security checklist
- Cost optimization

## Performance

**Typical Processing Times** (on NVIDIA RTX 3080):

- Face Swap: 5-10 seconds
- Image Upscale (2x): 3-5 seconds
- Image Upscale (4x): 8-12 seconds
- Background Removal: 2-4 seconds

**Throughput**:
- Single GPU: 6-12 jobs/minute
- With 3 workers: 18-36 jobs/minute

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

- Documentation: [docs/](docs/)
- Issues: GitHub Issues
- Deployment Guide: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- API Reference: [docs/API.md](docs/API.md)

## Acknowledgments

Built with:
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - Powerful UI for Stable Diffusion
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Redis](https://redis.io/) - In-memory data store
- [Cloudflare R2](https://www.cloudflare.com/products/r2/) - S3-compatible storage
- [Nginx](https://www.nginx.com/) - Reverse proxy

AI Models:
- [ReActor](https://github.com/Gourieff/ComfyUI-ReActor) - Face swapping
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) - Image upscaling
- [RMBG-1.4](https://huggingface.co/briaai/RMBG-1.4) - Background removal

---

**Ready to deploy?** Start with the [Deployment Guide](docs/DEPLOYMENT.md).
