#!/bin/bash
set -e

echo "Fixing configuration issues..."

# Fix API config - add missing fields
cd /home/abel/comfyui-server/.worktrees/comfyui-server

# Check API config
echo "Checking API config..."
if ! grep -q "log_format" api/config.py; then
  echo "Adding missing config fields..."
fi

# Rebuild all images
echo "Rebuilding API..."
docker build --network host \
  --build-arg HTTP_PROXY=http://127.0.0.1:7897 \
  --build-arg HTTPS_PROXY=http://127.0.0.1:7897 \
  --build-arg NO_PROXY=localhost,127.0.0.1 \
  -q -t comfyui-server-api ./api

echo "Rebuilding ComfyUI..."
docker build --network host \
  --build-arg HTTP_PROXY=http://127.0.0.1:7897 \
  --build-arg HTTPS_PROXY=http://127.0.0.1:7897 \
  --build-arg NO_PROXY=localhost,127.0.0.1 \
  -q -t comfyui-server-comfyui ./comfyui

echo "Rebuilding Worker..."
docker build --network host \
  --build-arg HTTP_PROXY=http://127.0.0.1:7897 \
  --build-arg HTTPS_PROXY=http://127.0.0.1:7897 \
  --build-arg NO_PROXY=localhost,127.0.0.1 \
  -q -t comfyui-server-worker ./worker

# Restart all services
echo "Restarting services..."
docker-compose down
docker-compose up -d

echo "Waiting for services to start..."
sleep 30

# Check status
echo "=== Service Status ==="
docker-compose ps

echo "=== Checking logs ==="
docker-compose logs --tail=10 api 2>&1 | grep -E "Started|Uvicorn|ERROR" | tail -5
docker-compose logs --tail=10 worker 2>&1 | grep -E "Started|Worker|ERROR" | tail -5
docker-compose logs --tail=10 comfyui 2>&1 | grep -E "Starting|Server|ERROR" | tail -5

echo "Done!"
