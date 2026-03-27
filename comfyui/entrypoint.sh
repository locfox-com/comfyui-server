#!/bin/bash

set -e

echo "Starting ComfyUI server..."

# Start ComfyUI (internal network only)
cd /app/ComfyUI

exec python main.py \
    --listen 0.0.0.0 \
    --port 8188 \
    --enable-cors-header * \
    --disable-auto-launch \
    --disable-xformers
