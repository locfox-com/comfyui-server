# Deployment Guide

This guide covers deploying the ComfyUI AI Image Server to production.

## Prerequisites

- Docker and Docker Compose installed
- Cloudflare R2 bucket (or compatible S3 storage)
- Domain name (optional, for SSL)
- At least 8GB RAM and 20GB disk space
- GPU with CUDA support (recommended) or CPU-only mode

## Quick Start

1. **Clone and configure:**
   ```bash
   git clone <repository>
   cd comfyui-server
   cp .env.example .env
   ```

2. **Edit environment variables:**
   ```bash
   # Edit .env with your values
   nano .env
   ```

3. **Start services:**
   ```bash
   docker compose up -d
   ```

4. **Download AI models:**
   ```bash
   docker compose exec comfyui bash /app/download_models.sh
   ```

5. **Verify deployment:**
   ```bash
   curl http://localhost/health
   ```

## Configuration

### Required Environment Variables

```bash
# API Configuration
JWT_SECRET_KEY=<generate-secure-random-string>
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com

# Database
POSTGRES_USER=apiuser
POSTGRES_PASSWORD=<secure-password>
POSTGRES_DB=comfyui_server

# Redis
REDIS_PASSWORD=<secure-password>

# Cloudflare R2
R2_ACCOUNT_ID=<your-account-id>
R2_ACCESS_KEY_ID=<your-access-key>
R2_SECRET_ACCESS_KEY=<your-secret-key>
R2_BUCKET_NAME=<your-bucket-name>
R2_PUBLIC_URL=https://<your-bucket>.r2.dev

# ComfyUI
COMFYUI_SERVER_URL=http://comfyui:8188
GPU_MEMORY_LIMIT=16g
GPU_ID=0
```

### Generating Secure Keys

Generate random strings for secrets:

```bash
# JWT secret (64 characters)
openssl rand -hex 32

# Database password (32 characters)
openssl rand -hex 16

# Redis password (32 characters)
openssl rand -hex 16
```

## Production Deployment

### SSL/TLS with Let's Encrypt

1. **Use Certbot with Nginx:**

   Create `docker-compose.prod.yml`:
   ```yaml
   services:
     certbot:
       image: certbot/certbot
       volumes:
         - ./certbot/conf:/etc/letsencrypt
         - ./certbot/www:/var/www/certbot
       entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done;'"

     nginx:
       ports:
         - "80:80"
         - "443:443"
       volumes:
         - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
         - ./certbot/conf:/etc/letsencrypt:ro
         - ./certbot/www:/var/www/certbot:ro
   ```

2. **Update Nginx config for SSL:**

   ```nginx
   server {
       listen 443 ssl http2;
       server_name yourdomain.com;

       ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

       # ... rest of config
   }

   server {
       listen 80;
       server_name yourdomain.com;
       return 301 https://$server_name$request_uri;
   }
   ```

### Scaling Workers

Scale horizontally by adding more workers:

```bash
# Scale to 3 workers
docker compose up -d --scale worker=3

# Or update docker-compose.yml:
services:
  worker:
    deploy:
      replicas: 3
```

### Resource Limits

Configure resource limits in `docker-compose.yml`:

```yaml
services:
  comfyui:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
        limits:
          memory: 16G

  worker:
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
```

## Monitoring

### Health Checks

```bash
# Check all services
docker compose ps

# Check API health
curl http://localhost/health

# Check logs
docker compose logs -f api
docker compose logs -f worker
```

### Metrics

The API exposes metrics at `/metrics` for Prometheus scraping:

```bash
curl http://localhost/metrics
```

Key metrics:
- `jobs_total` - Total jobs processed
- `jobs_duration_seconds` - Job processing duration
- `active_jobs` - Currently active jobs
- `gpu_memory_used_bytes` - GPU memory usage

### Logging

View logs for specific services:

```bash
# All services
docker compose logs -f

# API only
docker compose logs -f api

# Worker only
docker compose logs -f worker

# Last 100 lines
docker compose logs --tail=100 api
```

## Troubleshooting

### Common Issues

**1. Workers not processing jobs:**
   ```bash
   # Check Redis connection
   docker compose logs worker | grep Redis

   # Check ComfyUI connection
   docker compose logs worker | grep ComfyUI

   # Verify jobs in queue
   docker compose exec redis redis-cli LLEN job_queue
   ```

**2. GPU not detected:**
   ```bash
   # Check nvidia-docker runtime
   docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

   # Verify GPU access in ComfyUI container
   docker compose exec comfyui nvidia-smi
   ```

**3. Models not loading:**
   ```bash
   # Check model files
   docker compose exec comfyui ls -lh /app/ComfyUI/models/

   # Re-download models
   docker compose exec comfyui bash /app/download_models.sh
   ```

**4. R2 upload failures:**
   ```bash
   # Check R2 credentials
   docker compose exec worker env | grep R2

   # Test R2 connection
   docker compose exec worker python -c "
   from worker.utils.r2 import R2Client
   client = R2Client()
   print('Bucket:', client.bucket)
   "
   ```

### Performance Tuning

**Increase job throughput:**
- Scale workers horizontally: `--scale worker=3`
- Increase Redis memory
- Use faster storage for ComfyUI output

**Reduce latency:**
- Use local SSD for ComfyUI models
- Pre-load models into GPU memory
- Enable Keep-Alive connections

**Optimize GPU usage:**
- Adjust `GPU_MEMORY_LIMIT` based on available VRAM
- Use CUDA_VISIBLE_DEVICES to assign specific GPUs
- Enable GPU monitoring to detect bottlenecks

## Backup and Recovery

### Database Backup

```bash
# Automated backup script
cat > backup.sh <<'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker compose exec -T db pg_dump -U apiuser comfyui_server > backup_$DATE.sql
gzip backup_$DATE.sql
aws s3 cp backup_$DATE.sql.gz s3://your-backup-bucket/
EOF

chmod +x backup.sh

# Run daily via cron
0 2 * * * /path/to/backup.sh
```

### Restore Database

```bash
# Restore from backup
gunzip backup_YYYYMMDD_HHMMSS.sql.gz
docker compose exec -T db psql -U apiuser comfyui_server < backup_YYYYMMDD_HHMMSS.sql
```

## Security Checklist

- [ ] Use strong, unique passwords for all services
- [ ] Enable SSL/TLS in production
- [ ] Set up firewall rules (only allow necessary ports)
- [ ] Use secrets management for sensitive data
- [ ] Enable rate limiting (configured in Nginx)
- [ ] Regular security updates: `docker compose pull && docker compose up -d`
- [ ] Monitor logs for suspicious activity
- [ ] Use read-only database credentials for workers
- [ ] Enable audit logging for API operations
- [ ] Set up intrusion detection (e.g., CrowdSec)

## Cost Optimization

**Cloudflare R2:**
- Use lifecycle policies to move old files to cheaper storage
- Enable R2 cache for frequently accessed images
- Consider CDN for public URLs

**Compute:**
- Use spot/preemptible instances for workers
- Scale to zero during low traffic periods
- Use CPU-only for smaller workloads

**Database:**
- Archive old job records periodically
- Use connection pooling
- Optimize queries with proper indexes

## Support

For issues and questions:
- Check logs: `docker compose logs -f`
- Review configuration: `docker compose config`
- Health check: `curl http://localhost/health`
- GitHub Issues: <repository-url>
